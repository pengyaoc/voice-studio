import os
import platform
import threading
import torch
from enum import Enum


class ModelVariant(str, Enum):
    CUSTOM_VOICE = "custom_voice"
    VOICE_CLONE = "voice_clone"
    VOICE_DESIGN = "voice_design"


class ModelSize(str, Enum):
    SMALL = "0.6B"
    LARGE = "1.7B"


MODEL_IDS = {
    (ModelVariant.CUSTOM_VOICE, ModelSize.LARGE): "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    (ModelVariant.CUSTOM_VOICE, ModelSize.SMALL): "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    (ModelVariant.VOICE_CLONE, ModelSize.LARGE): "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    (ModelVariant.VOICE_CLONE, ModelSize.SMALL): "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    (ModelVariant.VOICE_DESIGN, ModelSize.LARGE): "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
}

MLX_MODEL_IDS = {
    (ModelVariant.CUSTOM_VOICE, ModelSize.LARGE): "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16",
    (ModelVariant.CUSTOM_VOICE, ModelSize.SMALL): "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-bf16",
    (ModelVariant.VOICE_CLONE, ModelSize.LARGE): "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
    (ModelVariant.VOICE_CLONE, ModelSize.SMALL): "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16",
    (ModelVariant.VOICE_DESIGN, ModelSize.LARGE): "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16",
}

DTYPES = {
    (ModelVariant.CUSTOM_VOICE, ModelSize.LARGE): torch.float16,
    (ModelVariant.CUSTOM_VOICE, ModelSize.SMALL): torch.float16,
    (ModelVariant.VOICE_CLONE, ModelSize.LARGE): torch.float32,
    (ModelVariant.VOICE_CLONE, ModelSize.SMALL): torch.float32,
    (ModelVariant.VOICE_DESIGN, ModelSize.LARGE): torch.float16,
}


def _cache_key(variant: ModelVariant, size: ModelSize) -> str:
    return f"{variant.value}_{size.value}"


def _default_runtime() -> str:
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mlx"
    return "qwen"


RUNTIME = os.environ.get("VOICE_STUDIO_BACKEND", _default_runtime()).lower()
USING_MLX = RUNTIME == "mlx"
ACTIVE_MODEL_IDS = MLX_MODEL_IDS if USING_MLX else MODEL_IDS
SUPPORTS_FAST_CLONE = not USING_MLX
MODEL_IDS = ACTIVE_MODEL_IDS


def _huggingface_hub_cache_dir() -> str:
    if os.environ.get("HUGGINGFACE_HUB_CACHE"):
        return os.environ["HUGGINGFACE_HUB_CACHE"]
    if os.environ.get("HF_HOME"):
        return os.path.join(os.environ["HF_HOME"], "hub")
    return os.path.expanduser("~/.cache/huggingface/hub")


def _is_model_cached(model_id: str) -> bool:
    owner, name = model_id.split("/", 1)
    repo_dir = os.path.join(_huggingface_hub_cache_dir(), f"models--{owner}--{name}")
    snapshots_dir = os.path.join(repo_dir, "snapshots")
    return os.path.isdir(snapshots_dir) and any(os.scandir(snapshots_dir))


class ModelManager:
    def __init__(self):
        self._models: dict = {}
        self._status: dict[str, dict] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._lock_creation = threading.Lock()
        self.model_ids = ACTIVE_MODEL_IDS

    def _get_lock(self, key: str) -> threading.Lock:
        with self._lock_creation:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def get_status(self, variant: ModelVariant, size: ModelSize = ModelSize.LARGE) -> dict:
        key = _cache_key(variant, size)
        return self._status.get(key, {"status": "not_loaded"})

    def get_runtime(self) -> str:
        return RUNTIME

    def supports_fast_clone(self) -> bool:
        return SUPPORTS_FAST_CLONE

    def get_model(self, variant: ModelVariant, size: ModelSize = ModelSize.LARGE):
        key = _cache_key(variant, size)
        if key in self._models:
            return self._models[key]
        return None

    def load_model(self, variant: ModelVariant, size: ModelSize = ModelSize.LARGE):
        model_key = (variant, size)
        if model_key not in ACTIVE_MODEL_IDS:
            raise ValueError(f"No {size.value} model available for {variant.value}")

        key = _cache_key(variant, size)
        lock = self._get_lock(key)
        if not lock.acquire(blocking=False):
            return

        try:
            if key in self._models:
                return

            model_id = ACTIVE_MODEL_IDS[model_key]
            device_label = "MLX (Apple Silicon)" if USING_MLX else (
                "MPS (Apple Silicon)" if torch.backends.mps.is_available() else "CPU (fallback)"
            )
            cached_locally = _is_model_cached(model_id)
            loading_message = (
                f"Loading {model_id} from local cache on {device_label}..."
                if cached_locally
                else f"Downloading and loading {model_id}... This may take a few minutes on first run."
            )

            self._status[key] = {
                "status": "loading",
                "message": loading_message,
                "device": device_label,
            }

            if USING_MLX:
                from backend.mlx_backend import MLXQwen3TTSModelWrapper

                model = MLXQwen3TTSModelWrapper(model_id)
            else:
                dtype = DTYPES[model_key]
                device = "mps" if torch.backends.mps.is_available() else "cpu"

                from qwen_tts import Qwen3TTSModel

                model = Qwen3TTSModel.from_pretrained(
                    model_id,
                    device_map=device,
                    dtype=dtype,
                )

            self._models[key] = model
            self._status[key] = {
                "status": "ready",
                "message": f"{model_id} loaded on {device_label}",
                "device": device_label,
            }
        except Exception as e:
            self._status[key] = {
                "status": "error",
                "message": f"Failed to load model: {str(e)}",
            }
        finally:
            lock.release()


model_manager = ModelManager()
