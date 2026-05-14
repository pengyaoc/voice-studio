# Voice Studio — Qwen3-TTS Developer Prototype

## Problem Statement

Build a local developer prototype for exploring Qwen3-TTS text-to-speech capabilities on an M2 Max MacBook Pro. The tool should support all three model variants (CustomVoice, Voice Clone, VoiceDesign) with a browser-based UI for generating, playing, and downloading audio.

## Goals

- Expose all three Qwen3-TTS model variants through a single UI
- Optimize for M2 Max (MPS backend, appropriate dtypes)
- Simple single-command startup
- Clear feedback during model download and loading
- Play and download generated audio in the browser

## Non-Goals

- Production deployment or multi-user support
- Audio streaming during generation
- Persistent history across sessions
- MLX optimization (can be explored later)
- Docker/container support

## Architecture

### Monolithic Python App

Single FastAPI process serves both the API and static frontend files.

```
voice_studio/
├── main.py                  # FastAPI entry point, static file mount
├── requirements.txt         # Python dependencies
├── backend/
│   ├── __init__.py
│   ├── models.py            # Model loading & management (lazy-load per variant)
│   ├── tts.py               # TTS generation logic for all 3 modes
│   ├── routes.py            # API endpoints
│   └── audio_utils.py       # Audio file management
├── frontend/
│   ├── index.html           # Single-page app
│   ├── style.css            # Tailwind CDN + custom styles
│   └── app.js               # All UI logic
├── audio_output/            # Generated audio files (gitignored)
└── voice_clips/             # Uploaded reference clips (gitignored)
```

### Tech Stack

- **Backend:** Python 3.12, FastAPI, `qwen-tts` package, PyTorch with MPS backend
- **Frontend:** Vanilla HTML/JS, Tailwind CSS (CDN), no build step
- **Audio:** WAV format (native model output), served via FastAPI static files

## Model Variants & Inputs

### Qwen3-TTS-12Hz-1.7B-CustomVoice

- **Function:** `generate_custom_voice()`
- **Inputs:** `text`, `language`, `speaker`, `instruct` (optional style instruction)
- **Speaker presets (9):** Vivian, Serena, Uncle_Fu, Dylan, Eric, Ryan, Aiden, Ono_Anna, Sohee
- **`instruct` controls:** Delivery style — "speak warmly", "read with excitement"
- **Languages:** Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian

### Qwen3-TTS-12Hz-1.7B-Base (Voice Clone)

- **Function:** `generate_voice_clone()`
- **Inputs:** `text`, `language`, `ref_audio`, `ref_text`
- **No style control** — voice identity comes entirely from the reference clip
- **Reference audio:** 3-10 seconds recommended, accepts WAV/MP3/M4A
- **`ref_text`:** Must match reference audio exactly for best results

### Qwen3-TTS-12Hz-1.7B-VoiceDesign

- **Function:** `generate_voice_design()`
- **Inputs:** `text`, `language`, `instruct` (required voice description)
- **`instruct` defines:** Voice identity from scratch — pitch, timbre, accent, personality
- **Example:** "A calm, deep male voice with a slight British accent"

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/tts/custom-voice` | POST | Generate with preset speaker + style instruction |
| `/api/tts/voice-clone` | POST | Generate with uploaded reference audio |
| `/api/tts/voice-design` | POST | Generate with text voice description |
| `/api/voices` | GET | List available preset speakers |
| `/api/model-status` | GET | Check model loading/download status |
| `/api/audio/{filename}` | GET | Serve generated audio files |
| `/api/upload-clip` | POST | Upload a reference voice clip |

## Frontend UI

### Layout

- **Header:** "Voice Studio" title + model/device info badge
- **Tab bar:** Custom Voice | Voice Clone | Voice Design
- **Two-column split:**
  - Left: Input panel (fields vary per tab)
  - Right: Audio player + download button + generation history

### Tab Fields

**Custom Voice:**
- Speaker dropdown (9 presets)
- Language dropdown (10 languages)
- Style Instruction textarea (optional)
- Text to Speak textarea

**Voice Clone:**
- Reference audio file upload (drag-and-drop)
- Reference transcript textarea
- Language dropdown
- Text to Speak textarea

**Voice Design:**
- Voice Description textarea (required)
- Language dropdown
- Text to Speak textarea

### Output Panel (shared across tabs)

- Audio player with play/pause, progress bar, duration
- Download WAV button
- Copy file path button
- History list: text snippet, mode, speaker/voice info, duration, click to replay

## Model Loading & Performance

### M2 Max Optimization

- **Device:** `mps` (Metal Performance Shaders)
- **Dtype:** `torch.float32` for Base model (voice cloning requires it on MPS), `torch.float16` for CustomVoice and VoiceDesign
- **No FlashAttention** — not supported on MPS
- **Default attention implementation**

### Loading Strategy

- **Lazy loading:** Models loaded on first use per tab, cached in memory
- **No models loaded at startup** — FastAPI starts instantly
- **HuggingFace caching:** Models download to `~/.cache/huggingface/` on first use (~3-4GB per variant)

### Download/Loading UX

- First generation request triggers download if model not cached
- `/api/model-status` endpoint returns status: `{"status": "loading", "message": "Downloading Qwen3-TTS-12Hz-1.7B-CustomVoice (3.2GB)..."}`
- Frontend polls `/api/model-status` every 2 seconds during loading
- Generate button shows progress indicator with descriptive message
- Clear distinction between "Downloading model (first time only)..." and "Loading model into memory..."
- Button disabled during loading to prevent double-trigger

## Generation Flow

1. User fills in fields, clicks "Generate Speech"
2. Button shows spinner + "Generating..."
3. Frontend POSTs to `/api/tts/{mode}` with form data (+ file upload for voice clone)
4. Backend checks if model is loaded → if not, returns loading status, frontend polls `/api/model-status`
5. Model ready → backend runs inference, saves WAV to `audio_output/`, returns filename + metadata
6. Frontend loads audio player with new file, adds entry to history list

## Error Handling

- **Model not downloaded:** Show download progress message
- **Empty required fields:** Frontend validation, disable button until filled
- **Wrong audio format:** Backend returns error, frontend shows inline
- **Generation failure (OOM/model error):** Backend catches exception, returns error message, frontend shows red banner
- **No MPS available:** Backend falls back to CPU with warning in UI

## History

- In-memory only (JavaScript array), clears on page refresh
- Each entry: text snippet, mode, speaker/voice info, duration, audio file path
- Click to replay any previous generation

## Success Criteria

- Single `python main.py` starts the full app
- All three TTS modes generate audio successfully
- Audio plays in browser and downloads as WAV
- Voice cloning works with uploaded audio clips
- Model download progress is clearly communicated
- Responsive on M2 Max with MPS acceleration
