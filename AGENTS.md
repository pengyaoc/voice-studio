# AGENTS.md

This repository does not currently include a `CLAUDE.md`. The guidance below is derived from `.claude/settings.local.json`, `README.md`, and the current application code.

## Project Summary

Voice Studio is a local FastAPI app for experimenting with Qwen3-TTS. One Python process serves both the API and the static frontend.

- Entry point: `main.py`
- Backend: `backend/`
- Frontend: `frontend/`
- Generated audio: `audio_output/`
- Uploaded voice references: `voice_clips/`

## Local Setup

Use Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Open `http://127.0.0.1:8000`.

## Runtime Notes

- The server creates `audio_output/` and `voice_clips/` at startup if they do not exist.
- Models are loaded lazily on first use.
- First use of a model variant downloads large HuggingFace assets, roughly 4 GB per variant.
- Apple Silicon with MPS is the primary target; CPU fallback is supported.
- Voice cloning on MPS requires `float32`.

## API Surface

- `GET /api/voices`
- `GET /api/model-status`
- `POST /api/tts/custom-voice`
- `POST /api/tts/voice-clone`
- `POST /api/tts/voice-design`

## Agent Guidance

- Preserve the single-process architecture: FastAPI serves both API routes and the frontend.
- Keep model loading lazy unless there is a strong reason to change startup behavior.
- Treat generated files in `audio_output/` and uploaded samples in `voice_clips/` as runtime artifacts, not source files.
- When changing model behavior, verify the Apple Silicon path and CPU fallback both still make sense.
- When changing the frontend, keep it compatible with the existing static-file mount from `main.py`.

## Current Claude Config

`.claude/settings.local.json` currently allows:

- `WebSearch`
- `WebFetch(domain:github.com)`
- `WebFetch(domain:mybyways.com)`
