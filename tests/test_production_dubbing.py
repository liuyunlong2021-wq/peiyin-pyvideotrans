from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from videotrans.configure import config
import pytest

from videotrans.configure.excepts import DubbingSrtError
from videotrans.task._stage_dubbing import DubbingMixin
from videotrans.task.production_dubbing import (
    compose_project_video, confirm_calibrated_subtitle, prepare_dubbing_workspace,
)
from videotrans.tts import QWEN3LOCAL_TTS
from videotrans.util.production_markdown import import_recognition_srt, import_translation_srt
from videotrans.util.production_project import scaffold_project, update_stage


SRT = """1
00:00:00,000 --> 00:00:01,000
测试
"""


def test_dubbing_workspace_is_isolated_and_uses_existing_contract(tmp_path):
    project, source, target, video = tmp_path / "project", tmp_path / "zh.srt", tmp_path / "en.srt", tmp_path / "input.mp4"
    source.write_text(SRT, encoding="utf-8")
    target.write_text(SRT.replace("测试", "Test"), encoding="utf-8")
    video.write_bytes(b"video")
    scaffold_project(project, 1)
    import_recognition_srt(project, 1, source)
    import_translation_srt(project, 1, target, assignments=["林夏"])

    with patch.object(config, "TEMP_DIR", (tmp_path / "tasks").as_posix()), \
            patch("videotrans.task.production_dubbing.runffmpeg") as ffmpeg:
        def create_audio(command):
            Path(command[-1]).write_bytes(b"RIFF-source")
        ffmpeg.side_effect = create_audio
        work, zh, en, wav = prepare_dubbing_workspace(project, "第01集", video)

    assert project not in work.parents and work not in project.parents
    assert zh.is_file() and en.is_file() and wav.is_file()
    assert (en.parent / "turns.json").is_file()
    assert (en.parent / "voice_library.json").is_file()


def test_final_composition_uses_isolated_output_and_publishes(tmp_path):
    project = tmp_path / "project"
    scaffold_project(project, 1)
    video = project / ".raw/media/视频/第01集/无字幕.mp4"
    audio = project / ".raw/media/音频/第01集/英文配音.wav"
    subtitle = project / ".raw/media/文件/第01集/英文-已确认.srt"
    for path, data in ((video, b"video"), (audio, b"audio"), (subtitle, SRT.encode())):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    update_stage(project, 1, "英文克隆配音", "已完成")
    update_stage(project, 1, "配音字幕校准", "已确认")

    with patch.object(config, "TEMP_DIR", (tmp_path / "tasks").as_posix()), \
            patch("videotrans.task.production_dubbing.get_video_info", return_value={"width": 1080, "height": 1920}), \
            patch("videotrans.task.production_dubbing.set_ass_font") as ass_font, \
            patch("videotrans.task.production_dubbing.validate_media"), \
            patch("videotrans.task.production_dubbing.runffmpeg") as ffmpeg:
        def make_ass(path, *_):
            ass = Path(path).with_suffix(".ass")
            ass.write_text("ass", encoding="utf-8")
            return ass.as_posix()
        def make_video(command, **_):
            Path(command[-1]).write_bytes(b"final")
        ass_font.side_effect, ffmpeg.side_effect = make_ass, make_video
        work, output = compose_project_video(project, "第01集")

    assert project not in work.parents and work not in project.parents
    assert output.read_bytes() == b"final"
    page = project / "wiki/集数/第01集/字幕校准与合成.md"
    assert "最终视频.mp4" in page.read_text(encoding="utf-8")


def test_cancelled_composition_keeps_previous_video_and_page(tmp_path):
    project = tmp_path / "project"
    scaffold_project(project, 1)
    video = project / ".raw/media/视频/第01集/无字幕.mp4"
    audio = project / ".raw/media/音频/第01集/英文配音.wav"
    subtitle = project / ".raw/media/文件/第01集/英文-已确认.srt"
    output = project / ".raw/media/视频/第01集/最终视频.mp4"
    page = project / "wiki/集数/第01集/字幕校准与合成.md"
    for path, data in ((video, b"video"), (audio, b"audio"), (subtitle, SRT.encode()),
                       (output, b"confirmed video"), (page, b"confirmed page")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    update_stage(project, 1, "英文克隆配音", "已完成")
    update_stage(project, 1, "配音字幕校准", "已确认")

    with patch.object(config, "TEMP_DIR", (tmp_path / "tasks").as_posix()), \
            patch("videotrans.task.production_dubbing.get_video_info", return_value={"width": 1080, "height": 1920}), \
            patch("videotrans.task.production_dubbing.set_ass_font") as ass_font, \
            patch("videotrans.task.production_dubbing.runffmpeg") as ffmpeg:
        def make_ass(path, *_):
            ass = Path(path).with_suffix(".ass")
            ass.write_text("ass", encoding="utf-8")
            return ass.as_posix()
        def make_video(command, **_):
            Path(command[-1]).write_bytes(b"new video")
        ass_font.side_effect, ffmpeg.side_effect = make_ass, make_video
        with pytest.raises(InterruptedError, match="未发布"):
            compose_project_video(project, "第01集", cancelled=lambda: True)

    assert output.read_bytes() == b"confirmed video"
    assert page.read_bytes() == b"confirmed page"


def test_project_mode_rejects_voice_library_failure(tmp_path):
    target, cache = tmp_path / "target", tmp_path / "cache"
    target.mkdir()
    cache.mkdir()
    (target / "voice_library.json").write_text(
        '{"path":"voice-library","add_current":false}', encoding="utf-8")
    task = SimpleNamespace(
        strict_voice_reference=True,
        cfg=SimpleNamespace(
            target_dir=target.as_posix(), cache_folder=cache.as_posix(),
            tts_type=QWEN3LOCAL_TTS, noextname="第01集"),
        queue_tts=[],
        _process_callback=lambda _data: None,
        _new_process=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("analysis failed")),
    )

    with patch("videotrans.util.help_down.check_and_down_ms"), \
            pytest.raises(DubbingSrtError, match="已阻止配音"):
        DubbingMixin._apply_voice_library(task)

    task.strict_voice_reference = False
    with patch("videotrans.util.help_down.check_and_down_ms"):
        DubbingMixin._apply_voice_library(task)


def test_confirm_subtitle_rejects_invalid_srt(tmp_path):
    project, subtitle = tmp_path / "project", tmp_path / "invalid.srt"
    scaffold_project(project, 1)
    subtitle.write_text("not an srt", encoding="utf-8")
    update_stage(project, 1, "英文克隆配音", "已完成")

    with pytest.raises(ValueError, match="为空或格式无效"):
        confirm_calibrated_subtitle(project, "第01集", subtitle)
