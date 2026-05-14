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
