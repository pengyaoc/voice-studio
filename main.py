import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.routes import router

app = FastAPI(title="Voice Studio")

os.makedirs("audio_output", exist_ok=True)
os.makedirs("voice_clips", exist_ok=True)

app.include_router(router, prefix="/api")
app.mount("/audio", StaticFiles(directory="audio_output"), name="audio")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
