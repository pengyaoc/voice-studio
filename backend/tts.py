import os
import re
import threading
import time
from collections.abc import Iterator

from backend.models import model_manager, ModelVariant, ModelSize, MODEL_IDS
from backend.audio_utils import (
    AUDIO_OUTPUT_DIR,
    STREAM_CHUNKS_DIR,
    concatenate_audio,
    get_audio_duration,
    save_wav,
)
from backend.history import add_history_entry


STREAMING_CHUNK_MODEL_SIZE = ModelSize.SMALL
STREAMING_TARGET_CHARS = 90


def _round_elapsed(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 2)


def _build_history_entry(
    *,
    filename: str,
    duration: float,
    mode: str,
    model_size: str,
    language: str,
    text: str,
    processing_time: float,
    extra: dict | None = None,
) -> dict:
    return add_history_entry({
        "status": "done",
        "filename": filename,
        "duration": duration,
        "mode": mode,
        "model_size": model_size,
        "language": language,
        "text": text,
        "processing_time": processing_time,
        **(extra or {}),
    })


def _split_text_for_streaming(text: str, target_chars: int = STREAMING_TARGET_CHARS) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    sentences = [
        segment.strip()
        for segment in re.split(r"(?<=[。！？!?;；:\n])\s*", stripped)
        if segment.strip()
    ]
    if not sentences:
        sentences = [stripped]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = sentence if not current else f"{current} {sentence}"
        if current and len(candidate) > target_chars:
            chunks.append(current)
            current = sentence
            continue
        current = candidate

    if current:
        chunks.append(current)

    expanded: list[str] = []
    for chunk in chunks:
        if len(chunk) <= target_chars * 2:
            expanded.append(chunk)
            continue
        words = chunk.split()
        if len(words) > 1:
            current_words = ""
            for word in words:
                candidate = word if not current_words else f"{current_words} {word}"
                if current_words and len(candidate) > target_chars:
                    expanded.append(current_words)
                    current_words = word
                    continue
                current_words = candidate
            if current_words:
                expanded.append(current_words)
            continue

        for index in range(0, len(chunk), target_chars):
            expanded.append(chunk[index:index + target_chars])

    return expanded


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

    started_at = time.perf_counter()
    wavs, sr = model.generate_custom_voice(**kwargs)
    processing_time = _round_elapsed(started_at)

    filename = save_wav(wavs[0], sr)
    duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, filename))

    return _build_history_entry(
        filename=filename,
        duration=duration,
        mode="custom_voice",
        model_size=model_size.value,
        language=language,
        text=text,
        processing_time=processing_time,
        extra={
            "speaker": speaker,
            "instruct": instruct or "",
        },
    )


def generate_voice_clone(
    text: str,
    language: str,
    ref_audio_path: str,
    ref_text: str | None,
    profile_name: str | None = None,
    model_size: ModelSize = ModelSize.LARGE,
) -> dict:
    variant = ModelVariant.VOICE_CLONE
    if not _ensure_model_loaded(variant, model_size):
        return {"status": "loading", **model_manager.get_status(variant, model_size)}

    model = model_manager.get_model(variant, model_size)

    started_at = time.perf_counter()
    wavs, sr = model.generate_voice_clone(
        text=text,
        language=language,
        ref_audio=ref_audio_path,
        ref_text=ref_text,
    )
    processing_time = _round_elapsed(started_at)

    filename = save_wav(wavs[0], sr)
    duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, filename))

    return _build_history_entry(
        filename=filename,
        duration=duration,
        mode="voice_clone",
        model_size=model_size.value,
        language=language,
        text=text,
        processing_time=processing_time,
        extra={
            "profile_name": profile_name or "",
            "ref_text": ref_text or "",
        },
    )


def generate_voice_design(text: str, language: str, instruct: str) -> dict:
    variant = ModelVariant.VOICE_DESIGN
    if not _ensure_model_loaded(variant):
        return {"status": "loading", **model_manager.get_status(variant)}

    model = model_manager.get_model(variant)

    started_at = time.perf_counter()
    wavs, sr = model.generate_voice_design(
        text=text, language=language, instruct=instruct
    )
    processing_time = _round_elapsed(started_at)

    filename = save_wav(wavs[0], sr)
    duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, filename))

    return _build_history_entry(
        filename=filename,
        duration=duration,
        mode="voice_design",
        model_size=ModelSize.LARGE.value,
        language=language,
        text=text,
        processing_time=processing_time,
        extra={
            "instruct": instruct,
        },
    )


def _stream_chunks(
    *,
    variant: ModelVariant,
    size: ModelSize,
    text: str,
    generator,
    history_mode: str,
    language: str,
    extra: dict | None = None,
) -> Iterator[dict]:
    if not _ensure_model_loaded(variant, size):
        yield {"status": "loading", **model_manager.get_status(variant, size)}
        return

    chunks = _split_text_for_streaming(text)
    if not chunks:
        yield {"status": "error", "message": "No text provided for streaming generation."}
        return

    full_started_at = time.perf_counter()
    chunk_audio: list = []
    sample_rate = None

    for index, chunk_text in enumerate(chunks):
        chunk_started_at = time.perf_counter()
        wavs, sr = generator(chunk_text)
        sample_rate = sr
        audio = wavs[0]
        chunk_audio.append(audio)

        chunk_filename = save_wav(audio, sr, directory=STREAM_CHUNKS_DIR)
        chunk_duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, chunk_filename))

        yield {
            "status": "chunk",
            "index": index,
            "count": len(chunks),
            "filename": chunk_filename,
            "duration": chunk_duration,
            "text": chunk_text,
            "processing_time": _round_elapsed(chunk_started_at),
        }

    combined_audio = concatenate_audio(chunk_audio)
    final_filename = save_wav(combined_audio, sample_rate or 24000)
    final_duration = get_audio_duration(os.path.join(AUDIO_OUTPUT_DIR, final_filename))
    history_item = _build_history_entry(
        filename=final_filename,
        duration=final_duration,
        mode=history_mode,
        model_size=size.value,
        language=language,
        text=text,
        processing_time=_round_elapsed(full_started_at),
        extra={
            **(extra or {}),
            "streaming": True,
            "chunk_count": len(chunks),
        },
    )
    yield {"status": "done", "item": history_item}


def stream_custom_voice(
    text: str,
    language: str,
    speaker: str,
    instruct: str | None = None,
) -> Iterator[dict]:
    variant = ModelVariant.CUSTOM_VOICE
    size = STREAMING_CHUNK_MODEL_SIZE

    def generate_chunk(chunk_text: str):
        model = model_manager.get_model(variant, size)
        kwargs = {"text": chunk_text, "language": language, "speaker": speaker}
        if instruct:
            kwargs["instruct"] = instruct
        return model.generate_custom_voice(**kwargs)

    yield from _stream_chunks(
        variant=variant,
        size=size,
        text=text,
        generator=generate_chunk,
        history_mode="custom_voice",
        language=language,
        extra={
            "speaker": speaker,
            "instruct": instruct or "",
        },
    )


def stream_voice_clone(
    text: str,
    language: str,
    ref_audio_path: str,
    ref_text: str | None,
    profile_name: str | None = None,
) -> Iterator[dict]:
    variant = ModelVariant.VOICE_CLONE
    size = STREAMING_CHUNK_MODEL_SIZE

    def generate_chunk(chunk_text: str):
        model = model_manager.get_model(variant, size)
        return model.generate_voice_clone(
            text=chunk_text,
            language=language,
            ref_audio=ref_audio_path,
            ref_text=ref_text,
        )

    yield from _stream_chunks(
        variant=variant,
        size=size,
        text=text,
        generator=generate_chunk,
        history_mode="voice_clone",
        language=language,
        extra={
            "profile_name": profile_name or "",
            "ref_text": ref_text or "",
        },
    )
