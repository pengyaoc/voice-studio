import json
import os
import threading
from datetime import datetime

from backend.audio_utils import AUDIO_OUTPUT_DIR, get_audio_duration


HISTORY_FILE = os.path.join(AUDIO_OUTPUT_DIR, "history.json")
_history_lock = threading.Lock()


def _read_history_unlocked() -> list[dict]:
    if not os.path.exists(HISTORY_FILE):
        return []

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    return []


def _write_history_unlocked(items: list[dict]) -> None:
    temp_file = f"{HISTORY_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=True, indent=2)
    os.replace(temp_file, HISTORY_FILE)


def _build_recovered_entry(filename: str) -> dict:
    filepath = os.path.join(AUDIO_OUTPUT_DIR, filename)
    created_at = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
    return {
        "filename": filename,
        "duration": get_audio_duration(filepath),
        "mode": "recovered",
        "model_size": "unknown",
        "language": "Unknown",
        "text": "Recovered generation",
        "label": "Recovered clip",
        "snippet": filename,
        "created_at": created_at,
    }


def list_history() -> list[dict]:
    with _history_lock:
        items = _read_history_unlocked()
        indexed = {item.get("filename"): item for item in items if item.get("filename")}

        recovered = False
        for filename in sorted(os.listdir(AUDIO_OUTPUT_DIR), reverse=True):
            if not filename.endswith(".wav"):
                continue
            if filename not in indexed:
                items.append(_build_recovered_entry(filename))
                recovered = True

        items = [
            item for item in items
            if item.get("filename")
            and os.path.exists(os.path.join(AUDIO_OUTPUT_DIR, item["filename"]))
        ]
        items.sort(key=lambda item: item.get("created_at", ""), reverse=True)

        if recovered:
            _write_history_unlocked(items)

        return items


def add_history_entry(item: dict) -> dict:
    entry = {
        **item,
        "created_at": item.get("created_at") or datetime.now().isoformat(),
    }

    with _history_lock:
        items = _read_history_unlocked()
        items = [existing for existing in items if existing.get("filename") != entry.get("filename")]
        items.insert(0, entry)
        _write_history_unlocked(items)

    return entry
