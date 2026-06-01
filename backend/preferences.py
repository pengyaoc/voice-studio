import json
import os
import threading

from backend.history import list_history


PREFERENCES_FILE = os.path.join("voice_clips", "preferences.json")
_preferences_lock = threading.Lock()


def _default_clone_preferences() -> dict:
    latest_clone = next(
        (item for item in list_history() if item.get("mode") == "voice_clone"),
        None,
    )
    return {
        "reference_clip": "",
        "ref_text": latest_clone.get("ref_text", "") if latest_clone else "",
    }


def get_clone_preferences() -> dict:
    with _preferences_lock:
        if not os.path.exists(PREFERENCES_FILE):
            return _default_clone_preferences()

        with open(PREFERENCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    prefs = _default_clone_preferences()
    if isinstance(data, dict):
        prefs.update({
            "reference_clip": data.get("reference_clip", ""),
            "ref_text": data.get("ref_text", prefs["ref_text"]),
        })
    return prefs


def save_clone_preferences(reference_clip: str, ref_text: str) -> dict:
    prefs = {
        "reference_clip": reference_clip,
        "ref_text": ref_text,
    }

    os.makedirs(os.path.dirname(PREFERENCES_FILE), exist_ok=True)
    temp_file = f"{PREFERENCES_FILE}.tmp"
    with _preferences_lock:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=True, indent=2)
        os.replace(temp_file, PREFERENCES_FILE)

    return prefs
