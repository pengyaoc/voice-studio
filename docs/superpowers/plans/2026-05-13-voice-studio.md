# Voice Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Qwen3-TTS developer prototype with a FastAPI backend and vanilla HTML/JS frontend, supporting all three model variants (CustomVoice, Voice Clone, VoiceDesign) optimized for M2 Max.

**Architecture:** Monolithic Python app — FastAPI serves both the TTS API and static frontend files. Models lazy-load on first use via the `qwen-tts` package with PyTorch MPS backend. Frontend is a single-page app with Tailwind CSS (CDN).

**Tech Stack:** Python 3.12, FastAPI, qwen-tts, PyTorch (MPS), soundfile, vanilla HTML/JS, Tailwind CSS

---

## File Structure

```
voice_studio/
├── main.py                     # FastAPI app entry point, mounts routes + static files
├── requirements.txt            # Python dependencies
├── .gitignore                  # Ignore audio_output/, voice_clips/, __pycache__, .venv
├── backend/
│   ├── __init__.py             # Empty
│   ├── models.py               # ModelManager class: lazy-load, cache, status tracking
│   ├── tts.py                  # TTS generation functions for all 3 modes
│   ├── routes.py               # FastAPI router with all API endpoints
│   └── audio_utils.py          # Save WAV, generate filenames, manage audio_output/
├── frontend/
│   ├── index.html              # Single-page app shell, tabs, layout
│   ├── style.css               # Custom styles on top of Tailwind CDN
│   └── app.js                  # Tab switching, API calls, audio player, history
├── audio_output/               # Generated WAV files (gitignored)
└── voice_clips/                # Uploaded reference clips (gitignored)
```

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `main.py`
- Create: `backend/__init__.py`
- Create: `frontend/index.html` (minimal placeholder)
- Create: `audio_output/.gitkeep`
- Create: `voice_clips/.gitkeep`

- [ ] **Step 1: Create conda environment and requirements.txt**

```bash
conda create -n voice_studio python=3.12 -y
conda activate voice_studio
```

Create `requirements.txt`:

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
python-multipart==0.0.20
qwen-tts>=0.3.0
soundfile>=0.13.1
torch>=2.6.0
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: All packages install successfully. `qwen-tts` pulls in transformers, tokenizers, etc.

- [ ] **Step 3: Create .gitignore**

```
audio_output/*.wav
voice_clips/*
!voice_clips/.gitkeep
!audio_output/.gitkeep
__pycache__/
*.pyc
.venv/
.env
.superpowers/
```

- [ ] **Step 4: Create minimal main.py**

```python
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.routes import router

app = FastAPI(title="Voice Studio")

os.makedirs("audio_output", exist_ok=True)
os.makedirs("voice_clips", exist_ok=True)

app.include_router(router, prefix="/api")
app.mount("/audio", StaticFiles(directory="audio_output"), name="audio")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 5: Create backend/__init__.py**

Empty file.

- [ ] **Step 6: Create placeholder backend/routes.py**

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Create placeholder frontend/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Studio</title>
</head>
<body>
    <h1>Voice Studio</h1>
    <p>Loading...</p>
</body>
</html>
```

- [ ] **Step 8: Create .gitkeep files**

```bash
mkdir -p audio_output voice_clips
touch audio_output/.gitkeep voice_clips/.gitkeep
```

- [ ] **Step 9: Verify the app starts**

```bash
python main.py
```

Expected: Server starts on `http://127.0.0.1:8000`, shows "Voice Studio / Loading..." in browser. `http://127.0.0.1:8000/api/health` returns `{"status": "ok"}`.

- [ ] **Step 10: Initialize git and commit**

```bash
git init
git add -A
git commit -m "chore: scaffold voice studio project with FastAPI + static frontend"
```

---

### Task 2: Model Manager (Lazy Loading with Status Tracking)

**Files:**
- Create: `backend/models.py`

- [ ] **Step 1: Create backend/models.py with ModelManager class**

```python
import threading
import torch
from enum import Enum


class ModelVariant(str, Enum):
    CUSTOM_VOICE = "custom_voice"
    VOICE_CLONE = "voice_clone"
    VOICE_DESIGN = "voice_design"


MODEL_IDS = {
    ModelVariant.CUSTOM_VOICE: "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    ModelVariant.VOICE_CLONE: "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    ModelVariant.VOICE_DESIGN: "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
}

DTYPES = {
    ModelVariant.CUSTOM_VOICE: torch.float16,
    ModelVariant.VOICE_CLONE: torch.float32,
    ModelVariant.VOICE_DESIGN: torch.float16,
}


class ModelManager:
    def __init__(self):
        self._models: dict = {}
        self._status: dict[str, dict] = {}
        self._locks: dict[str, threading.Lock] = {
            v.value: threading.Lock() for v in ModelVariant
        }

    def get_status(self, variant: ModelVariant) -> dict:
        return self._status.get(variant.value, {"status": "not_loaded"})

    def get_model(self, variant: ModelVariant):
        if variant.value in self._models:
            return self._models[variant.value]
        return None

    def load_model(self, variant: ModelVariant):
        lock = self._locks[variant.value]
        if not lock.acquire(blocking=False):
            return

        try:
            if variant.value in self._models:
                return

            model_id = MODEL_IDS[variant]
            dtype = DTYPES[variant]

            device = "mps" if torch.backends.mps.is_available() else "cpu"
            device_label = "MPS (Apple Silicon)" if device == "mps" else "CPU (fallback)"

            self._status[variant.value] = {
                "status": "loading",
                "message": f"Downloading and loading {model_id}... This may take a few minutes on first run.",
                "device": device_label,
            }

            from qwen_tts import Qwen3TTSModel

            model = Qwen3TTSModel.from_pretrained(
                model_id,
                device_map=device,
                dtype=dtype,
            )

            self._models[variant.value] = model
            self._status[variant.value] = {
                "status": "ready",
                "message": f"{model_id} loaded on {device_label}",
                "device": device_label,
            }
        except Exception as e:
            self._status[variant.value] = {
                "status": "error",
                "message": f"Failed to load model: {str(e)}",
            }
        finally:
            lock.release()


model_manager = ModelManager()
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from backend.models import model_manager, ModelVariant; print('OK')"
```

Expected: Prints `OK` without errors.

- [ ] **Step 3: Commit**

```bash
git add backend/models.py
git commit -m "feat: add ModelManager with lazy loading and status tracking for all 3 variants"
```

---

### Task 3: Audio Utilities

**Files:**
- Create: `backend/audio_utils.py`

- [ ] **Step 1: Create backend/audio_utils.py**

```python
import os
import uuid
import soundfile as sf
import numpy as np


AUDIO_OUTPUT_DIR = "audio_output"


def save_wav(audio_data: np.ndarray, sample_rate: int) -> str:
    filename = f"{uuid.uuid4().hex[:12]}.wav"
    filepath = os.path.join(AUDIO_OUTPUT_DIR, filename)
    sf.write(filepath, audio_data, sample_rate)
    return filename


def get_audio_duration(filepath: str) -> float:
    info = sf.info(filepath)
    return round(info.duration, 2)
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from backend.audio_utils import save_wav, get_audio_duration; print('OK')"
```

Expected: Prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add backend/audio_utils.py
git commit -m "feat: add audio utility functions for saving WAV and getting duration"
```

---

### Task 4: TTS Generation Logic

**Files:**
- Create: `backend/tts.py`

- [ ] **Step 1: Create backend/tts.py**

```python
import os
import threading
from backend.models import model_manager, ModelVariant
from backend.audio_utils import save_wav, get_audio_duration, AUDIO_OUTPUT_DIR


def _ensure_model_loaded(variant: ModelVariant) -> bool:
    model = model_manager.get_model(variant)
    if model is not None:
        return True

    status = model_manager.get_status(variant)
    if status["status"] == "loading":
        return False

    thread = threading.Thread(
        target=model_manager.load_model, args=(variant,), daemon=True
    )
    thread.start()
    return False


def generate_custom_voice(
    text: str, language: str, speaker: str, instruct: str | None = None
) -> dict:
    variant = ModelVariant.CUSTOM_VOICE
    if not _ensure_model_loaded(variant):
        return {"status": "loading", **model_manager.get_status(variant)}

    model = model_manager.get_model(variant)
    kwargs = {"text": text, "language": language, "speaker": speaker}
    if instruct:
        kwargs["instruct"] = instruct

    wavs, sr = model.generate_custom_voice(**kwargs)

    filename = save_wav(wavs[0], sr)
    duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, filename))

    return {
        "status": "done",
        "filename": filename,
        "duration": duration,
        "mode": "custom_voice",
        "speaker": speaker,
        "language": language,
    }


def generate_voice_clone(
    text: str, language: str, ref_audio_path: str, ref_text: str
) -> dict:
    variant = ModelVariant.VOICE_CLONE
    if not _ensure_model_loaded(variant):
        return {"status": "loading", **model_manager.get_status(variant)}

    model = model_manager.get_model(variant)

    wavs, sr = model.generate_voice_clone(
        text=text,
        language=language,
        ref_audio=ref_audio_path,
        ref_text=ref_text,
    )

    filename = save_wav(wavs[0], sr)
    duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, filename))

    return {
        "status": "done",
        "filename": filename,
        "duration": duration,
        "mode": "voice_clone",
        "language": language,
    }


def generate_voice_design(text: str, language: str, instruct: str) -> dict:
    variant = ModelVariant.VOICE_DESIGN
    if not _ensure_model_loaded(variant):
        return {"status": "loading", **model_manager.get_status(variant)}

    model = model_manager.get_model(variant)

    wavs, sr = model.generate_voice_design(
        text=text, language=language, instruct=instruct
    )

    filename = save_wav(wavs[0], sr)
    duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, filename))

    return {
        "status": "done",
        "filename": filename,
        "duration": duration,
        "mode": "voice_design",
        "language": language,
    }
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from backend.tts import generate_custom_voice, generate_voice_clone, generate_voice_design; print('OK')"
```

Expected: Prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add backend/tts.py
git commit -m "feat: add TTS generation functions for all 3 modes"
```

---

### Task 5: API Routes

**Files:**
- Modify: `backend/routes.py`

- [ ] **Step 1: Replace backend/routes.py with full API routes**

```python
import os
import shutil
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from backend.models import model_manager, ModelVariant
from backend.tts import generate_custom_voice, generate_voice_clone, generate_voice_design

router = APIRouter()

SPEAKERS = [
    {"id": "Vivian", "name": "Vivian", "language": "Chinese", "description": "Bright, edgy female"},
    {"id": "Serena", "name": "Serena", "language": "Chinese", "description": "Warm, gentle female"},
    {"id": "Uncle_Fu", "name": "Uncle Fu", "language": "Chinese", "description": "Low, mellow male"},
    {"id": "Dylan", "name": "Dylan", "language": "Chinese", "description": "Beijing dialect male"},
    {"id": "Eric", "name": "Eric", "language": "Chinese", "description": "Sichuan dialect male"},
    {"id": "Ryan", "name": "Ryan", "language": "English", "description": "Dynamic male"},
    {"id": "Aiden", "name": "Aiden", "language": "English", "description": "American male"},
    {"id": "Ono_Anna", "name": "Ono Anna", "language": "Japanese", "description": "Japanese female"},
    {"id": "Sohee", "name": "Sohee", "language": "Korean", "description": "Korean female"},
]

LANGUAGES = [
    "Chinese", "English", "Japanese", "Korean", "German",
    "French", "Russian", "Portuguese", "Spanish", "Italian",
]


@router.get("/voices")
async def list_voices():
    return {"speakers": SPEAKERS, "languages": LANGUAGES}


@router.get("/model-status")
async def model_status(variant: str = "custom_voice"):
    try:
        v = ModelVariant(variant)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown variant: {variant}")
    return model_manager.get_status(v)


@router.post("/tts/custom-voice")
async def tts_custom_voice(
    text: str = Form(...),
    language: str = Form(...),
    speaker: str = Form(...),
    instruct: str = Form(""),
):
    result = generate_custom_voice(
        text=text,
        language=language,
        speaker=speaker,
        instruct=instruct if instruct else None,
    )
    return result


@router.post("/tts/voice-clone")
async def tts_voice_clone(
    text: str = Form(...),
    language: str = Form(...),
    ref_text: str = Form(...),
    ref_audio: UploadFile = File(...),
):
    os.makedirs("voice_clips", exist_ok=True)
    clip_path = os.path.join("voice_clips", ref_audio.filename)
    with open(clip_path, "wb") as f:
        shutil.copyfileobj(ref_audio.file, f)

    result = generate_voice_clone(
        text=text,
        language=language,
        ref_audio_path=clip_path,
        ref_text=ref_text,
    )
    return result


@router.post("/tts/voice-design")
async def tts_voice_design(
    text: str = Form(...),
    language: str = Form(...),
    instruct: str = Form(...),
):
    result = generate_voice_design(
        text=text, language=language, instruct=instruct
    )
    return result
```

- [ ] **Step 2: Verify the app starts with all routes**

```bash
python main.py &
sleep 2
curl -s http://127.0.0.1:8000/api/voices | python -m json.tool
curl -s http://127.0.0.1:8000/api/model-status?variant=custom_voice | python -m json.tool
kill %1
```

Expected: `/api/voices` returns the speakers list and languages. `/api/model-status` returns `{"status": "not_loaded"}`.

- [ ] **Step 3: Commit**

```bash
git add backend/routes.py
git commit -m "feat: add all API routes for TTS generation, voices, and model status"
```

---

### Task 6: Frontend — HTML Shell & Layout

**Files:**
- Modify: `frontend/index.html`
- Create: `frontend/style.css`

- [ ] **Step 1: Create frontend/index.html with full layout**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Studio</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        bg: { primary: '#0f0f1a', secondary: '#1a1a2e', tertiary: '#2a2a3e' },
                        accent: '#7c8aff',
                        'accent-hover': '#6b78ee',
                    }
                }
            }
        }
    </script>
    <link rel="stylesheet" href="/style.css">
</head>
<body class="bg-bg-primary text-gray-200 min-h-screen font-sans">
    <!-- Header -->
    <header class="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <h1 class="text-xl font-bold text-white">Voice Studio</h1>
        <span class="text-xs text-gray-500" id="device-badge">Qwen3-TTS</span>
    </header>

    <!-- Tab Bar -->
    <nav class="flex border-b border-gray-800" id="tab-bar">
        <button class="tab-btn active" data-tab="custom-voice">Custom Voice</button>
        <button class="tab-btn" data-tab="voice-clone">Voice Clone</button>
        <button class="tab-btn" data-tab="voice-design">Voice Design</button>
    </nav>

    <!-- Main Content -->
    <main class="grid grid-cols-2 min-h-[calc(100vh-105px)]">
        <!-- Left: Input Panel -->
        <div class="p-6 border-r border-gray-800">
            <!-- Custom Voice Tab -->
            <div id="tab-custom-voice" class="tab-content">
                <div class="grid grid-cols-2 gap-3 mb-5">
                    <div>
                        <label class="field-label">Speaker</label>
                        <select id="cv-speaker" class="field-select">
                            <option value="">Loading...</option>
                        </select>
                    </div>
                    <div>
                        <label class="field-label">Language</label>
                        <select id="cv-language" class="field-select">
                            <option value="">Loading...</option>
                        </select>
                    </div>
                </div>
                <div class="mb-5">
                    <label class="field-label">Style Instruction <span class="text-gray-600">(optional)</span></label>
                    <textarea id="cv-instruct" class="field-textarea h-16" placeholder='e.g. "Speak warmly and slowly"'></textarea>
                    <p class="text-xs text-gray-600 mt-1">Controls delivery style — voice identity comes from the speaker preset</p>
                </div>
                <div class="mb-5">
                    <label class="field-label">Text to Speak</label>
                    <textarea id="cv-text" class="field-textarea h-28" placeholder="Enter the text you want to convert to speech..."></textarea>
                </div>
                <button class="generate-btn" onclick="generateCustomVoice()">Generate Speech</button>
            </div>

            <!-- Voice Clone Tab -->
            <div id="tab-voice-clone" class="tab-content hidden">
                <div class="mb-5">
                    <label class="field-label">Reference Voice Clip</label>
                    <div id="vc-dropzone" class="dropzone">
                        <div class="text-2xl mb-2">🎤</div>
                        <p>Drop audio file here or click to upload</p>
                        <p class="text-xs text-gray-600 mt-1">WAV, MP3, or M4A · 3-10 seconds recommended</p>
                        <input type="file" id="vc-file" accept="audio/*" class="hidden">
                    </div>
                    <div id="vc-file-info" class="hidden mt-2 text-sm text-gray-400"></div>
                </div>
                <div class="mb-5">
                    <label class="field-label">Reference Transcript</label>
                    <textarea id="vc-ref-text" class="field-textarea h-16" placeholder="What is said in the reference clip..."></textarea>
                    <p class="text-xs text-gray-600 mt-1">Must match the reference audio exactly for best results</p>
                </div>
                <div class="mb-5">
                    <label class="field-label">Language</label>
                    <select id="vc-language" class="field-select">
                        <option value="">Loading...</option>
                    </select>
                    <p class="text-xs text-gray-600 mt-1">Target language — can differ from reference clip</p>
                </div>
                <div class="mb-5">
                    <label class="field-label">Text to Speak</label>
                    <textarea id="vc-text" class="field-textarea h-20" placeholder="Enter the text you want spoken in the cloned voice..."></textarea>
                </div>
                <button class="generate-btn" onclick="generateVoiceClone()">Generate Speech</button>
            </div>

            <!-- Voice Design Tab -->
            <div id="tab-voice-design" class="tab-content hidden">
                <div class="mb-5">
                    <label class="field-label">Voice Description <span class="text-red-400">*required</span></label>
                    <textarea id="vd-instruct" class="field-textarea h-20" placeholder='e.g. "A calm, deep male voice with a slight British accent, speaking slowly and thoughtfully"'></textarea>
                    <p class="text-xs text-gray-600 mt-1">Defines voice identity from scratch — pitch, timbre, accent, personality</p>
                </div>
                <div class="mb-5">
                    <label class="field-label">Language</label>
                    <select id="vd-language" class="field-select">
                        <option value="">Loading...</option>
                    </select>
                </div>
                <div class="mb-5">
                    <label class="field-label">Text to Speak</label>
                    <textarea id="vd-text" class="field-textarea h-20" placeholder="Enter the text you want spoken..."></textarea>
                </div>
                <button class="generate-btn" onclick="generateVoiceDesign()">Generate Speech</button>
            </div>
        </div>

        <!-- Right: Output Panel -->
        <div class="p-6">
            <label class="field-label mb-3">Output</label>

            <!-- Status Banner -->
            <div id="status-banner" class="hidden mb-4 p-4 rounded-lg text-sm"></div>

            <!-- Audio Player -->
            <div id="audio-player" class="bg-bg-tertiary border border-gray-700 rounded-lg p-5 mb-4 hidden">
                <audio id="audio-element" class="w-full mb-3" controls></audio>
                <div class="flex gap-2">
                    <a id="download-btn" class="bg-gray-700 hover:bg-gray-600 text-gray-300 px-4 py-2 rounded text-sm cursor-pointer">Download WAV</a>
                </div>
            </div>

            <!-- History -->
            <label class="field-label mb-2">History</label>
            <div id="history-list" class="space-y-2">
                <p class="text-sm text-gray-600">No generations yet</p>
            </div>
        </div>
    </main>

    <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create frontend/style.css**

```css
.tab-btn {
    padding: 0.75rem 1.5rem;
    font-size: 0.875rem;
    color: #666;
    border-bottom: 2px solid transparent;
    background: none;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover {
    color: #999;
}

.tab-btn.active {
    color: #7c8aff;
    border-bottom-color: #7c8aff;
    font-weight: 600;
    background: rgba(122, 138, 255, 0.05);
}

.field-label {
    display: block;
    font-size: 0.75rem;
    color: #aaa;
    margin-bottom: 0.375rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.field-select {
    width: 100%;
    background: #2a2a3e;
    border: 1px solid #444;
    border-radius: 0.375rem;
    padding: 0.625rem 0.875rem;
    color: #fff;
    font-size: 0.875rem;
    appearance: auto;
}

.field-textarea {
    width: 100%;
    background: #2a2a3e;
    border: 1px solid #444;
    border-radius: 0.375rem;
    padding: 0.75rem;
    color: #fff;
    font-size: 0.875rem;
    resize: vertical;
}

.field-textarea::placeholder,
.field-select option:first-child {
    color: #666;
}

.field-textarea:focus,
.field-select:focus {
    outline: none;
    border-color: #7c8aff;
}

.generate-btn {
    width: 100%;
    background: #7c8aff;
    color: #fff;
    text-align: center;
    padding: 0.75rem;
    border-radius: 0.375rem;
    font-weight: 600;
    font-size: 0.9375rem;
    border: none;
    cursor: pointer;
    transition: background 0.15s;
}

.generate-btn:hover {
    background: #6b78ee;
}

.generate-btn:disabled {
    background: #4a4a6a;
    cursor: not-allowed;
}

.dropzone {
    background: #2a2a3e;
    border: 2px dashed #444;
    border-radius: 0.375rem;
    padding: 1.5rem;
    text-align: center;
    color: #888;
    font-size: 0.875rem;
    cursor: pointer;
    transition: border-color 0.15s;
}

.dropzone:hover,
.dropzone.dragover {
    border-color: #7c8aff;
}

.history-item {
    background: #2a2a3e;
    border: 1px solid #444;
    border-radius: 0.375rem;
    padding: 0.75rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    transition: border-color 0.15s;
}

.history-item:hover {
    border-color: #7c8aff;
}

.status-loading {
    background: rgba(122, 138, 255, 0.1);
    border: 1px solid rgba(122, 138, 255, 0.3);
    color: #7c8aff;
}

.status-error {
    background: rgba(255, 107, 107, 0.1);
    border: 1px solid rgba(255, 107, 107, 0.3);
    color: #ff6b6b;
}
```

- [ ] **Step 3: Verify layout renders**

```bash
python main.py
```

Open `http://127.0.0.1:8000` in browser. Expected: Dark themed page with header, three tabs, two-column layout, all form fields visible. Tabs don't switch yet (no JS).

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html frontend/style.css
git commit -m "feat: add complete frontend HTML shell with tabs, forms, and output panel"
```

---

### Task 7: Frontend — JavaScript Application Logic

**Files:**
- Create: `frontend/app.js`

- [ ] **Step 1: Create frontend/app.js**

```javascript
let history = [];
let currentTab = "custom-voice";

// --- Tab Switching ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");

        currentTab = btn.dataset.tab;
        document.querySelectorAll(".tab-content").forEach((c) => c.classList.add("hidden"));
        document.getElementById(`tab-${currentTab}`).classList.remove("hidden");
    });
});

// --- Load Voices & Languages ---
async function loadVoices() {
    try {
        const res = await fetch("/api/voices");
        const data = await res.json();

        const speakerSelect = document.getElementById("cv-speaker");
        speakerSelect.innerHTML = data.speakers
            .map((s) => `<option value="${s.id}">${s.name} — ${s.description} (${s.language})</option>`)
            .join("");

        const languageSelects = ["cv-language", "vc-language", "vd-language"];
        languageSelects.forEach((id) => {
            const sel = document.getElementById(id);
            sel.innerHTML = data.languages
                .map((l) => `<option value="${l}">${l}</option>`)
                .join("");
        });
    } catch (e) {
        console.error("Failed to load voices:", e);
    }
}

// --- File Upload (Voice Clone) ---
const dropzone = document.getElementById("vc-dropzone");
const fileInput = document.getElementById("vc-file");
const fileInfo = document.getElementById("vc-file-info");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        showFileInfo(e.dataTransfer.files[0]);
    }
});
fileInput.addEventListener("change", () => {
    if (fileInput.files.length) showFileInfo(fileInput.files[0]);
});

function showFileInfo(file) {
    fileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    fileInfo.classList.remove("hidden");
}

// --- Status Banner ---
function showStatus(message, type = "loading") {
    const banner = document.getElementById("status-banner");
    banner.textContent = message;
    banner.className = `mb-4 p-4 rounded-lg text-sm status-${type}`;
    banner.classList.remove("hidden");
}

function hideStatus() {
    document.getElementById("status-banner").classList.add("hidden");
}

// --- Model Loading Poll ---
async function pollModelStatus(variant) {
    while (true) {
        const res = await fetch(`/api/model-status?variant=${variant}`);
        const data = await res.json();

        if (data.status === "ready") {
            hideStatus();
            return true;
        }
        if (data.status === "error") {
            showStatus(data.message, "error");
            return false;
        }
        showStatus(data.message, "loading");
        await new Promise((r) => setTimeout(r, 2000));
    }
}

// --- Set Button State ---
function setGenerating(tabId, generating) {
    const btn = document.querySelector(`#tab-${tabId} .generate-btn`);
    if (generating) {
        btn.disabled = true;
        btn.textContent = "Generating...";
    } else {
        btn.disabled = false;
        btn.textContent = "Generate Speech";
    }
}

// --- Handle Generation Response ---
async function handleResponse(res, tabId, variant, meta) {
    const data = await res.json();

    if (data.status === "loading") {
        showStatus(data.message, "loading");
        const ready = await pollModelStatus(variant);
        if (!ready) {
            setGenerating(tabId, false);
            return;
        }
        // Retry the generation — model is now loaded
        return null; // Signal to retry
    }

    if (data.status === "done") {
        hideStatus();
        showAudio(data.filename);
        addHistory({ ...data, text: meta.text });
        setGenerating(tabId, false);
    }

    if (data.status === "error") {
        showStatus(data.message, "error");
        setGenerating(tabId, false);
    }
}

// --- Generate: Custom Voice ---
async function generateCustomVoice() {
    const text = document.getElementById("cv-text").value.trim();
    if (!text) return;

    setGenerating("custom-voice", true);

    const form = new FormData();
    form.append("text", text);
    form.append("language", document.getElementById("cv-language").value);
    form.append("speaker", document.getElementById("cv-speaker").value);
    form.append("instruct", document.getElementById("cv-instruct").value);

    while (true) {
        const res = await fetch("/api/tts/custom-voice", { method: "POST", body: form });
        const result = await handleResponse(res, "custom-voice", "custom_voice", { text });
        if (result !== null) break;
    }
}

// --- Generate: Voice Clone ---
async function generateVoiceClone() {
    const text = document.getElementById("vc-text").value.trim();
    const refText = document.getElementById("vc-ref-text").value.trim();
    const file = document.getElementById("vc-file").files[0];
    if (!text || !refText || !file) {
        showStatus("Please fill in all fields and upload a reference audio clip.", "error");
        return;
    }

    setGenerating("voice-clone", true);

    const form = new FormData();
    form.append("text", text);
    form.append("language", document.getElementById("vc-language").value);
    form.append("ref_text", refText);
    form.append("ref_audio", file);

    while (true) {
        const res = await fetch("/api/tts/voice-clone", { method: "POST", body: form });
        const result = await handleResponse(res, "voice-clone", "voice_clone", { text });
        if (result !== null) break;
    }
}

// --- Generate: Voice Design ---
async function generateVoiceDesign() {
    const text = document.getElementById("vd-text").value.trim();
    const instruct = document.getElementById("vd-instruct").value.trim();
    if (!text || !instruct) {
        showStatus("Please fill in both voice description and text.", "error");
        return;
    }

    setGenerating("voice-design", true);

    const form = new FormData();
    form.append("text", text);
    form.append("language", document.getElementById("vd-language").value);
    form.append("instruct", instruct);

    while (true) {
        const res = await fetch("/api/tts/voice-design", { method: "POST", body: form });
        const result = await handleResponse(res, "voice-design", "voice_design", { text });
        if (result !== null) break;
    }
}

// --- Audio Player ---
function showAudio(filename) {
    const player = document.getElementById("audio-player");
    const audio = document.getElementById("audio-element");
    const downloadBtn = document.getElementById("download-btn");

    const url = `/audio/${filename}`;
    audio.src = url;
    downloadBtn.href = url;
    downloadBtn.download = filename;

    player.classList.remove("hidden");
    audio.play();
}

// --- History ---
function addHistory(item) {
    const snippet = item.text.length > 40 ? item.text.substring(0, 40) + "..." : item.text;
    let label = item.mode.replace("_", " ");
    if (item.speaker) label = item.speaker;
    if (item.mode === "voice_clone") label = "Cloned voice";
    if (item.mode === "voice_design") label = "Designed voice";

    history.unshift({ ...item, snippet, label });

    const list = document.getElementById("history-list");
    list.innerHTML = history
        .map(
            (h, i) => `
        <div class="history-item" onclick="showAudio('${h.filename}')">
            <div>
                <div class="text-white text-sm">"${h.snippet}"</div>
                <div class="text-gray-500 text-xs">${h.label} · ${h.language} · ${h.duration}s</div>
            </div>
            <div class="text-accent text-sm">▶</div>
        </div>
    `
        )
        .join("");
}

// --- Init ---
loadVoices();
```

- [ ] **Step 2: Verify the full app works end-to-end in the browser**

```bash
python main.py
```

Open `http://127.0.0.1:8000`. Verify:
1. Tabs switch correctly, showing/hiding the right content
2. Speaker and language dropdowns are populated
3. File upload drag-and-drop shows file info
4. Generate button exists on each tab

At this point, clicking Generate will trigger model download (takes a few minutes on first run). The status banner should show download progress.

- [ ] **Step 3: Commit**

```bash
git add frontend/app.js
git commit -m "feat: add frontend JS with tab switching, API calls, audio player, and history"
```

---

### Task 8: End-to-End Testing & Polish

**Files:**
- Modify: `main.py` (add CORS if needed, logging)

- [ ] **Step 1: Add startup logging to main.py**

Replace `main.py` with:

```python
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Studio")

os.makedirs("audio_output", exist_ok=True)
os.makedirs("voice_clips", exist_ok=True)

app.include_router(router, prefix="/api")
app.mount("/audio", StaticFiles(directory="audio_output"), name="audio")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    import torch

    device = "MPS (Apple Silicon)" if torch.backends.mps.is_available() else "CPU"
    logger.info(f"Starting Voice Studio on {device}")
    logger.info("Models will be downloaded and loaded on first use")
    logger.info("Open http://127.0.0.1:8000 in your browser")
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 2: Test Custom Voice generation**

1. Start the app: `python main.py`
2. Open `http://127.0.0.1:8000`
3. Select speaker "Ryan", language "English"
4. Type: "Hello, this is a test of the voice studio application."
5. Click Generate Speech
6. First run: status banner should show model download progress
7. After model loads: audio should play automatically
8. Download button should work
9. History entry should appear

Expected: WAV file generated and playable.

- [ ] **Step 3: Test Voice Clone generation**

1. Switch to Voice Clone tab
2. Upload a short audio clip (3-10 seconds)
3. Type the transcript of the clip
4. Select language, enter text to speak
5. Click Generate Speech

Expected: Audio generated in the cloned voice.

- [ ] **Step 4: Test Voice Design generation**

1. Switch to Voice Design tab
2. Enter: "A deep, calm male voice with a British accent"
3. Select language "English"
4. Enter text to speak
5. Click Generate Speech

Expected: Audio generated with the designed voice characteristics.

- [ ] **Step 5: Commit final polish**

```bash
git add -A
git commit -m "feat: complete voice studio with all 3 TTS modes, audio player, and history"
```

---

## Quick Start (for README reference)

```bash
# 1. Create environment
conda create -n voice_studio python=3.12 -y
conda activate voice_studio

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py

# 4. Open browser
open http://127.0.0.1:8000
```

Models download automatically on first use (~3-4GB per variant). Subsequent runs start instantly.
