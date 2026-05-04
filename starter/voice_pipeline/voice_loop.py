"""Ex8 — voice loop (reference solution).

Two modes:
  * text mode: stdin → manager → stdout. Free, no mic needed.
  * voice mode: mic → Speechmatics realtime STT → manager →
    Rime.ai Arcana TTS → speakers.

Both modes write identical trace events so downstream grading
doesn't care which ran.

Voice mode degrades gracefully:
  - No SPEECHMATICS_KEY        → text mode with warning
  - No RIME_API_KEY            → voice STT, but manager replies printed not spoken
  - speechmatics-python missing → text mode with install hint
  - No mic / no playback       → attempted run; errors surface clearly
"""

from __future__ import annotations

import asyncio
import os
import sys
import wave

from sovereign_agent.session.directory import Session
from sovereign_agent.session.state import now_utc

from starter.voice_pipeline.manager_persona import ManagerPersona

# Audio config — matches Speechmatics' default expectations
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
# Voice mode — real Speechmatics STT + Rime Arcana TTS
# ---------------------------------------------------------------------------
async def run_voice_mode(session: Session, persona: ManagerPersona, max_turns: int = 6) -> None:
    """Voice mode. Real mic capture → Speechmatics STT → manager → Rime TTS."""

    # ── preflight: keys + deps ─────────────────────────────────────
    speechmatics_key = os.environ.get("SPEECHMATICS_KEY", "").strip()
    rime_key = os.environ.get("RIME_API_KEY", "").strip()

    if not speechmatics_key:
        print(
            "⚠  SPEECHMATICS_KEY not set — falling back to text mode.\n"
            "   Add to .env and re-run for real voice.",
            file=sys.stderr,
        )
        await run_text_mode(session, persona, max_turns=max_turns)
        return

    try:
        import sounddevice as sd  # type: ignore[import-not-found]
        import speechmatics  # type: ignore[import-not-found]  # noqa: F401
        from speechmatics.client import WebsocketClient  # type: ignore[import-not-found]
        from speechmatics.models import (  # type: ignore[import-not-found]
            AudioSettings,
            ConnectionSettings,
            ServerMessageType,
            TranscriptionConfig,
        )
    except ImportError as e:
        print(
            f"⚠  Missing voice dep: {e.name}. Run 'make setup' with voice extra:\n"
            "     uv sync --extra voice\n"
            "   Falling back to text mode.",
            file=sys.stderr,
        )
        await run_text_mode(session, persona, max_turns=max_turns)
        return

    # Rime is optional — we fall through to text-reply-only if missing
    rime_enabled = bool(rime_key)
    if not rime_enabled:
        print(
            "ℹ  RIME_API_KEY not set — manager replies will be printed, not spoken.",
            file=sys.stderr,
        )

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
            print(
                "   macOS? Check System Settings → Privacy & Security → Microphone\n"
                "   and grant your terminal app access, then restart the terminal.",
                file=sys.stderr,
            )
            return

        if not audio_bytes:
            print("   (silence detected; ending conversation)")
            break

        # ── transcribe via Speechmatics ────────────────────────────
        try:
            user_text = await _transcribe_speechmatics(
                audio_bytes,
                speechmatics_key,
                AudioSettings,
                ConnectionSettings,
                ServerMessageType,
                TranscriptionConfig,
                WebsocketClient,
            )
        except Exception as e:  # noqa: BLE001
            print(f"✗ STT failed: {e}", file=sys.stderr)
            print(
                "   Check SPEECHMATICS_KEY (make educator-diagnostics).\n"
                "   Free-tier has a monthly cap; 403 usually means exhausted.",
                file=sys.stderr,
            )
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

        # ── speak reply via Rime TTS (if enabled) ──────────────────
        if rime_enabled:
            try:
                await _speak_rime(manager_text, rime_key, sd)
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

    Uses a simple RMS threshold — fine for quiet rooms, may need bumping
    in noisy ones. Writes the captured audio to session/workspace/turn_<N>.wav
    for debugging.
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

            # RMS amplitude (crude VAD)
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

            # End conditions
            if speech_started and silence_chunks >= silence_chunks_needed:
                break
            if total_ms >= MAX_UTTERANCE_S * 1000:
                break
            # Grace: if no speech in first 3s, exit with empty
            if not speech_started and total_ms >= 3000:
                return b""

    audio_bytes = b"".join(captured)

    # Save for debugging
    wav_path = session.workspace_dir / f"turn_{turn}_input.wav"
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_bytes)

    return audio_bytes


# ---------------------------------------------------------------------------
# Speechmatics realtime STT
# ---------------------------------------------------------------------------
async def _transcribe_speechmatics(
    audio_bytes: bytes,
    api_key: str,
    AudioSettings,  # noqa: N803 — class passed as arg to avoid top-level import
    ConnectionSettings,  # noqa: N803
    ServerMessageType,  # noqa: N803
    TranscriptionConfig,  # noqa: N803
    WebsocketClient,  # noqa: N803
) -> str:
    """Send PCM bytes to Speechmatics realtime API, collect final transcripts.

    Uses the batch-via-realtime pattern: one connection, push all bytes,
    await final results. Simpler than true streaming for this use case.
    """
    import io

    transcripts: list[str] = []

    def _on_final(message: dict) -> None:
        for result in message.get("results", []):
            for alt in result.get("alternatives", []):
                content = alt.get("content")
                if content:
                    transcripts.append(content)

    conn_settings = ConnectionSettings(
        url="wss://eu2.rt.speechmatics.com/v2",
        auth_token=api_key,
    )
    audio_settings = AudioSettings(
        encoding="pcm_s16le",
        sample_rate=SAMPLE_RATE,
    )
    trans_config = TranscriptionConfig(
        language="en",
        enable_partials=False,
        max_delay=1.5,
    )

    client = WebsocketClient(conn_settings)
    client.add_event_handler(ServerMessageType.AddTranscript, _on_final)

    # Speechmatics client is sync; run in executor
    stream = io.BytesIO(audio_bytes)

    def _blocking_run():
        client.run_synchronously(stream, trans_config, audio_settings)

    await asyncio.get_event_loop().run_in_executor(None, _blocking_run)

    return " ".join(transcripts).strip()


# ---------------------------------------------------------------------------
# Rime.ai Arcana TTS + playback
# ---------------------------------------------------------------------------
async def _speak_rime(text: str, api_key: str, sd) -> None:
    """Call Rime.ai TTS, get MP3 back, play it."""
    import httpx
    
    url = "https://users.rime.ai/v1/rime-tts"
    payload = {
        "speaker": "luna",  # an Arcana voice; change if Rime renames
        "text": text,
        "modelId": "arcana",
        "audioFormat": "mp3",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "audio/mp3",
    }

    # TODO: Make an async HTTP POST request using `httpx.AsyncClient` to `url` with `payload` as JSON and `headers`.
    # Check for status_code == 200, and raise RuntimeError with the response text if it fails.
    # Assign the raw bytes to `mp3_bytes`.
    raise NotImplementedError("TODO: Implement async HTTP POST for Rime TTS")
    
    # mp3_bytes = <your variable>

    # Decode MP3 → PCM via pydub (stdlib can't handle mp3)
    try:
        from io import BytesIO

        from pydub import AudioSegment  # type: ignore[import-not-found]
    except ImportError:
        print(
            "   (pydub not installed; can't decode mp3 for playback — "
            "install with: uv sync --extra voice)",
            file=sys.stderr,
        )
        return

    segment = AudioSegment.from_file(BytesIO(mp3_bytes), format="mp3")
    # Resample + convert to int16 mono for sounddevice
    segment = segment.set_frame_rate(SAMPLE_RATE).set_channels(1).set_sample_width(2)

    import numpy as np

    samples = np.array(segment.get_array_of_samples(), dtype=np.int16)
    sd.play(samples, samplerate=SAMPLE_RATE)
    sd.wait()


__all__ = ["run_text_mode", "run_voice_mode"]
