import os
import threading
from backend.models import model_manager, ModelVariant, ModelSize, MODEL_IDS
from backend.audio_utils import save_wav, get_audio_duration, AUDIO_OUTPUT_DIR
from backend.history import add_history_entry


def _ensure_model_loaded(variant: ModelVariant, size: ModelSize = ModelSize.LARGE) -> bool:
    if (variant, size) not in MODEL_IDS:
        raise ValueError(f"No {size.value} model available for {variant.value}")

    model = model_manager.get_model(variant, size)
    if model is not None:
        return True

    if model_manager.get_runtime() == "mlx":
        model_manager.load_model(variant, size)
        return model_manager.get_model(variant, size) is not None

    status = model_manager.get_status(variant, size)
    if status["status"] == "loading":
        return False

    thread = threading.Thread(
        target=model_manager.load_model, args=(variant, size), daemon=True
    )
    thread.start()
    return False


def generate_custom_voice(
    text: str, language: str, speaker: str, instruct: str | None = None,
    model_size: ModelSize = ModelSize.LARGE,
) -> dict:
    variant = ModelVariant.CUSTOM_VOICE
    if not _ensure_model_loaded(variant, model_size):
        return {"status": "loading", **model_manager.get_status(variant, model_size)}

    model = model_manager.get_model(variant, model_size)
    kwargs = {"text": text, "language": language, "speaker": speaker}
    if instruct:
        kwargs["instruct"] = instruct

    wavs, sr = model.generate_custom_voice(**kwargs)

    filename = save_wav(wavs[0], sr)
    duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, filename))

    return add_history_entry({
        "status": "done",
        "filename": filename,
        "duration": duration,
        "mode": "custom_voice",
        "model_size": model_size.value,
        "speaker": speaker,
        "language": language,
        "text": text,
        "instruct": instruct or "",
    })


def generate_voice_clone(
    text: str,
    language: str,
    ref_audio_path: str,
    ref_text: str | None,
    model_size: ModelSize = ModelSize.LARGE,
) -> dict:
    variant = ModelVariant.VOICE_CLONE
    if not _ensure_model_loaded(variant, model_size):
        return {"status": "loading", **model_manager.get_status(variant, model_size)}

    model = model_manager.get_model(variant, model_size)

    wavs, sr = model.generate_voice_clone(
        text=text,
        language=language,
        ref_audio=ref_audio_path,
        ref_text=ref_text,
    )

    filename = save_wav(wavs[0], sr)
    duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, filename))

    return add_history_entry({
        "status": "done",
        "filename": filename,
        "duration": duration,
        "mode": "voice_clone",
        "model_size": model_size.value,
        "language": language,
        "text": text,
        "ref_text": ref_text or "",
    })


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

    return add_history_entry({
        "status": "done",
        "filename": filename,
        "duration": duration,
        "mode": "voice_design",
        "model_size": ModelSize.LARGE.value,
        "language": language,
        "text": text,
        "instruct": instruct,
    })
