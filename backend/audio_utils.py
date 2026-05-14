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
