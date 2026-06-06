import os
import uuid
import soundfile as sf
import numpy as np


AUDIO_OUTPUT_DIR = "audio_output"
STREAM_CHUNKS_DIR = os.path.join(AUDIO_OUTPUT_DIR, "stream_chunks")


def save_wav(audio_data: np.ndarray, sample_rate: int, directory: str = AUDIO_OUTPUT_DIR) -> str:
    os.makedirs(directory, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:12]}.wav"
    filepath = os.path.join(directory, filename)
    sf.write(filepath, audio_data, sample_rate)
    return os.path.relpath(filepath, AUDIO_OUTPUT_DIR)


def concatenate_audio(chunks: list[np.ndarray]) -> np.ndarray:
    if not chunks:
        raise ValueError("Cannot concatenate empty audio chunks")
    if len(chunks) == 1:
        return np.asarray(chunks[0], dtype=np.float32)
    return np.concatenate([np.asarray(chunk, dtype=np.float32) for chunk in chunks])


def get_audio_duration(filepath: str) -> float:
    info = sf.info(filepath)
    return round(info.duration, 2)
