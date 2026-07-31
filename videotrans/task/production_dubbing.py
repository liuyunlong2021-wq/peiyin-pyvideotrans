import shutil
from pathlib import Path

from videotrans.configure import config
from videotrans.task.taskcfg import TaskCfgVTT
from videotrans.task.trans_create import TransCreate
from videotrans.tts import QWEN3LOCAL_TTS
from videotrans.util.help_ffmpeg import format_video, get_video_duration, get_video_info, runffmpeg
from videotrans.util.help_srt import set_ass_font
from videotrans.util.production_markdown import export_recognition_srt, export_translation_task, read_strict_srt
from videotrans.util.production_project import (
    check_cancelled, episode_name, isolated_work_dir, publish_files, require_stage, snapshot_files,
    stage_execution, update_stage, validate_media, verify_snapshot,
)
from videotrans.util.production_markdown import write_calibration_page, write_dubbing_page


def prepare_dubbing_workspace(project, episode, source_video):
    project, source_video = Path(project).resolve(), Path(source_video).resolve()
    work = isolated_work_dir(config.TEMP_DIR, project)
    target = Path(format_video(source_video.as_posix(), (work / "target").as_posix()).target_dir)
    target.mkdir(parents=True, exist_ok=True)
    cache = work / "cache"
    exported = export_translation_task(project, episode, target)
    source_srt = export_recognition_srt(project, episode, target / "zh-CN.srt")
    shutil.move(exported, target / "en.srt")
    source_wav = cache / "zh-CN.wav"
    runffmpeg([
        "-y", "-i", source_video.as_posix(), "-vn", "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le", source_wav.as_posix(),
    ])
    return work, source_srt, target / "en.srt", source_wav


def run_project_dubbing(project, episode, source_video, cancelled=None):
    project, source_video = Path(project).resolve(), Path(source_video).resolve()
    require_stage(project, episode, "剧情翻译与轮次", ("已确认",))
    episode = episode_name(episode)
    input_snapshot = snapshot_files((
        source_video,
        project / "wiki/集数" / episode / "中文识别.md",
        project / "wiki/集数" / episode / "翻译与轮次.md",
    ))
    input_snapshot += snapshot_files(sorted((project / "wiki/角色").glob("*/配音档案.md")))
    work, source_srt, target_srt, source_wav = prepare_dubbing_workspace(project, episode, source_video)
    with stage_execution(project, episode, "英文克隆配音"):
        target, cache = work / "target", work / "cache"
        input_file = format_video(source_video.as_posix(), (work / "target").as_posix())
        cfg = TaskCfgVTT(**(dict(
            cache_folder=cache.as_posix(), clear_cache=False, source_language_code="zh-CN",
            target_language_code="en", detect_language="zh", voice_role="clone",
            tts_type=QWEN3LOCAL_TTS, voice_rate="+0%", volume="+0%", pitch="+0Hz",
            voice_autorate=True, video_autorate=False, align_sub_audio=True,
            app_mode="biaozhun", fix_punc=2,
        ) | input_file))
        task = TransCreate(cfg=cfg)
        task.strict_voice_reference = True
        task.cfg.source_sub, task.cfg.target_sub = source_srt.as_posix(), target_srt.as_posix()
        task.cfg.source_wav = source_wav.as_posix()
        task.cfg.target_wav = (cache / "英文配音.wav").as_posix()
        task.clone_ref = source_wav.as_posix()
        task.video_time = get_video_duration(source_video.as_posix())
        task.dubbing()
        task.align()
        check_cancelled(cancelled)
        verify_snapshot(input_snapshot)
        validate_media(task.cfg.target_wav, audio=True)
        turn_sources = [Path(item["filename"]) for item in task.queue_tts]
        reference_sources = [Path(item["ref_wav"]) for item in task.queue_tts]
        turn_destinations = [
            project / ".raw/media/音频" / episode / "英文配音" / f"turn-{index:03d}.wav"
            for index in range(1, len(task.queue_tts) + 1)]
        reference_destinations = [
            project / ".raw/media/音频" / episode / "英文配音" / f"reference-{index:03d}.wav"
            for index in range(1, len(task.queue_tts) + 1)]
        page = work / "target/英文配音.md"
        write_dubbing_page(
            project, episode, task.queue_tts, turn_destinations, reference_destinations, page_file=page)
        published = publish_files((
            (task.cfg.target_wav, project / ".raw/media/音频" / episode / "英文配音.wav"),
            (task.cfg.target_sub, project / ".raw/media/文件" / episode / "英文-机器校准.srt"),
            (page, project / "wiki/集数" / episode / "英文配音.md"),
            *zip(turn_sources, turn_destinations),
            *zip(reference_sources, reference_destinations),
        ), project=project)
        audio, subtitle = published[:2]
        update_stage(project, episode, "英文克隆配音", "已完成", invalidate_downstream=True)
        update_stage(project, episode, "配音字幕校准", "待校对")
    return work, audio, subtitle


def confirm_calibrated_subtitle(project, episode, subtitle, cancelled=None):
    project, subtitle = Path(project).resolve(), Path(subtitle).resolve()
    require_stage(project, episode, "英文克隆配音", ("已完成",))
    read_strict_srt(subtitle)
    input_snapshot = snapshot_files((subtitle,))
    work = isolated_work_dir(config.TEMP_DIR, project)
    try:
        with stage_execution(project, episode, "配音字幕校准"):
            check_cancelled(cancelled)
            page = write_calibration_page(project, episode, page_file=work / "target/字幕校准与合成.md")
            verify_snapshot(input_snapshot)
            destination, _ = publish_files((
                (subtitle, project / ".raw/media/文件" / episode / "英文-已确认.srt"),
                (page, project / "wiki/集数" / episode / "字幕校准与合成.md"),
            ), project=project)
            update_stage(project, episode, "配音字幕校准", "已确认", invalidate_downstream=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return destination


def compose_project_video(project, episode, cancelled=None):
    project = Path(project).resolve()
    require_stage(project, episode, "英文克隆配音", ("已完成",))
    require_stage(project, episode, "配音字幕校准", ("已确认",))
    video = project / ".raw/media/视频" / episode / "无字幕.mp4"
    audio = project / ".raw/media/音频" / episode / "英文配音.wav"
    subtitle = project / ".raw/media/文件" / episode / "英文-已确认.srt"
    for path in (video, audio, subtitle):
        if not path.is_file():
            raise FileNotFoundError(f"缺少最终合成输入：{path}")
    input_snapshot = snapshot_files((video, audio, subtitle))
    work = isolated_work_dir(config.TEMP_DIR, project)
    with stage_execution(project, episode, "最终合成"):
        local_subtitle = work / "target/英文-已确认.srt"
        shutil.copy2(subtitle, local_subtitle)
        info = get_video_info(video.as_posix())
        ass = Path(set_ass_font(local_subtitle.as_posix(), int(info["width"]), int(info["height"])))
        output = work / "target/最终视频.mp4"
        fonts = (Path(config.ROOT_DIR) / "videotrans/styles/fonts").as_posix().replace("'", "'\\''")
        ass_path = ass.as_posix().replace("'", "'\\''")
        runffmpeg([
            "-y", "-i", video.as_posix(), "-i", audio.as_posix(),
            "-vf", f"subtitles=filename='{ass_path}':fontsdir='{fonts}'",
            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "23",
            "-preset", "medium", "-c:a", "aac", "-b:a", "128k", "-shortest", output.as_posix(),
        ], force_cpu=True)
        check_cancelled(cancelled)
        verify_snapshot(input_snapshot)
        validate_media(output, video=True, audio=True)
        page = write_calibration_page(
            project, episode, final=True, page_file=work / "target/字幕校准与合成.md")
        destination, _ = publish_files((
            (output, project / ".raw/media/视频" / episode / "最终视频.mp4"),
            (page, project / "wiki/集数" / episode / "字幕校准与合成.md"),
        ), project=project)
        update_stage(project, episode, "最终合成", "已完成")
    return work, destination
