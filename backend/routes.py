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
