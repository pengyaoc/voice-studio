# Worklog

## 2026-05-31

### MLX backend migration

- Swapped the default backend on Apple Silicon to MLX-Audio and validated successful generation for:
  - `custom_voice` `0.6B`
  - `voice_clone` `0.6B`
  - `voice_design` `1.7B`
- Fixed an MLX runtime failure caused by loading models in a background thread and then generating from a different request thread.
  - Symptom: `RuntimeError: There is no Stream(gpu, ...) in current thread.`
  - Resolution: MLX model loading now happens synchronously in the request thread on first use.

### Known issue left as-is

- The legacy `qwen-tts` fallback backend is not currently considered repaired.
- Installing `mlx-audio` upgraded shared dependencies in the project virtualenv, most notably `transformers`.
- `qwen-tts 0.1.1` expects `transformers==4.57.3`, while `mlx-audio` installed a newer `transformers` version.
- Result:
  - The active MLX backend works.
  - The fallback `VOICE_STUDIO_BACKEND=qwen` path may be unreliable until dependencies are isolated or the environment is split.
- Decision:
  - Leave the fallback backend as-is for now.
  - Treat MLX as the supported runtime on this Apple Silicon machine.
