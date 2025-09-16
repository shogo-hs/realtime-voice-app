"""Audio helpers for realtime microphone capture and playback."""

import asyncio
import queue
import threading
from typing import Any, Callable, Optional

import numpy as np
import sounddevice as sd


class AudioHandler:
    """Realtime audio input/output manager."""

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        blocksize: int = 960,
        logger: Optional[Callable[[str], None]] = None,
    ):
        """Initialise handler with audio format and optional logger."""
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.log = logger or print

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
        """Receive microphone frames and enqueue them for transmission."""
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
        """Stream buffered assistant audio to the speaker output."""
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
        """Open input/output streams and begin audio processing."""
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
        """Stop streams and release devices."""
        self.is_running = False

        if self.input_stream:
            self.input_stream.stop()
            self.input_stream.close()

        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()

        self.log("Audio streams stopped")

    async def get_input_audio(self, timeout: Optional[float] = 0.1) -> Optional[bytes]:
        """Return the next audio chunk from the queue if available."""
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
        """Append assistant audio bytes to the playback buffer."""
        with self.buffer_lock:
            current_size = len(self.audio_buffer)
            if current_size + len(audio_data) > self.max_buffer_size:
                bytes_to_remove = (current_size + len(audio_data)) - self.max_buffer_size
                self.audio_buffer = self.audio_buffer[bytes_to_remove:]
                if bytes_to_remove > 0:
                    self.log(f"⚠️ Buffer near limit, removed {bytes_to_remove} bytes")

            self.audio_buffer.extend(audio_data)

    def clear_audio_buffer(self) -> None:
        """Remove all audio currently queued for playback."""
        with self.buffer_lock:
            buffer_size = len(self.audio_buffer)
            self.audio_buffer.clear()
            if buffer_size > 0:
                self.log(f"🗑️ Cleared {buffer_size} bytes from audio buffer")

    def get_buffer_status(self) -> tuple[int, int]:
        """Return current and maximum buffer sizes in bytes."""
        with self.buffer_lock:
            return len(self.audio_buffer), self.max_buffer_size
