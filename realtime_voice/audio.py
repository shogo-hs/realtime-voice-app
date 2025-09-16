"""Realtime 音声入出力を扱うユーティリティ群。"""

from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, Callable, Optional, Tuple, Union

import numpy as np
import sounddevice as sd

from .config import AudioConfig


class AudioHandler:
    """音声ストリームの入出力とバッファを管理する。"""

    def __init__(
        self,
        config: AudioConfig,
        logger: Optional[Callable[[str], None]] = None,
    ):
        """フォーマット設定とロガーを受け取って初期化する。"""
        self._config = config
        self.sample_rate = config.sample_rate
        self.blocksize = config.blocksize
        self.input_channels = config.input_channels
        self.output_channels = config.output_channels
        self.log = logger or print

        self.input_queue: "queue.Queue[bytes]" = queue.Queue()
        self.input_stream: Optional[sd.InputStream] = None
        self.output_stream: Optional[sd.OutputStream] = None
        self.is_running = False

        self.audio_buffer = bytearray()
        self.buffer_lock = threading.Lock()
        self.max_buffer_size = (
            self.sample_rate * max(self.output_channels, 1) * 2 * self._config.max_buffer_seconds
        )
        self.target_buffer_size = self.blocksize * 8
        self._buffer_warning_triggered = False

    def audio_input_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time: Any,
        status: sd.CallbackFlags,
    ) -> None:
        """マイク入力を PCM16 に変換して送信用キューへ積む。"""
        if status:
            self.log(f"Input status: {status}")

        audio_data = (indata * 32767).astype(np.int16).tobytes()
        try:
            self.input_queue.put_nowait(audio_data)
        except queue.Full:
            pass

    def audio_output_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time: Any,
        status: sd.CallbackFlags,
    ) -> None:
        """バッファ済み音声をステレオ出力へ書き込む。"""
        if status and status != sd.CallbackFlags.OUTPUT_UNDERFLOW:
            self.log(f"Output status: {status}")

        with self.buffer_lock:
            required_bytes = frames * 2  # 入力は常にモノラルPCM16

            if len(self.audio_buffer) >= required_bytes:
                audio_bytes = bytes(self.audio_buffer[:required_bytes])
                self.audio_buffer = self.audio_buffer[required_bytes:]
                audio_array = (
                    np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767.0
                )
                if self.output_channels == 1:
                    outdata[:, 0] = audio_array
                else:
                    outdata[:, 0] = audio_array
                    outdata[:, 1] = audio_array
            else:
                outdata.fill(0)

    def _normalize_device(self, value: Union[int, str, None]) -> Optional[Union[int, str]]:
        """デバイス指定を sounddevice に渡せる形式へ正規化する。"""
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        value = value.strip()
        if value.lower() == "default":
            return None
        if value.isdigit():
            return int(value)
        return value

    def _resolve_device(
        self, kind: str, desired_channels: int
    ) -> Tuple[Optional[Union[int, str]], dict]:
        """設定値と環境に基づいて入出力デバイスを選択する。"""
        override = (
            self._normalize_device(self._config.input_device)
            if kind == "input"
            else self._normalize_device(self._config.output_device)
        )
        if override is not None:
            info = sd.query_devices(override, kind=kind)
            return override, info

        defaults = sd.default.device or (None, None)
        index = 0 if kind == "input" else 1
        candidate = defaults[index]
        if candidate not in (None, -1):
            info = sd.query_devices(candidate, kind=kind)
            return candidate, info

        for device_id, info in enumerate(sd.query_devices()):
            channels_key = "max_input_channels" if kind == "input" else "max_output_channels"
            if info.get(channels_key, 0) >= desired_channels:
                return device_id, info

        raise RuntimeError(
            f"利用可能な{'入力' if kind == 'input' else '出力'}デバイスが見つかりませんでした"
        )

    def start(self) -> None:
        """入出力ストリームを開いて処理を開始する。"""
        self.is_running = True

        try:
            input_device, input_info = self._resolve_device("input", self.input_channels)
            output_device, output_info = self._resolve_device("output", self.output_channels)
            self.log(f"📥 使用する入力デバイス: {input_info['name']}")
            self.log(f"📤 使用する出力デバイス: {output_info['name']}")

            self.input_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.input_channels,
                dtype="float32",
                blocksize=self.blocksize,
                callback=self.audio_input_callback,
                device=input_device,
                latency="low",
            )

            self.output_stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.output_channels,
                dtype="float32",
                blocksize=self.blocksize,
                callback=self.audio_output_callback,
                device=output_device,
                latency="low",
            )

            self.input_stream.start()
            self.output_stream.start()
            self.log(
                f"✅ Audio streams started (Sample rate: {self.sample_rate}Hz, Block size: {self.blocksize})"
            )

        except Exception as exc:  # noqa: BLE001
            self.log(f"Error starting audio streams: {exc}")
            raise

    def stop(self) -> None:
        """ストリームを停止してデバイスを解放する。"""
        self.is_running = False

        if self.input_stream:
            self.input_stream.stop()
            self.input_stream.close()

        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()

        self.log("Audio streams stopped")

    async def get_input_audio(self, timeout: Optional[float] = 0.1) -> Optional[bytes]:
        """キューに溜まった音声を取得し、無ければ None を返す。"""
        loop = asyncio.get_event_loop()

        def _get_item() -> bytes:
            if timeout is None:
                return self.input_queue.get()
            return self.input_queue.get(timeout=timeout)

        try:
            return await loop.run_in_executor(None, _get_item)
        except queue.Empty:
            return None

    def add_audio_to_buffer(self, audio_data: bytes) -> None:
        """再生用バッファへ音声データを追加する。"""
        with self.buffer_lock:
            current_size = len(self.audio_buffer)
            if current_size + len(audio_data) > self.max_buffer_size:
                bytes_to_remove = (current_size + len(audio_data)) - self.max_buffer_size
                self.audio_buffer = self.audio_buffer[bytes_to_remove:]
                if bytes_to_remove > 0 and not self._buffer_warning_triggered:
                    self.log(
                        f"⚠️ Buffer near limit, removed {bytes_to_remove} bytes; consider lowering "
                        "max_buffer_seconds"
                    )
                    self._buffer_warning_triggered = True

            self.audio_buffer.extend(audio_data)

    def clear_audio_buffer(self) -> None:
        """再生バッファをクリアする。"""
        with self.buffer_lock:
            buffer_size = len(self.audio_buffer)
            self.audio_buffer.clear()
            if buffer_size > 0:
                self.log(f"🗑️ Cleared {buffer_size} bytes from audio buffer")
            self._buffer_warning_triggered = False

    def get_buffer_status(self) -> tuple[int, int]:
        """現在のバッファサイズと上限を返す。"""
        with self.buffer_lock:
            return len(self.audio_buffer), self.max_buffer_size
