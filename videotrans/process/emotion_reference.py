"""emotion2vec analysis and same-character reference selection."""

import json
import shutil
import traceback
from pathlib import Path


def _value(result, *names):
    if not isinstance(result, dict):
        return None
    for name in names:
        if name in result:
            return result[name]
    return None


def _first(value):
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def _normalize_emotion(value):
    value = str(value or "neutral").strip().lower()
    return value.rsplit("/", 1)[-1]


def _analyze(model, filename):
    import numpy as np
    result = model.generate(input=filename, granularity="utterance", extract_embedding=True)
    result = _first(result) or {}
    labels = _value(result, "labels", "label") or []
    scores = _value(result, "scores", "score") or []
    embedding = _value(result, "feats", "embedding", "embeddings")
    if isinstance(labels, str):
        labels = [labels]
    scores = np.asarray(scores, dtype="float32").reshape(-1).tolist()
    emotion = _normalize_emotion(labels[max(range(len(scores)), key=scores.__getitem__)]) \
        if labels and len(labels) == len(scores) else str(_first(labels) or "neutral")
    if embedding is None:
        return {"emotion": emotion, "scores": scores, "embedding": []}
    try:
        vector = np.asarray(embedding, dtype="float32")
        if vector.ndim > 1:
            vector = vector[0]
        vector = vector.reshape(-1)
        return {"emotion": emotion, "scores": scores,
                "embedding": vector.tolist()}
    except (TypeError, ValueError):
        return {"emotion": emotion, "scores": scores, "embedding": []}


def analyze_and_select(queue_file, library_dir="", add_current=False, model_dir=None,
                       episode="", emotion_file=""):
    """Update queue refs in-place; failures are returned to the caller, not raised."""
    try:
        from funasr import AutoModel
        from videotrans.util.voice_library import add_performance, find_reference
        model = AutoModel(model=model_dir or "iic/emotion2vec_plus_large",
                          hub="ms", disable_update=True, disable_log=True,
                          device="cpu")
        queue = json.loads(Path(queue_file).read_text(encoding="utf-8"))
        overrides = {}
        try:
            saved = json.loads(Path(emotion_file).read_text(encoding="utf-8")) \
                if emotion_file and Path(emotion_file).is_file() else []
            overrides = {index + 1: _normalize_emotion(value) for index, value in enumerate(saved)}
        except (OSError, json.JSONDecodeError):
            pass
        for item in queue:
            ref = Path(str(item.get("ref_wav", "")))
            character = str(item.get("_speaker", "")).strip()
            if not character or not ref.is_file():
                continue
            analysis = _analyze(model, str(ref))
            analysis["emotion"] = overrides.get(int(item.get("line", 0)), analysis["emotion"])
            item["emotion"] = analysis["emotion"]
            item["emotion_scores"] = analysis["scores"]
            item["emotion_embedding"] = analysis["embedding"]
            duration = int(item.get("end_time_source", 0) - item.get("start_time_source", 0))
            if add_current and duration >= 3000 and analysis["embedding"]:
                add_performance(library_dir, character, ref, item.get("ref_text", ""),
                                analysis["emotion"], analysis["scores"], analysis["embedding"],
                                episode, item.get("line"),
                                (item.get("_subtitle_items") or [{}])[-1].get("line", item.get("line")),
                                duration)
        for item in queue:
            character = str(item.get("_speaker", "")).strip()
            duration = int(item.get("end_time_source", 0) - item.get("start_time_source", 0))
            analysis = {"emotion": item.get("emotion", ""),
                        "embedding": item.get("emotion_embedding", [])}
            if duration < 3000 and analysis["embedding"]:
                selected = find_reference(library_dir, character, analysis["emotion"],
                                          analysis["embedding"])
                if selected:
                    item["original_ref_wav"] = str(item.get("ref_wav", ""))
                    item["ref_wav"] = selected["audio"]
                    item["ref_text"] = selected["text"] or item.get("ref_text", "")
                    item["reference_source"] = selected["id"]
        Path(queue_file).write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
        return True, None
    except Exception as error:
        return False, f"{error}\n{traceback.format_exc()}"
