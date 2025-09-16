"""Realtime 音声入出力を扱うユーティリティ群。"""

import asyncio
import queue
import threading
from typing import Any, Callable, Optional

import numpy as np
import sounddevice as sd


class AudioHandler:
    """音声ストリームの入出力とバッファを管理する。"""

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        blocksize: int = 960,
        logger: Optional[Callable[[str], None]] = None,
        enable_audio: bool = True,
    ):
        """フォーマット設定とロガーを受け取って初期化する。"""
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.log = logger or print
        self.enable_audio = enable_audio

        self.input_queue: "queue.Queue[bytes]" = queue.Queue()
        self.input_stream: Optional[sd.InputStream] = None
        self.output_stream: Optional[sd.OutputStream] = None
        self.is_running = False

        self.audio_buffer = bytearray()
        self.buffer_lock = threading.Lock()
        self.max_buffer_size = self.sample_rate * 2 * 30  # roughly 30s
        self.target_buffer_size = self.blocksize * 8

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
            required_bytes = frames * 2

            if len(self.audio_buffer) >= required_bytes:
                audio_bytes = bytes(self.audio_buffer[:required_bytes])
                self.audio_buffer = self.audio_buffer[required_bytes:]
                audio_array = (
                    np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767.0
                )
                outdata[:, 0] = audio_array
                outdata[:, 1] = audio_array
            else:
                outdata.fill(0)

    def start(self) -> None:
        """入出力ストリームを開いて処理を開始する。"""
        if not self.enable_audio:
            self.log("🔇 音声入出力を無効化しているため初期化をスキップします")
            return

        self.is_running = True

        try:
            default_input = sd.query_devices(kind="input")
            default_output = sd.query_devices(kind="output")
            self.log(f"📥 Using input device: {default_input['name']}")
            self.log(f"📤 Using output device: {default_output['name']}")

            self.input_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.blocksize,
                callback=self.audio_input_callback,
                latency="low",
            )

            self.output_stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=2,
                dtype="float32",
                blocksize=self.blocksize,
                callback=self.audio_output_callback,
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
        if not self.enable_audio:
            return

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
                if bytes_to_remove > 0:
                    self.log(f"⚠️ Buffer near limit, removed {bytes_to_remove} bytes")

            self.audio_buffer.extend(audio_data)

    def clear_audio_buffer(self) -> None:
        """再生バッファをクリアする。"""
        with self.buffer_lock:
            buffer_size = len(self.audio_buffer)
            self.audio_buffer.clear()
            if buffer_size > 0:
                self.log(f"🗑️ Cleared {buffer_size} bytes from audio buffer")

    def get_buffer_status(self) -> tuple[int, int]:
        """現在のバッファサイズと上限を返す。"""
        with self.buffer_lock:
            return len(self.audio_buffer), self.max_buffer_size
