import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest

from videotrans.util.voice_library import add_performance, character_ids, find_reference
from videotrans.process.emotion_reference import _analyze, analyze_and_select


def test_reference_search_stays_inside_character(tmp_path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF-test")
    add_performance(tmp_path / "library", "alice", source, "hello", "angry", [], [1, 0])
    add_performance(tmp_path / "library", "bob", source, "wrong voice", "angry", [], [1, 0])

    selected = find_reference(tmp_path / "library", "alice", "angry", [0.9, 0.1])

    assert selected["text"] == "hello"
    assert "alice" in selected["id"]
    assert character_ids(tmp_path / "library") == ["alice", "bob"]


def test_reference_search_skips_bad_embedding(tmp_path):
    library = tmp_path / "library"
    (library / "refs").mkdir(parents=True)
    (library / "embeddings").mkdir()
    (library / "refs" / "ok.wav").write_bytes(b"RIFF-test")
    np.save(library / "embeddings" / "bad.npy", np.array([1, 2, 3]))
    (library / "library.json").write_text(json.dumps({
        "version": 1,
        "characters": [{"id": "alice", "performances": [{
            "id": "bad", "audio": "refs/ok.wav", "embedding": "embeddings/bad.npy",
            "emotion": "happy", "approved": True
        }]}]
    }), encoding="utf-8")

    assert find_reference(library, "alice", "happy", [1, 0]) is None


def test_emotion_result_keeps_full_embedding_and_uses_highest_score():
    class Model:
        def generate(self, **_):
            return [{"labels": ["angry", "happy"], "scores": [0.2, 0.8],
                     "feats": [0.1, 0.2, 0.3]}]

    result = _analyze(Model(), "test.wav")

    assert result["emotion"] == "happy"
    assert result["embedding"] == pytest.approx([0.1, 0.2, 0.3])


def test_current_long_reference_is_available_to_earlier_short_line(tmp_path, monkeypatch):
    short = tmp_path / "short.wav"
    long = tmp_path / "long.wav"
    short.write_bytes(b"RIFF-short")
    long.write_bytes(b"RIFF-long")
    queue = [{
        "line": 1, "_speaker": "alice", "ref_wav": str(short), "ref_text": "short",
        "start_time_source": 0, "end_time_source": 1000,
    }, {
        "line": 2, "_speaker": "alice", "ref_wav": str(long), "ref_text": "long",
        "start_time_source": 1000, "end_time_source": 5000,
    }]
    queue_file = tmp_path / "queue.json"
    queue_file.write_text(json.dumps(queue), encoding="utf-8")

    class Model:
        def __init__(self, **_):
            pass

        def generate(self, **_):
            return [{"labels": ["angry"], "scores": [1], "feats": [1, 0]}]

    monkeypatch.setitem(sys.modules, "funasr", types.SimpleNamespace(AutoModel=Model))
    ok, error = analyze_and_select(queue_file, tmp_path / "library", add_current=True)
    saved = json.loads(queue_file.read_text(encoding="utf-8"))

    assert ok is True and error is None
    assert saved[0]["ref_text"] == "long"
    assert saved[0]["reference_source"].startswith("alice_angry")
