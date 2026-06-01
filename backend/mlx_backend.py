import numpy as np


DEFAULT_SAMPLE_RATE = 24000


class MLXQwen3TTSModelWrapper:
    def __init__(self, model_id: str):
        from mlx_audio.tts.utils import load_model

        self.model = load_model(model_id)
        self.model_id = model_id

    def _finalize(self, results) -> tuple[list[np.ndarray], int]:
        chunks = list(results)
        if not chunks:
            raise RuntimeError(f"No audio returned by MLX-Audio for {self.model_id}")

        final = chunks[-1]
        audio = np.asarray(final.audio, dtype=np.float32)
        sample_rate = (
            getattr(final, "sample_rate", None)
            or getattr(final, "_sample_rate", None)
            or getattr(final, "sampling_rate", None)
            or DEFAULT_SAMPLE_RATE
        )
        return [audio], int(sample_rate)

    def generate_custom_voice(self, **kwargs) -> tuple[list[np.ndarray], int]:
        return self._finalize(self.model.generate_custom_voice(**kwargs))

    def generate_voice_clone(self, **kwargs) -> tuple[list[np.ndarray], int]:
        kwargs.pop("x_vector_only_mode", None)
        return self._finalize(self.model.generate(**kwargs))

    def generate_voice_design(self, **kwargs) -> tuple[list[np.ndarray], int]:
        return self._finalize(self.model.generate_voice_design(**kwargs))
