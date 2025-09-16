"""音声アシスタントをバックグラウンド実行するコントローラ。"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .assistant import run_assistant
from .config import AppConfig


@dataclass
class LogEntry:
    """アシスタント実行時のログエントリを表す。"""

    id: int
    timestamp: float
    message: str


class VoiceSessionController:
    """アシスタントの起動・停止と状態問い合わせを司る。"""

    def __init__(self, *, logger: logging.Logger, config: AppConfig) -> None:
        """内部状態を初期化し、空のログ履歴を用意する。"""
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._lock = threading.Lock()
        self._history_lock = threading.Lock()

        self._logger = logger
        self._config = config

        self._log_history: List[LogEntry] = []
        self._next_log_id = 1
        self._state = "idle"

    # Logging helpers
    def _log(self, message: str) -> None:
        """メッセージを履歴に追加し、必要に応じてトリムする。"""
        self._logger.info(message)
        with self._history_lock:
            entry = LogEntry(self._next_log_id, time.time(), message)
            self._next_log_id += 1
            self._log_history.append(entry)
            if len(self._log_history) > 2000:
                self._log_history = self._log_history[-1000:]

    def get_logs(self, after_id: int = 0) -> List[LogEntry]:
        """指定 ID 以降のログエントリを返す。"""
        with self._history_lock:
            return [entry for entry in self._log_history if entry.id > after_id]

    def state(self) -> str:
        """現在の状態を返す。"""
        with self._lock:
            return self._state

    def status(self) -> Dict[str, object]:
        """Web ダッシュボード向けに状態を要約して返す。"""
        with self._lock:
            running = self._running
            state = self._state
        with self._history_lock:
            log_count = len(self._log_history)
        return {"state": state, "running": running, "log_count": log_count}

    def start(self) -> bool:
        """未起動であればバックグラウンドスレッドを立ち上げる。"""
        with self._lock:
            if self._running:
                self._log("⚠️ Assistant already running")
                return False

            self._stop_event.clear()
            self._running = True
            self._state = "starting"

            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            self._log("🚀 Starting realtime assistant")
            return True

    def _run_loop(self) -> None:
        """専用スレッドで asyncio ループを実行する。"""
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._runner())
        self._loop.run_forever()

    async def _runner(self) -> None:
        """アシスタントを起動してライフサイクルを監視する。"""
        with self._lock:
            self._state = "connecting"
        try:
            await run_assistant(
                config=self._config,
                logger=self._log,
                stop_event=self._stop_event,
            )
            with self._lock:
                if self._stop_event.is_set():
                    self._state = "stopped"
                else:
                    self._state = "completed"
        except Exception as exc:  # noqa: BLE001
            self._log(f"❌ Unexpected error: {exc}")
            with self._lock:
                self._state = "error"
        finally:
            with self._lock:
                self._running = False
            self._stop_event.set()
            loop = asyncio.get_running_loop()
            loop.call_soon(loop.stop)

    def stop(self) -> bool:
        """停止を指示し、終了まで待機する。"""
        with self._lock:
            if not self._running:
                return False

            self._log("🛑 Stop requested")
            self._state = "stopping"
            self._stop_event.set()

            if self._loop:
                self._loop.call_soon_threadsafe(lambda: None)

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2)

            self._running = False
            self._state = "stopped"
            return True
