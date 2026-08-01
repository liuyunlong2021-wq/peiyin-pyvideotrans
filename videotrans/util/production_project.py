import os
import hashlib
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


STAGES = (
    ("中文识别", "[[集数/{episode}/中文识别]]"),
    ("剧情翻译与轮次", "[[集数/{episode}/翻译与轮次]]"),
    ("英文克隆配音", "[[集数/{episode}/英文配音]]"),
    ("配音字幕校准", "[[集数/{episode}/字幕校准与合成]]"),
    ("最终合成", "[[集数/{episode}/字幕校准与合成]]"),
)
STAGE_STATUSES = ("未开始", "处理中", "待校对", "已确认", "已完成", "失败")


def episode_name(value):
    text = str(value).strip()
    if text.startswith("第") and text.endswith("集"):
        text = text[1:-1]
    if not text.isdigit() or int(text) < 1:
        raise ValueError("集数必须是大于 0 的数字")
    return f"第{int(text):02d}集"


def _write_missing(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def scaffold_project(root, episode=1):
    root = Path(root).expanduser().resolve()
    episode = episode_name(episode)
    wiki = root / "wiki"
    media = root / ".raw/media"
    for folder in (
        wiki / "集数" / episode,
        wiki / "角色",
        wiki / "制作规范",
        media / "视频" / episode,
        media / "音频" / episode,
        media / "图片",
        media / "文件" / episode,
    ):
        folder.mkdir(parents=True, exist_ok=True)

    _write_missing(wiki / "index.md", "# 制作项目\n\n- [[项目看板]]\n- [[来源索引]]\n")
    _write_missing(wiki / "hot.md", "# 当前重点\n")
    _write_missing(wiki / "log.md", "# 制作日志\n")
    _write_missing(wiki / "来源索引.md", "# 来源索引\n\n| Wiki 文档 | 原始材料 | 说明 |\n|---|---|---|\n")
    for name in ("识别与翻译", "声音克隆", "字幕与合成"):
        _write_missing(wiki / "制作规范" / f"{name}.md", f"# {name}\n")
    ensure_episode(root, episode)
    refresh_board(root)
    return root, episode


def validate_project(root):
    root = Path(root).expanduser().resolve()
    missing = [path for path in (root / "wiki/index.md", root / "wiki/来源索引.md") if not path.is_file()]
    if missing:
        raise ValueError(f"所选目录不是制作项目，缺少：{missing[0]}")
    (root / ".raw/media").mkdir(parents=True, exist_ok=True)
    return root


def import_original_video(root, episode, source):
    root, episode, source = validate_project(root), episode_name(episode), Path(source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"原视频不存在：{source}")
    folder = root / ".raw/media/视频" / episode
    folder.mkdir(parents=True, exist_ok=True)
    existing = next(folder.glob("原视频.*"), None)
    destination = existing or folder / f"原视频{source.suffix.lower() or '.mp4'}"
    if destination.resolve() != source:
        if destination.exists():
            if _file_digest(destination) != _file_digest(source):
                raise FileExistsError(f"{episode}已存在不同的原视频，请新建集数：{destination}")
        else:
            publish_file(source, destination, project=root)
    index = root / "wiki/来源索引.md"
    link = f"[原视频](../.raw/media/视频/{episode}/{destination.name})"
    text = index.read_text(encoding="utf-8")
    if link not in text:
        index.write_text(
            text.rstrip() + f"\n| [[集数/{episode}/状态]] | {link} | 原始视频 |\n", encoding="utf-8")
    return destination


def project_video(root, episode):
    folder = Path(root) / ".raw/media/视频" / episode_name(episode)
    for name in ("无字幕.mp4", "原视频.mp4"):
        path = folder / name
        if path.is_file():
            return path
    return folder / "原视频.mp4"


def ensure_episode(root, episode):
    root = Path(root).expanduser().resolve()
    episode = episode_name(episode)
    episode_wiki = root / "wiki/集数" / episode
    for folder in (
        episode_wiki,
        root / ".raw/media/视频" / episode,
        root / ".raw/media/音频" / episode,
        root / ".raw/media/文件" / episode,
    ):
        folder.mkdir(parents=True, exist_ok=True)
    _write_missing(episode_wiki / "状态.md", _status_document(episode))
    _write_missing(episode_wiki / "中文识别.md", f"# {episode}中文识别\n\n- 状态：未开始\n")
    _write_missing(episode_wiki / "翻译与轮次.md", f"# {episode}翻译与轮次\n\n- 状态：未开始\n")
    _write_missing(episode_wiki / "英文配音.md", f"# {episode}英文配音\n\n- 状态：未开始\n")
    _write_missing(episode_wiki / "字幕校准与合成.md", f"# {episode}字幕校准与合成\n\n- 状态：未开始\n")
    return episode


def _status_document(episode, states=None):
    states = states or {}
    lines = [f"# {episode}制作状态", "", "| 阶段 | 状态 | 产物 | 更新时间 |", "|---|---|---|---|"]
    for stage, output in STAGES:
        status, updated = states.get(stage, ("未开始", "-"))
        lines.append(f"| {stage} | {status} | {output.format(episode=episode)} | {updated} |")
    return "\n".join(lines) + "\n"


def read_states(root, episode):
    path = Path(root) / "wiki/集数" / episode_name(episode) / "状态.md"
    states = {}
    if not path.is_file():
        return states
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] in dict(STAGES):
            states[cells[0]] = (cells[1], cells[3])
    return states


def update_stage(root, episode, stage, status, invalidate_downstream=False):
    if stage not in dict(STAGES):
        raise ValueError(f"未知阶段：{stage}")
    if status not in STAGE_STATUSES:
        raise ValueError(f"未知阶段状态：{status}")
    episode = ensure_episode(root, episode)
    states = read_states(root, episode)
    states[stage] = (status, datetime.now().strftime("%Y-%m-%d %H:%M"))
    if invalidate_downstream:
        stage_names = [name for name, _ in STAGES]
        for downstream in stage_names[stage_names.index(stage) + 1:]:
            states[downstream] = ("未开始", "-")
    (Path(root) / "wiki/集数" / episode / "状态.md").write_text(
        _status_document(episode, states), encoding="utf-8")
    refresh_board(root)


def require_stage(root, episode, stage, allowed):
    status = read_states(root, episode_name(episode)).get(stage, ("未开始", "-"))[0]
    if status not in allowed:
        expected = "、".join(allowed)
        raise ValueError(f"{stage}当前为“{status}”，需要先达到：{expected}")
    return status


def begin_stage(root, episode, stage):
    require_stage(root, episode, stage, ("未开始", "待校对", "已确认", "已完成", "失败"))
    update_stage(root, episode, stage, "处理中")


@contextmanager
def stage_execution(root, episode, stage):
    begin_stage(root, episode, stage)
    try:
        yield
    except Exception:
        try:
            update_stage(root, episode, stage, "失败")
        except Exception:
            pass
        raise


def check_cancelled(cancelled=None):
    if cancelled and cancelled():
        raise InterruptedError("任务已取消，未发布任何正式产物")


def _file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_files(paths):
    """Capture the small set of user-owned inputs a stage is about to consume."""
    snapshot = []
    for value in paths:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"快照输入不存在：{path}")
        digest = _file_digest(path)
        stat = path.stat()
        snapshot.append((path.as_posix(), stat.st_size, stat.st_mtime_ns, digest))
    return tuple(snapshot)


def verify_snapshot(snapshot):
    for name, size, mtime_ns, digest in snapshot:
        path = Path(name)
        if not path.is_file():
            raise RuntimeError(f"任务输入在运行期间被删除：{path}")
        stat = path.stat()
        current = _file_digest(path)
        if (stat.st_size, stat.st_mtime_ns, current) != (size, mtime_ns, digest):
            raise RuntimeError(f"任务输入在运行期间发生变化，请重新运行：{path}")


def refresh_board(root):
    root = Path(root).expanduser().resolve()
    episodes = sorted((root / "wiki/集数").glob("第*集"))
    lines = ["# 项目看板", "", "| 集数 | 去字幕 | 识别 | 翻译校对 | 配音 | 字幕校准 | 合成 |", "|---|---|---|---|---|---|---|"]
    for folder in episodes:
        states = read_states(root, folder.name)
        values = [states.get(stage, ("未开始", "-"))[0] for stage, _ in STAGES]
        lines.append(f"| [[集数/{folder.name}/状态|{folder.name}]] | " + " | ".join(values) + " |")
    path = root / "wiki/项目看板.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def isolated_work_dir(temp_root, project_root):
    work = Path(temp_root).expanduser().resolve() / "production-project" / uuid.uuid4().hex
    project = Path(project_root).expanduser().resolve()
    if project == work or project in work.parents or work in project.parents:
        raise ValueError("任务工作目录必须与项目目录隔离")
    (work / "target").mkdir(parents=True)
    (work / "cache").mkdir()
    return work


def _require_project_path(project, path):
    project, path = Path(project).resolve(), Path(path).resolve()
    if path != project and project not in path.parents:
        raise ValueError(f"项目产物路径越界：{path}")
    return path


def publish_file(source, destination, project=None):
    source, destination = Path(source), Path(destination)
    if project:
        destination = _require_project_path(project, destination)
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError(f"任务产物不存在或为空：{source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source, pending)
        os.replace(pending, destination)
    finally:
        pending.unlink(missing_ok=True)
    return destination


def publish_files(files, project=None):
    pairs = [(Path(source), Path(destination)) for source, destination in files]
    if project:
        pairs = [(source, _require_project_path(project, destination)) for source, destination in pairs]
    for source, _ in pairs:
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError(f"任务产物不存在或为空：{source}")
    pending, backups, published = [], [], []
    try:
        for source, destination in pairs:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
            shutil.copy2(source, temp)
            pending.append((temp, destination))
        for temp, destination in pending:
            backup = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.bak")
            if destination.exists():
                os.replace(destination, backup)
                backups.append((backup, destination))
            os.replace(temp, destination)
            published.append(destination)
    except Exception:
        backed_up = {destination for _, destination in backups}
        for destination in published:
            if destination not in backed_up:
                destination.unlink(missing_ok=True)
        for backup, destination in reversed(backups):
            destination.unlink(missing_ok=True)
            os.replace(backup, destination)
        raise
    finally:
        for temp, _ in pending:
            temp.unlink(missing_ok=True)
        for backup, _ in backups:
            backup.unlink(missing_ok=True)
    return [destination for _, destination in pairs]


def validate_media(path, video=False, audio=False):
    from videotrans.util.help_ffmpeg import get_video_info

    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"任务产物不存在或为空：{path}")
    info = get_video_info(path.as_posix())
    if video and info.get("video_streams", 0) < 1:
        raise ValueError(f"任务产物没有视频流：{path}")
    if audio and info.get("streams_audio", 0) < 1:
        raise ValueError(f"任务产物没有音频流：{path}")
    return info
