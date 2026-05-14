# Voice Studio

A local developer tool for exploring [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) text-to-speech capabilities. Generate speech with preset voices, clone voices from short audio clips, or design entirely new voices from text descriptions — all running locally on your machine.

## Features

**Three TTS modes:**

- **Custom Voice** — Pick from 9 preset speakers (Vivian, Serena, Ryan, Aiden, etc.) and control delivery style with natural language instructions like "speak warmly and slowly"
- **Voice Clone** — Upload a 3-10 second audio clip and clone that voice to speak any text in any of the 10 supported languages
- **Voice Design** — Describe a voice in plain text ("a calm, deep male voice with a British accent") and the model generates it from scratch

**10 languages:** Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian

**Built for Apple Silicon:** Optimized for MPS (Metal Performance Shaders) with appropriate dtype settings per model variant. Also works on CPU as a fallback.

## Requirements

- Python 3.12+
- macOS with Apple Silicon (M1/M2/M3/M4) recommended
- ~4GB disk per model variant (downloaded automatically on first use)

## Install

```bash
git clone https://github.com/pengyaoc/voice-studio.git
cd voice-studio

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Open **http://127.0.0.1:8000** in your browser.

The first time you generate speech in each mode, the corresponding model (~4GB) will download from HuggingFace. A status banner in the UI shows download progress. Subsequent runs load from cache.

## How It Works

A single FastAPI process serves both the backend API and the frontend UI. Models are lazy-loaded on first use — the server starts instantly and only downloads/loads a model when you actually need it.

```
voice_studio/
├── main.py              # FastAPI entry point
├── backend/
│   ├── models.py        # Lazy model loading with status tracking
│   ├── tts.py           # Generation logic for all 3 modes
│   ├── routes.py        # API endpoints
│   └── audio_utils.py   # WAV file management
└── frontend/
    ├── index.html       # Single-page app
    ├── style.css        # Dark theme styles
    └── app.js           # UI logic
```

## Model Details

| Mode | Model | Size | Dtype on MPS |
|------|-------|------|-------------|
| Custom Voice | Qwen3-TTS-12Hz-1.7B-CustomVoice | ~4GB | float16 |
| Voice Clone | Qwen3-TTS-12Hz-1.7B-Base | ~4GB | float32 |
| Voice Design | Qwen3-TTS-12Hz-1.7B-VoiceDesign | ~4GB | float16 |

Voice cloning requires float32 on MPS — float16 causes runtime errors on Apple Silicon for this variant.

## License

MIT
