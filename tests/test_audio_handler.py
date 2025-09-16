"""Unit tests for `AudioHandler` behaviours that do not touch LLM APIs."""

import asyncio
from typing import List

import numpy as np

from realtime_voice.audio import AudioHandler


class LogCollector:
    """テスト用にログメッセージを捕捉するコレクタ。"""

    def __init__(self) -> None:
        """空のメッセージリストを初期化する。"""
        self.messages: List[str] = []

    def __call__(self, message: str) -> None:
        """渡されたメッセージを蓄積する。"""
        self.messages.append(message)


def test_audio_input_callback_enqueues_pcm_bytes() -> None:
    """マイク入力が PCM16 バイト列としてキューに積まれる。"""
    collector = LogCollector()
    handler = AudioHandler(sample_rate=8000, blocksize=320, logger=collector)

    samples = np.array([[0.0], [0.5], [-0.5]], dtype=np.float32)
    handler.audio_input_callback(samples, frames=len(samples), time=None, status=0)

    queued = handler.input_queue.get_nowait()
    # 0.5 * 32767 ≈ 16383 -> ensure PCM conversion occurred
    assert isinstance(queued, bytes)
    assert len(queued) == len(samples) * 2  # int16 => 2 bytes per sample
    assert collector.messages == []


def test_add_audio_to_buffer_trims_when_exceeding_capacity() -> None:
    """バッファ上限を超えると古いデータが削除される。"""
    collector = LogCollector()
    handler = AudioHandler(sample_rate=8000, blocksize=320, logger=collector)
    handler.max_buffer_size = 16

    handler.add_audio_to_buffer(b"a" * 12)
    handler.add_audio_to_buffer(b"b" * 12)

    current, maximum = handler.get_buffer_status()
    assert maximum == 16
    assert current == 16
    assert any("Buffer near limit" in message for message in collector.messages)


def test_audio_output_callback_consumes_buffer() -> None:
    """再生コールバックがバッファを消費してステレオ出力する。"""
    collector = LogCollector()
    handler = AudioHandler(sample_rate=8000, blocksize=4, logger=collector)

    # Prepare 4 frames (int16) worth of audio (8 bytes)
    audio_bytes = (np.array([0, 8192, -8192, 16384], dtype=np.int16)).tobytes()
    handler.add_audio_to_buffer(audio_bytes)

    out = np.zeros((4, 2), dtype=np.float32)
    handler.audio_output_callback(out, frames=4, time=None, status=0)

    # Mono buffer duplicated across stereo channels
    expected = np.array([0.0, 8192 / 32767.0, -8192 / 32767.0, 16384 / 32767.0], dtype=np.float32)
    np.testing.assert_allclose(out[:, 0], expected, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(out[:, 1], expected, rtol=1e-5, atol=1e-5)

    current, _ = handler.get_buffer_status()
    assert current == 0
    assert collector.messages == []


def test_get_input_audio_returns_none_when_queue_empty() -> None:
    """キューが空の場合は None が返る。"""
    handler = AudioHandler(sample_rate=8000, blocksize=320, logger=lambda _: None)

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(handler.get_input_audio(timeout=0.01))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        asyncio.set_event_loop(None)

    assert result is None
