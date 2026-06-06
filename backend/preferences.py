import json
import os
import threading
import uuid
from datetime import datetime

from backend.history import list_history


PREFERENCES_FILE = os.path.join("voice_clips", "preferences.json")
_preferences_lock = threading.Lock()


def _timestamp() -> str:
    return datetime.now().isoformat()


def _default_selected_fields() -> dict:
    latest_clone = next(
        (item for item in list_history() if item.get("mode") == "voice_clone"),
        None,
    )
    return {
        "reference_clip": "",
        "ref_text": latest_clone.get("ref_text", "") if latest_clone else "",
    }


def _default_state() -> dict:
    return {
        "profiles": [],
        "selected_profile_id": "",
    }


def _profile_name_from_clip(reference_clip: str) -> str:
    if not reference_clip:
        return "Imported Voice"
    return os.path.splitext(os.path.basename(reference_clip))[0] or "Imported Voice"


def _normalize_profile(profile: dict) -> dict:
    now = _timestamp()
    return {
        "id": str(profile.get("id") or uuid.uuid4().hex[:12]),
        "name": str(profile.get("name") or "").strip() or _profile_name_from_clip(str(profile.get("reference_clip") or "")),
        "reference_clip": str(profile.get("reference_clip") or ""),
        "ref_text": str(profile.get("ref_text") or ""),
        "created_at": str(profile.get("created_at") or now),
        "updated_at": str(profile.get("updated_at") or profile.get("created_at") or now),
    }


def _migrate_legacy_state(data: dict) -> dict:
    state = _default_state()
    reference_clip = str(data.get("reference_clip") or "")
    ref_text = str(data.get("ref_text") or "")
    if reference_clip or ref_text:
        profile = _normalize_profile({
            "name": _profile_name_from_clip(reference_clip),
            "reference_clip": reference_clip,
            "ref_text": ref_text,
        })
        state["profiles"] = [profile]
        state["selected_profile_id"] = profile["id"]
    return state


def _normalize_state(data: dict | None) -> dict:
    base = _default_state()
    if not isinstance(data, dict):
        return base

    if "profiles" not in data:
        return _migrate_legacy_state(data)

    profiles = [
        _normalize_profile(profile)
        for profile in data.get("profiles", [])
        if isinstance(profile, dict)
    ]
    selected_profile_id = str(data.get("selected_profile_id") or "")
    if selected_profile_id and not any(profile["id"] == selected_profile_id for profile in profiles):
        selected_profile_id = ""
    if not selected_profile_id and profiles:
        selected_profile_id = profiles[0]["id"]

    return {
        "profiles": profiles,
        "selected_profile_id": selected_profile_id,
    }


def _read_state_unlocked() -> dict:
    if not os.path.exists(PREFERENCES_FILE):
        return _default_state()

    with open(PREFERENCES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _normalize_state(data)


def _write_state_unlocked(state: dict) -> dict:
    normalized = _normalize_state(state)
    os.makedirs(os.path.dirname(PREFERENCES_FILE), exist_ok=True)
    temp_file = f"{PREFERENCES_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=True, indent=2)
    os.replace(temp_file, PREFERENCES_FILE)
    return normalized


def _find_profile(state: dict, profile_id: str) -> dict | None:
    return next((profile for profile in state["profiles"] if profile["id"] == profile_id), None)


def _selected_profile(state: dict) -> dict | None:
    selected_profile_id = state.get("selected_profile_id", "")
    if not selected_profile_id:
        return None
    return _find_profile(state, selected_profile_id)


def _serialize_selected_fields(state: dict) -> dict:
    fields = _default_selected_fields()
    selected = _selected_profile(state)
    if selected:
        fields.update({
            "reference_clip": selected.get("reference_clip", ""),
            "ref_text": selected.get("ref_text", ""),
        })
    return fields


def get_clone_profiles_state() -> dict:
    with _preferences_lock:
        state = _read_state_unlocked()
        return _write_state_unlocked(state)


def get_clone_preferences() -> dict:
    state = get_clone_profiles_state()
    return {
        **_serialize_selected_fields(state),
        "selected_profile_id": state["selected_profile_id"],
        "profiles": state["profiles"],
    }


def create_clone_profile(name: str, reference_clip: str, ref_text: str) -> dict:
    now = _timestamp()
    profile = _normalize_profile({
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "reference_clip": reference_clip,
        "ref_text": ref_text,
        "created_at": now,
        "updated_at": now,
    })
    with _preferences_lock:
        state = _read_state_unlocked()
        state["profiles"].insert(0, profile)
        state["selected_profile_id"] = profile["id"]
        return _write_state_unlocked(state)


def update_clone_profile(profile_id: str, name: str, reference_clip: str, ref_text: str) -> dict:
    with _preferences_lock:
        state = _read_state_unlocked()
        profile = _find_profile(state, profile_id)
        if profile is None:
            raise KeyError(profile_id)

        profile.update({
            "name": name.strip() or profile["name"],
            "reference_clip": reference_clip,
            "ref_text": ref_text,
            "updated_at": _timestamp(),
        })
        state["selected_profile_id"] = profile_id
        return _write_state_unlocked(state)


def delete_clone_profile(profile_id: str) -> dict:
    with _preferences_lock:
        state = _read_state_unlocked()
        remaining = [profile for profile in state["profiles"] if profile["id"] != profile_id]
        if len(remaining) == len(state["profiles"]):
            raise KeyError(profile_id)

        state["profiles"] = remaining
        if state["selected_profile_id"] == profile_id:
            state["selected_profile_id"] = remaining[0]["id"] if remaining else ""
        return _write_state_unlocked(state)


def select_clone_profile(profile_id: str) -> dict:
    with _preferences_lock:
        state = _read_state_unlocked()
        if profile_id:
            profile = _find_profile(state, profile_id)
            if profile is None:
                raise KeyError(profile_id)
            state["selected_profile_id"] = profile_id
        else:
            state["selected_profile_id"] = ""
        return _write_state_unlocked(state)


def save_clone_preferences(reference_clip: str, ref_text: str) -> dict:
    with _preferences_lock:
        state = _read_state_unlocked()
        selected = _selected_profile(state)
        if selected is None:
            now = _timestamp()
            selected = _normalize_profile({
                "id": uuid.uuid4().hex[:12],
                "name": _profile_name_from_clip(reference_clip),
                "reference_clip": reference_clip,
                "ref_text": ref_text,
                "created_at": now,
                "updated_at": now,
            })
            state["profiles"].insert(0, selected)
            state["selected_profile_id"] = selected["id"]
        else:
            selected.update({
                "reference_clip": reference_clip,
                "ref_text": ref_text,
                "updated_at": _timestamp(),
            })
        saved = _write_state_unlocked(state)
    return {
        **_serialize_selected_fields(saved),
        "selected_profile_id": saved["selected_profile_id"],
        "profiles": saved["profiles"],
    }
