"""Ex8 — voice loop (local solution).

Two modes:
  * text mode: stdin → manager → stdout. Free, no mic needed.
  * voice mode: mic → local Whisper STT → manager → local Piper TTS → speakers.

Both modes write identical trace events so downstream grading
doesn't care which ran.
"""

from __future__ import annotations

import asyncio
import os
import sys
import wave

from sovereign_agent.session.directory import Session
from sovereign_agent.session.state import now_utc

from starter.voice_pipeline.manager_persona import ManagerPersona

# Audio config
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM
MAX_UTTERANCE_S = 15.0  # cap per-turn recording
SILENCE_TIMEOUT_S = 2.0  # consecutive silence to end an utterance


# ---------------------------------------------------------------------------
# Text mode — reference implementation (read this first)
# ---------------------------------------------------------------------------
async def run_text_mode(session: Session, persona: ManagerPersona, max_turns: int = 6) -> None:
    """Conversation via stdin/stdout. Same trace-event shape as voice mode."""
    print("Text mode. Type a message to Alasdair (pub manager); blank line to quit.")
    print(f"Session: {session.session_id}")
    print("-" * 60)

    for turn_idx in range(max_turns):
        try:
            user_text = input("you> ").strip()
        except EOFError:
            break
        if not user_text:
            break

        session.append_trace_event(
            {
                "event_type": "voice.utterance_in",
                "actor": "user",
                "timestamp": now_utc().isoformat(),
                "payload": {"text": user_text, "turn": turn_idx, "mode": "text"},
            }
        )

        manager_text = await persona.respond(user_text)
        print(f"alasdair> {manager_text}")

        session.append_trace_event(
            {
                "event_type": "voice.utterance_out",
                "actor": "manager",
                "timestamp": now_utc().isoformat(),
                "payload": {"text": manager_text, "turn": turn_idx, "mode": "text"},
            }
        )

    print("-" * 60)
    print(f"Conversation ended. Trace: {session.trace_path}")


# ---------------------------------------------------------------------------
# Voice mode — Local Whisper STT + Piper TTS
# ---------------------------------------------------------------------------
async def run_voice_mode(session: Session, persona: ManagerPersona, max_turns: int = 6) -> None:
    """Voice mode. Real mic capture → Whisper STT → manager → Piper TTS."""

    # ── preflight: deps ────────────────────────────────────────────
    try:
        import numpy as np
        import sounddevice as sd  # type: ignore[import-not-found]
        import whisper  # type: ignore[import-not-found]
        from piper.voice import PiperVoice  # type: ignore[import-not-found]
    except ImportError as e:
        print(
            f"⚠  Missing voice dep: {e.name}. Run 'make setup' with voice extra:\n"
            "     uv sync --extra voice\n"
            "   Falling back to text mode.",
            file=sys.stderr,
        )
        await run_text_mode(session, persona, max_turns=max_turns)
        return

    print("ℹ  Loading local models (this might take a moment)...")

    # Load Whisper
    try:
        whisper_model = whisper.load_model("base.en")
    except Exception as e:
        print(f"✗ Failed to load Whisper model: {e}", file=sys.stderr)
        await run_text_mode(session, persona, max_turns=max_turns)
        return

    # Load Piper
    piper_model_path = "en_US-lessac-medium.onnx"
    try:
        piper_voice = _load_piper_voice(piper_model_path, PiperVoice)
    except Exception as e:
        print(f"✗ Failed to load Piper model: {e}", file=sys.stderr)
        await run_text_mode(session, persona, max_turns=max_turns)
        return

    print(f"🎙️  Voice mode. Session: {session.session_id}")
    print(f"    Speak when prompted. Silence for {SILENCE_TIMEOUT_S}s ends a turn.")
    print(f"    Max utterance: {MAX_UTTERANCE_S}s. Say 'goodbye' to end.")
    print("-" * 60)

    for turn_idx in range(max_turns):
        print(f"\n[turn {turn_idx + 1}] 🎤 listening...")

        # ── capture audio ──────────────────────────────────────────
        try:
            audio_bytes = _record_until_silence(sd, session, turn_idx)
        except Exception as e:  # noqa: BLE001
            print(f"✗ mic capture failed: {e}", file=sys.stderr)
            return

        if not audio_bytes:
            print("   (silence detected; ending conversation)")
            break

        # ── transcribe via Whisper ────────────────────────────
        try:
            user_text = await _transcribe_whisper(audio_bytes, whisper_model, np)
        except Exception as e:  # noqa: BLE001
            print(f"✗ STT failed: {e}", file=sys.stderr)
            return

        user_text = user_text.strip()
        if not user_text:
            print("   (no transcript; ending conversation)")
            break

        print(f"   you> {user_text}")
        session.append_trace_event(
            {
                "event_type": "voice.utterance_in",
                "actor": "user",
                "timestamp": now_utc().isoformat(),
                "payload": {"text": user_text, "turn": turn_idx, "mode": "voice"},
            }
        )

        if user_text.lower().strip(".!?") in ("goodbye", "bye", "cheerio"):
            break

        # ── get manager reply ──────────────────────────────────────
        manager_text = await persona.respond(user_text)
        print(f"   alasdair> {manager_text}")

        session.append_trace_event(
            {
                "event_type": "voice.utterance_out",
                "actor": "manager",
                "timestamp": now_utc().isoformat(),
                "payload": {"text": manager_text, "turn": turn_idx, "mode": "voice"},
            }
        )

        # ── speak reply via Piper TTS ──────────────────────────────
        try:
            await _speak_piper(manager_text, piper_voice, sd, np)
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠ TTS playback failed: {e} (continuing)", file=sys.stderr)

    print("-" * 60)
    print(f"Conversation ended. Trace: {session.trace_path}")


# ---------------------------------------------------------------------------
# Audio capture
# ---------------------------------------------------------------------------
def _record_until_silence(sd, session: Session, turn: int) -> bytes:
    """Record from the default mic until SILENCE_TIMEOUT_S of silence or
    MAX_UTTERANCE_S hit. Returns raw 16-bit PCM @ SAMPLE_RATE mono.
    """
    import numpy as np

    threshold = 500  # int16 RMS amplitude below which we call it silence
    chunk_ms = 100
    chunk_samples = int(SAMPLE_RATE * chunk_ms / 1000)
    silence_chunks_needed = int(SILENCE_TIMEOUT_S * 1000 / chunk_ms)

    captured: list[bytes] = []
    silence_chunks = 0
    total_ms = 0
    speech_started = False

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
        while True:
            data, _overflow = stream.read(chunk_samples)
            if hasattr(data, "tobytes"):
                raw = data.tobytes()
            else:
                raw = bytes(data)
            captured.append(raw)
            total_ms += chunk_ms

            arr = np.frombuffer(raw, dtype=np.int16)
            if arr.size == 0:
                rms = 0
            else:
                rms = int(np.sqrt(np.mean(arr.astype(np.float64) ** 2)))

            if rms >= threshold:
                speech_started = True
                silence_chunks = 0
            else:
                silence_chunks += 1

            if speech_started and silence_chunks >= silence_chunks_needed:
                break
            if total_ms >= MAX_UTTERANCE_S * 1000:
                break
            if not speech_started and total_ms >= 3000:
                return b""

    audio_bytes = b"".join(captured)

    wav_path = session.workspace_dir / f"turn_{turn}_input.wav"
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_bytes)

    return audio_bytes


# ---------------------------------------------------------------------------
# Local Whisper STT
# ---------------------------------------------------------------------------
async def _transcribe_whisper(audio_bytes: bytes, whisper_model, np) -> str:
    """Send PCM bytes to local Whisper model, collect transcript."""
    # Convert 16-bit PCM bytes to float32 NumPy array normalized between -1.0 and 1.0
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    def _blocking_run():
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Using fp16=False for compatibility with CPUs
            result = whisper_model.transcribe(audio_np, fp16=False)
        return result["text"]

    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, _blocking_run)

    return text.strip()


# ---------------------------------------------------------------------------
# Local Piper TTS
# ---------------------------------------------------------------------------
def _load_piper_voice(model_path: str, piper_voice_class):
    """Download and load Piper model."""
    import urllib.request

    if not os.path.exists(model_path):
        print(f"ℹ  Downloading Piper model to {model_path}...")
        url_model = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        url_json = url_model + ".json"
        urllib.request.urlretrieve(url_model, model_path)
        urllib.request.urlretrieve(url_json, model_path + ".json")

    return piper_voice_class.load(model_path)


async def _speak_piper(text: str, piper_voice, sd, np) -> None:
    """Call Piper TTS to generate audio and play it."""
    import io

    def _blocking_run():
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as w:
            piper_voice.synthesize_wav(text, w)
        return wav_io.getvalue()

    loop = asyncio.get_running_loop()
    wav_bytes = await loop.run_in_executor(None, _blocking_run)

    # Read wave bytes
    wav_io = io.BytesIO(wav_bytes)
    with wave.open(wav_io, "rb") as w:
        frames = w.readframes(w.getnframes())
        rate = w.getframerate()
        channels = w.getnchannels()

    audio_data = np.frombuffer(frames, dtype=np.int16)

    if channels > 1:
        audio_data = audio_data.reshape(-1, channels)

    def _play_audio():
        sd.play(audio_data, samplerate=rate)
        sd.wait()

    await loop.run_in_executor(None, _play_audio)


__all__ = ["run_text_mode", "run_voice_mode"]
