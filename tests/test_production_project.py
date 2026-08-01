from pathlib import Path
import shutil
from unittest.mock import patch

import pytest

from videotrans.util.production_project import (
    begin_stage, episode_name, import_original_video, isolated_work_dir, publish_file, publish_files,
    project_video, read_states, require_stage, scaffold_project, snapshot_files, update_stage,
    validate_project, verify_snapshot,
)


def test_scaffold_preserves_existing_wiki_and_updates_board(tmp_path):
    existing = tmp_path / "wiki/index.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("# 我的项目\n", encoding="utf-8")

    scaffold_project(tmp_path, 1)
    scaffold_project(tmp_path, 2)
    update_stage(tmp_path, 1, "中文识别", "已完成")

    assert existing.read_text(encoding="utf-8") == "# 我的项目\n"
    assert (tmp_path / ".raw/media/视频/第01集").is_dir()
    assert read_states(tmp_path, 1)["中文识别"][0] == "已完成"
    board = (tmp_path / "wiki/项目看板.md").read_text(encoding="utf-8")
    assert "第01集" in board and "第02集" in board and "已完成" in board


def test_work_dir_is_outside_project_and_publish_is_atomic(tmp_path):
    project = tmp_path / "project"
    work = isolated_work_dir(tmp_path / "tasks", project)
    source = work / "target/result.mp4"
    source.write_bytes(b"new video")
    destination = project / ".raw/media/视频/第01集/无字幕.mp4"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"old video")

    publish_file(source, destination)

    assert destination.read_bytes() == b"new video"
    assert not list(destination.parent.glob("*.tmp"))


def test_invalid_episode_and_overlapping_work_dir_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        episode_name("第一集")
    with pytest.raises(ValueError):
        isolated_work_dir(tmp_path / "project/.tasks", tmp_path / "project")


def test_project_validation_requires_wiki_contract_and_repairs_media_folder(tmp_path):
    with pytest.raises(ValueError, match="缺少"):
        validate_project(tmp_path)

    scaffold_project(tmp_path, 1)
    media = tmp_path / ".raw/media"
    shutil.rmtree(media)
    assert validate_project(tmp_path) == tmp_path.resolve()
    assert media.is_dir()


def test_original_video_is_imported_once_and_indexed(tmp_path):
    project, first, second = tmp_path / "project", tmp_path / "first.mp4", tmp_path / "second.mp4"
    scaffold_project(project, 1)
    first.write_bytes(b"first video")
    second.write_bytes(b"second video")

    imported = import_original_video(project, 1, first)
    assert imported.read_bytes() == b"first video"
    assert "[原视频](../.raw/media/视频/第01集/原视频.mp4)" in (
        project / "wiki/来源索引.md").read_text(encoding="utf-8")
    assert import_original_video(project, 1, first) == imported

    with pytest.raises(FileExistsError, match="已存在不同的原视频"):
        import_original_video(project, 1, second)

    assert project_video(project, 1) == imported


def test_publish_rejects_symlink_escape(tmp_path):
    project, outside = tmp_path / "project", tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (project / ".raw").symlink_to(outside, target_is_directory=True)
    source = tmp_path / "result.mp4"
    source.write_bytes(b"video")

    with pytest.raises(ValueError, match="路径越界"):
        publish_file(source, project / ".raw/result.mp4", project=project)

    assert not (outside / "result.mp4").exists()


def test_failed_publish_keeps_confirmed_output(tmp_path):
    destination = tmp_path / "无字幕.mp4"
    destination.write_bytes(b"confirmed")

    with pytest.raises(ValueError):
        publish_file(tmp_path / "missing.mp4", destination)

    assert destination.read_bytes() == b"confirmed"


def test_snapshot_rejects_changed_input(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("old", encoding="utf-8")
    snapshot = snapshot_files((source,))
    source.write_text("new", encoding="utf-8")

    with pytest.raises(RuntimeError, match="运行期间发生变化"):
        verify_snapshot(snapshot)


def test_stage_gate_rejects_unconfirmed_and_duplicate_run(tmp_path):
    scaffold_project(tmp_path, 1)
    with pytest.raises(ValueError, match="未知阶段状态"):
        update_stage(tmp_path, 1, "中文识别", "大概完成")
    with pytest.raises(ValueError, match="需要先达到：已确认"):
        require_stage(tmp_path, 1, "剧情翻译与轮次", ("已确认",))
    begin_stage(tmp_path, 1, "中文识别")
    with pytest.raises(ValueError, match="处理中"):
        begin_stage(tmp_path, 1, "中文识别")


def test_successful_upstream_change_invalidates_downstream_states(tmp_path):
    scaffold_project(tmp_path, 1)
    update_stage(tmp_path, 1, "英文克隆配音", "已完成")
    update_stage(tmp_path, 1, "配音字幕校准", "已确认")
    update_stage(tmp_path, 1, "最终合成", "已完成")

    update_stage(tmp_path, 1, "英文克隆配音", "已完成", invalidate_downstream=True)

    states = read_states(tmp_path, 1)
    assert states["英文克隆配音"][0] == "已完成"
    assert states["配音字幕校准"][0] == "未开始"
    assert states["最终合成"][0] == "未开始"


def test_group_publish_rolls_back_when_one_source_is_invalid(tmp_path):
    first, second = tmp_path / "old.wav", tmp_path / "old.srt"
    first.write_bytes(b"old audio")
    second.write_bytes(b"old subtitle")
    new = tmp_path / "new.wav"
    new.write_bytes(b"new audio")

    with pytest.raises(ValueError):
        publish_files(((new, first), (tmp_path / "missing.srt", second)))

    assert first.read_bytes() == b"old audio"
    assert second.read_bytes() == b"old subtitle"


def test_group_publish_rolls_back_after_partial_replace(tmp_path):
    first, second = tmp_path / "audio.wav", tmp_path / "subtitle.srt"
    new_first, new_second = tmp_path / "new.wav", tmp_path / "new.srt"
    first.write_bytes(b"old audio")
    second.write_bytes(b"old subtitle")
    new_first.write_bytes(b"new audio")
    new_second.write_bytes(b"new subtitle")

    from videotrans.util import production_project
    replace = production_project.os.replace

    def fail_second_publish(source, destination):
        if Path(destination) == second and str(source).endswith(".tmp"):
            raise OSError("simulated publish failure")
        return replace(source, destination)

    with patch("videotrans.util.production_project.os.replace", side_effect=fail_second_publish):
        with pytest.raises(OSError, match="simulated"):
            publish_files(((new_first, first), (new_second, second)))

    assert first.read_bytes() == b"old audio"
    assert second.read_bytes() == b"old subtitle"


def test_project_window_imports_original_video_before_recognition(tmp_path):
    from PySide6.QtWidgets import QApplication
    from videotrans.winform import fn_production_project

    app = QApplication.instance() or QApplication([])
    with patch.object(fn_production_project.params, "get", return_value=""):
        project = fn_production_project.ProductionProjectWindow()

    assert project.table.columnCount() == 4
    assert project.stage_pages.count() == 5
    project.select_stage(1)
    assert project.stage_pages.currentIndex() == 1

    scaffold_project(tmp_path, 1)
    project.project.setText(str(tmp_path))
    project.episode.addItem("第01集")
    project.refresh()
    assert not project.start_recognition.isEnabled()

    original = tmp_path / ".raw/media/视频/第01集/原视频.mp4"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"video")
    project.refresh()
    assert project.start_recognition.isEnabled()

    project.close()
