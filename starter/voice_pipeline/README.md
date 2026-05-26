# Ex8 — Voice pipeline

**You are building:** a conversational interface to a Llama-3.3-70B pub manager
persona, with real voice (Local Whisper STT + Local Piper TTS) or text-only
fallback.

**Spec:** see `ASSIGNMENT.md` §Ex8.

**Time estimate:** 3-6 hours (voice mode is the wildcard).

## Modes

- **Text mode** (`--text`, default): stdin/stdout. Zero extra setup. Full
  credit for this mode alone is 16/20.
- **Voice mode** (`--voice`): real audio via fully offline local models (Whisper & Piper).
  No `.env` keys required for voice anymore. The models will be downloaded on first run.

## Files

| File | What it is | Your job |
|---|---|---|
| `manager_persona.py` | Llama-3.3-70B pub-manager persona | Write the system prompt; wire the LLM client |
| `voice_loop.py` | STT → LLM → TTS loop | Local voice mode implementation using Whisper and Piper |
| `requirements-voice.txt` | Optional voice dep pins | — |

## How to run

First, ensure you have the necessary system-level and python dependencies for voice playback and capture:

**Ubuntu/Debian:**
```bash
sudo apt-get install -y portaudio19-dev libasound2-plugins
uv sync --extra voice
```

**macOS:**
```bash
brew install portaudio
uv sync --extra voice
```
*(Also ensure your terminal app has Microphone access in System Settings).*

Then, you can run the modes using:

```bash
make ex8-text        # text mode
make ex8-voice       # voice mode; fully offline local execution
```

**Note:** On the first run, the local models (e.g., Piper voice `.onnx`) might be downloaded, which could take a moment.

## Grading shape

Four evaluation dimensions:

1. **Conversation length & coherence** — at least 3 turns, the manager stays
   in character. Scored by an LLM-as-judge.
2. **Trace correctness** — every utterance appears as `voice.utterance_in` or
   `voice.utterance_out` in `logs/trace.jsonl`.
3. **Graceful degradation** — `--voice` with missing dependencies falls back with a clear
   warning, never crashes.
4. **Voice mode works end-to-end** — BONUS. You can get full marks without
   this if voice setup is impossible on your machine (e.g. no microphone).
