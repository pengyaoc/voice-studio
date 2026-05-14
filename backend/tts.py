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
