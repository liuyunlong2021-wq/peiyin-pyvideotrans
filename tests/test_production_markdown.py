import json
from pathlib import Path
import wave

import pytest

from videotrans.util.production_markdown import (
    build_voice_library_snapshot, export_recognition_srt, export_translation_task,
    import_recognition_srt, import_translation_srt, set_document_status,
    write_calibration_page, write_dubbing_page,
)
from videotrans.util.production_project import scaffold_project


SOURCE = """1
00:00:01,000 --> 00:00:02,500
你好 | 世界

2
00:00:02,600 --> 00:00:04,000
快走
"""

TARGET = """1
00:00:01,000 --> 00:00:02,500
Hello | world

2
00:00:02,600 --> 00:00:04,000
Let's go
"""


def test_recognition_markdown_roundtrip(tmp_path):
    scaffold_project(tmp_path, 1)
    source = tmp_path / "source.srt"
    source.write_text(SOURCE, encoding="utf-8")

    page = import_recognition_srt(tmp_path, 1, source, "SenseVoiceSmall")
    exported = export_recognition_srt(tmp_path, 1)

    assert "你好 \\| 世界" in page.read_text(encoding="utf-8")
    assert "你好 | 世界" in exported.read_text(encoding="utf-8")


def test_recognition_rejects_empty_srt_and_reversed_time(tmp_path):
    scaffold_project(tmp_path, 1)
    empty = tmp_path / "empty.srt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="为空或格式无效"):
        import_recognition_srt(tmp_path, 1, empty)

    page = tmp_path / "wiki/集数/第01集/中文识别.md"
    page.write_text(
        "# 识别\n\n| 行 | 开始 | 结束 | 中文原文 | 音频说话人 | 声音事件 |\n"
        "|---:|---:|---:|---|---|---|\n"
        "| 1 | 00:00:02,000 | 00:00:01,000 | 测试 | Speaker1 | speech |\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="结束时间必须晚于开始时间"):
        export_recognition_srt(tmp_path, 1)


def test_document_status_is_updated_in_place(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("# Page\n\n- 状态：待校对\n", encoding="utf-8")

    set_document_status(page, "已确认")

    assert "- 状态：已确认" in page.read_text(encoding="utf-8")


def test_translation_exports_existing_clone_contract(tmp_path):
    scaffold_project(tmp_path, 1)
    source, target = tmp_path / "source.srt", tmp_path / "target.srt"
    source.write_text(SOURCE, encoding="utf-8")
    target.write_text(TARGET, encoding="utf-8")
    import_recognition_srt(tmp_path, 1, source)

    page = import_translation_srt(
        tmp_path, 1, target, "gemini-3.6-flash",
        assignments=["林夏", "林夏"], emotions=["happy", "happy"], turns=[False, True])
    assert not (tmp_path / "wiki/角色/林夏/配音档案.md").exists()
    output = export_translation_task(tmp_path, 1).parent

    assert "[[角色/林夏/配音档案]]" in page.read_text(encoding="utf-8")
    assert (tmp_path / "wiki/角色/林夏/配音档案.md").is_file()
    assert "[[集数/第01集/翻译与轮次]]" in (
        tmp_path / "wiki/角色/林夏/角色档案.md").read_text(encoding="utf-8")
    assert json.loads((output / "speaker_assignments.json").read_text()) == ["林夏", "林夏"]
    assert json.loads((output / "turns.json").read_text()) == [False, True]
    assert "Hello | world" in (output / "英文.srt").read_text(encoding="utf-8")


def test_translation_rejects_bad_count_and_join_conflict(tmp_path):
    scaffold_project(tmp_path, 1)
    source, target = tmp_path / "source.srt", tmp_path / "target.srt"
    source.write_text(SOURCE, encoding="utf-8")
    target.write_text(TARGET, encoding="utf-8")
    import_recognition_srt(tmp_path, 1, source)

    with pytest.raises(ValueError, match="数组必须与字幕行数一致"):
        import_translation_srt(tmp_path, 1, target, assignments=["林夏"])

    page = import_translation_srt(tmp_path, 1, target, assignments=["林夏", "陈阳"], turns=[False, True])
    with pytest.raises(ValueError, match="第2行接上句"):
        export_translation_task(tmp_path, 1)

    text = page.read_text(encoding="utf-8").replace(
        "| 1 | [[角色/林夏/配音档案]] | neutral | 否 |",
        "| 1 | [[角色/林夏/配音档案]] | neutral | 是 |")
    page.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="第1行不能接上句"):
        export_translation_task(tmp_path, 1)


def test_voice_profile_builds_runtime_snapshot(tmp_path):
    import numpy as np

    profile = tmp_path / "wiki/角色/林夏/配音档案.md"
    audio = tmp_path / ".raw/media/音频/角色/林夏/开心/参考01.wav"
    audio.parent.mkdir(parents=True)
    with wave.open(audio.as_posix(), "wb") as output:
        output.setparams((1, 2, 16000, 16000, "NONE", "not compressed"))
        output.writeframes(b"\0\0" * 16000)
    np.save(audio.with_suffix(".npy"), np.array([1, 0], dtype="float32"))
    profile.parent.mkdir(parents=True)
    profile.write_text(
        "# 林夏配音档案\n\n"
        "| 情绪 | 参考音频 | 参考文本 | 来源 | 时长 | 状态 | 备注 |\n"
        "|---|---|---|---|---:|---|---|\n"
        "| happy | [参考01.wav](../../../.raw/media/音频/角色/林夏/开心/参考01.wav) | 你好 | [[集数/第01集/英文配音]] | 6.2秒 | 已确认 | 清晰 |\n",
        encoding="utf-8")

    snapshot = build_voice_library_snapshot(tmp_path, tmp_path / "runtime-library")
    library = json.loads((snapshot / "library.json").read_text(encoding="utf-8"))

    assert library["characters"][0]["id"] == "林夏"
    assert (snapshot / library["characters"][0]["performances"][0]["audio"]).is_file()
    assert (snapshot / library["characters"][0]["performances"][0]["embedding"]).is_file()

    profile.write_text(profile.read_text(encoding="utf-8").replace("| 你好 |", "|  |"), encoding="utf-8")
    with pytest.raises(ValueError, match="缺少参考文本"):
        build_voice_library_snapshot(tmp_path, tmp_path / "invalid-library")


def test_dubbing_and_calibration_pages_link_published_media(tmp_path):
    scaffold_project(tmp_path, 1)
    from videotrans.util.production_markdown import ensure_character_pages
    ensure_character_pages(tmp_path, "林夏")
    queue = [{
        "line": 1, "_speaker": "林夏", "emotion": "happy",
        "_subtitle_items": [{"line": 1}, {"line": 2}],
    }]
    dubbing = write_dubbing_page(
        tmp_path, 1, queue, [Path("turn-001.wav")], [Path("reference-001.wav")])
    calibration = write_calibration_page(tmp_path, 1, final=True)

    text = dubbing.read_text(encoding="utf-8")
    assert "[[角色/林夏/配音档案]]" in text
    assert "| 1 | 1-2 |" in text
    assert "turn-001.wav" in text and "reference-001.wav" in text
    assert "最终视频.mp4" in calibration.read_text(encoding="utf-8")
