import os
import shutil
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from backend.models import model_manager, ModelVariant, ModelSize, MODEL_IDS
from backend.history import list_history
from backend.preferences import get_clone_preferences, save_clone_preferences
from backend.tts import generate_custom_voice, generate_voice_clone, generate_voice_design

router = APIRouter()


class VoiceClonePreferencesPayload(BaseModel):
    reference_clip: str = ""
    ref_text: str = ""

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
VOICE_CLIPS_DIR = "voice_clips"


def _serialize_reference_clip(filename: str) -> dict:
    filepath = os.path.join(VOICE_CLIPS_DIR, filename)
    return {
        "filename": filename,
        "size": os.path.getsize(filepath),
        "modified_at": os.path.getmtime(filepath),
    }


def _resolve_reference_clip(filename: str) -> str:
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid reference clip name")

    clip_path = os.path.join(VOICE_CLIPS_DIR, safe_name)
    if not os.path.exists(clip_path):
        raise HTTPException(status_code=404, detail=f"Reference clip not found: {filename}")
    return clip_path


@router.get("/voices")
async def list_voices():
    model_sizes = {
        variant.value: [
            size.value for size in ModelSize if (variant, size) in model_manager.model_ids
        ]
        for variant in ModelVariant
    }
    return {
        "speakers": SPEAKERS,
        "languages": LANGUAGES,
        "model_sizes": model_sizes,
        "runtime": model_manager.get_runtime(),
        "supports_fast_clone": model_manager.supports_fast_clone(),
    }


@router.get("/model-status")
async def model_status(variant: str = "custom_voice", model_size: str = "1.7B"):
    try:
        v = ModelVariant(variant)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown variant: {variant}")
    try:
        s = ModelSize(model_size)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown model size: {model_size}")
    return model_manager.get_status(v, s)


@router.get("/history")
async def history():
    return {"items": list_history()}


@router.get("/reference-clips")
async def reference_clips():
    os.makedirs(VOICE_CLIPS_DIR, exist_ok=True)
    clips = []
    for filename in sorted(os.listdir(VOICE_CLIPS_DIR)):
        if filename.startswith("."):
            continue
        filepath = os.path.join(VOICE_CLIPS_DIR, filename)
        if os.path.isfile(filepath):
            clips.append(_serialize_reference_clip(filename))
    return {"items": clips}


@router.get("/voice-clone/preferences")
async def voice_clone_preferences():
    return get_clone_preferences()


@router.post("/voice-clone/preferences")
async def save_voice_clone_preferences(payload: VoiceClonePreferencesPayload):
    return save_clone_preferences(
        reference_clip=payload.reference_clip,
        ref_text=payload.ref_text,
    )


@router.post("/tts/custom-voice")
async def tts_custom_voice(
    text: str = Form(...),
    language: str = Form(...),
    speaker: str = Form(...),
    instruct: str = Form(""),
    model_size: str = Form("1.7B"),
):
    try:
        size = ModelSize(model_size)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown model size: {model_size}")
    result = generate_custom_voice(
        text=text,
        language=language,
        speaker=speaker,
        instruct=instruct if instruct else None,
        model_size=size,
    )
    return result


@router.post("/tts/voice-clone")
async def tts_voice_clone(
    text: str = Form(...),
    language: str = Form(...),
    ref_text: str = Form(""),
    ref_audio: UploadFile | None = File(None),
    reference_clip: str = Form(""),
    model_size: str = Form("1.7B"),
):
    try:
        size = ModelSize(model_size)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown model size: {model_size}")

    os.makedirs(VOICE_CLIPS_DIR, exist_ok=True)
    clip_path = None
    if ref_audio is not None and ref_audio.filename:
        clip_path = os.path.join(VOICE_CLIPS_DIR, os.path.basename(ref_audio.filename))
        with open(clip_path, "wb") as f:
            shutil.copyfileobj(ref_audio.file, f)
    elif reference_clip:
        clip_path = _resolve_reference_clip(reference_clip)

    if clip_path is None:
        raise HTTPException(status_code=400, detail="Provide a reference audio file or choose a saved clip")

    save_clone_preferences(
        reference_clip=os.path.basename(clip_path),
        ref_text=ref_text,
    )

    result = generate_voice_clone(
        text=text,
        language=language,
        ref_audio_path=clip_path,
        ref_text=ref_text if ref_text else None,
        model_size=size,
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
