"""Small, file-backed voice performance library used by clone dubbing."""

import json
import re
import shutil
from pathlib import Path


def library_path(folder):
    return Path(folder).expanduser() if folder else None


def load_library(folder):
    folder = library_path(folder)
    if not folder:
        return {"version": 1, "characters": []}
    file = folder / "library.json"
    try:
        value = json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}
    except (OSError, json.JSONDecodeError):
        value = {}
    if not isinstance(value, dict) or not isinstance(value.get("characters"), list):
        value = {}
    value.setdefault("version", 1)
    value.setdefault("characters", [])
    return value


def save_library(folder, value):
    folder = library_path(folder)
    if not folder:
        return
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "refs").mkdir(exist_ok=True)
    (folder / "embeddings").mkdir(exist_ok=True)
    (folder / "library.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def character_ids(folder):
    return [str(item.get("id", "")).strip() for item in load_library(folder)["characters"]
            if str(item.get("id", "")).strip()]


def _character(value, create=False):
    value = str(value or "").strip()
    if not value:
        return None
    return value


def _safe(value):
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("._")
    return value or "character"


def add_performance(folder, character_id, source_wav, text, emotion, scores, embedding,
                    episode="", line_start=None, line_end=None, duration_ms=0):
    """Copy one approved reference into the library and return its record."""
    folder = library_path(folder)
    character_id = _character(character_id)
    source = Path(source_wav) if source_wav else None
    if not folder or not character_id or not source or not source.is_file():
        return None
    value = load_library(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "refs").mkdir(exist_ok=True)
    (folder / "embeddings").mkdir(exist_ok=True)
    character = next((item for item in value["characters"]
                      if item.get("id") == character_id), None)
    if character is None:
        character = {"id": character_id, "name": character_id,
                     "identity_reference": "", "performances": []}
        value["characters"].append(character)
    performances = character.setdefault("performances", [])
    source_key = {"episode": str(episode or ""), "line_start": line_start,
                  "line_end": line_end}
    existing = next((item for item in performances if item.get("source") == source_key), None)
    if existing:
        return existing
    stem = f"{_safe(character_id)}_{_safe(emotion or 'neutral')}_{len(performances) + 1:02d}"
    wav_rel = f"refs/{stem}{source.suffix.lower() or '.wav'}"
    wav_dest = folder / wav_rel
    wav_dest.parent.mkdir(parents=True, exist_ok=True)
    if not wav_dest.exists():
        shutil.copy2(source, wav_dest)
    embedding_rel = ""
    if embedding:
        import numpy as np
        embedding_rel = f"embeddings/{stem}.npy"
        np.save(folder / embedding_rel, np.asarray(embedding, dtype="float32"))
    record = {
        "id": stem,
        "audio": wav_rel,
        "embedding": embedding_rel,
        "text": str(text or ""),
        "duration_ms": int(duration_ms),
        "emotion": str(emotion or "neutral"),
        "events": [],
        "source": source_key,
        "approved": True,
    }
    performances.append(record)
    save_library(folder, value)
    return record


def find_reference(folder, character_id, emotion, embedding):
    """Return the closest approved reference for one character, if any."""
    import numpy as np
    folder = library_path(folder)
    if not folder or not embedding:
        return None
    candidates = []
    value = load_library(folder)
    character = next((item for item in value["characters"]
                      if item.get("id") == character_id), None)
    if not character:
        return None
    wanted = str(emotion or "").lower()
    query = np.asarray(embedding, dtype="float32").reshape(-1)
    qnorm = float(np.linalg.norm(query))
    if not qnorm:
        return None
    for item in character.get("performances", []):
        if item.get("approved") is not True:
            continue
        audio = folder / str(item.get("audio", ""))
        emb_file = folder / str(item.get("embedding", ""))
        if not audio.is_file() or not emb_file.is_file():
            continue
        try:
            candidate = np.load(emb_file).reshape(-1).astype("float32")
            if candidate.size != query.size:
                continue
            score = float(np.dot(query, candidate) /
                          (qnorm * max(float(np.linalg.norm(candidate)), 1e-8)))
            if wanted and str(item.get("emotion", "")).lower() == wanted:
                score += 0.05
            candidates.append((score, item, audio))
        except (OSError, ValueError):
            continue
    if not candidates:
        return None
    _, item, audio = max(candidates, key=lambda value: value[0])
    return {"audio": str(audio), "text": str(item.get("text", "")),
            "id": str(item.get("id", "")), "emotion": item.get("emotion", "")}
