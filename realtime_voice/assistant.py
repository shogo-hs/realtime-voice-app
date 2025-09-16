"""Realtime エージェントとの対話セッションを制御する。"""

import asyncio
import os
import threading
from typing import Callable, Optional, Union

from agents.realtime import RealtimeAgent, RealtimeRunner
from dotenv import load_dotenv

from .audio import AudioHandler

INSTRUCTIONS = (
    "You are a courteous customer support specialist for this voice assistant. Always respond in "
    "polite Japanese, show empathy for the caller's situation, confirm your understanding before "
    "answering, and provide clear step-by-step guidance. Keep answers concise but thorough, avoid "
    "slang, and proactively offer additional help when appropriate. If you are unsure, admit it and "
    "suggest escalating or checking official documentation."
)


load_dotenv()


StopEvent = Union[asyncio.Event, threading.Event]


async def run_assistant(
    logger: Optional[Callable[[str], None]] = None,
    stop_event: Optional[StopEvent] = None,
) -> None:
    """停止要求を受けるまで音声セッションを実行する。"""
    log = logger or print
    audio_handler = AudioHandler(sample_rate=24000, blocksize=960, logger=log)

    def stop_requested() -> bool:
        """停止フラグが立っていれば真を返す。"""
        if not stop_event:
            return False
        return stop_event.is_set()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")

    agent = RealtimeAgent(
        name="Assistant",
        instructions=INSTRUCTIONS,
    )

    runner = RealtimeRunner(
        starting_agent=agent,
        config={
            "model_settings": {
                "model_name": "gpt-realtime",
                "instructions": INSTRUCTIONS,
                "voice": "alloy",
                "modalities": ["audio"],
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {"model": "gpt-4o-mini-transcribe"},
                "turn_detection": {
                    "type": "semantic_vad",
                    "interrupt_response": True,
                },
            }
        },
    )

    log("🔄 Connecting to OpenAI Realtime API...")
    session = await runner.run(model_config={"api_key": os.getenv("OPENAI_API_KEY")})

    audio_handler.start()
    session_connected = asyncio.Event()

    receiving_audio = False
    audio_chunks_received = 0
    total_audio_bytes = 0

    async def send_audio_task() -> None:
        """マイク入力をリアルタイムセッションへ順次送信する。"""
        nonlocal receiving_audio
        await session_connected.wait()
        log("🎤 Audio transmission started")

        try:
            while True:
                if stop_requested():
                    break

                audio_data = await audio_handler.get_input_audio(timeout=0.1)
                if not audio_data:
                    if stop_requested():
                        break
                    continue

                if not receiving_audio:
                    await session.send_audio(audio_data)

        except asyncio.CancelledError:
            log("Audio transmission task cancelled")
        except Exception as exc:  # noqa: BLE001
            log(f"Error in send_audio_task: {exc}")

    async def buffer_monitor_task() -> None:
        """再生バッファの使用率を定期的にログへ出力する。"""
        await session_connected.wait()

        try:
            while True:
                if stop_requested():
                    break
                await asyncio.sleep(5)
                current, max_size = audio_handler.get_buffer_status()
                if current > 0:
                    percentage = (current / max_size) * 100
                    if percentage > 50:
                        log(f"📊 Buffer usage: {percentage:.1f}% ({current}/{max_size} bytes)")
        except asyncio.CancelledError:
            pass

    send_task = asyncio.create_task(send_audio_task())
    monitor_task = asyncio.create_task(buffer_monitor_task())

    try:
        async with session:
            log("✅ Session connected!")
            first_event_received = False

            async for event in session:
                if stop_requested():
                    log("🛑 Stop requested. Closing session...")
                    break
                try:
                    if not first_event_received:
                        first_event_received = True
                        session_connected.set()
                        log("=" * 50)
                        log("🎙️ Voice Assistant Ready!")
                        log("💬 Speak clearly into your microphone")
                        log("⏸️  Press Stop to end")
                        log("=" * 50)

                    if event.type == "agent_start":
                        log("👂 Listening...")
                        receiving_audio = False
                        audio_chunks_received = 0
                        total_audio_bytes = 0

                    elif event.type == "agent_end":
                        if audio_chunks_received > 0:
                            log(
                                f"✅ Response completed ({audio_chunks_received} chunks, {total_audio_bytes / 1024:.1f}KB)"
                            )
                        receiving_audio = False

                    elif event.type == "audio":
                        if hasattr(event, "audio") and hasattr(event.audio, "data"):
                            audio_data = event.audio.data
                            if audio_data:
                                if not receiving_audio:
                                    receiving_audio = True
                                    log("🔊 Speaking...")
                                    audio_handler.clear_audio_buffer()

                                audio_chunks_received += 1
                                total_audio_bytes += len(audio_data)
                                audio_handler.add_audio_to_buffer(audio_data)

                    elif event.type == "audio_end":
                        receiving_audio = False

                    elif event.type == "audio_interrupted":
                        log("⚠️ Interrupted")
                        audio_handler.clear_audio_buffer()
                        receiving_audio = False

                    elif event.type == "error":
                        log(f"❌ Error: {event.error}")

                except Exception as exc:  # noqa: BLE001
                    log(f"Error processing event: {exc}")
                    import traceback

                    traceback.print_exc()

    except KeyboardInterrupt:
        log("👋 Shutting down...")

    finally:
        session_connected.set()
        send_task.cancel()
        monitor_task.cancel()
        try:
            await send_task
            await monitor_task
        except asyncio.CancelledError:
            pass
        audio_handler.stop()
        if not (stop_event and isinstance(stop_event, threading.Event) and stop_event.is_set()):
            log("Session ended")
