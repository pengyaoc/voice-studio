import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Studio")

os.makedirs("audio_output", exist_ok=True)
os.makedirs("voice_clips", exist_ok=True)

app.include_router(router, prefix="/api")
app.mount("/audio", StaticFiles(directory="audio_output"), name="audio")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    import torch

    device = "MPS (Apple Silicon)" if torch.backends.mps.is_available() else "CPU"
    logger.info(f"Starting Voice Studio on {device}")
    logger.info("Models will be downloaded and loaded on first use")
    logger.info("Open http://127.0.0.1:8000 in your browser")
    uvicorn.run(app, host="127.0.0.1", port=8000)
