import json
from pathlib import Path

from videotrans import recognition, translator
from videotrans.configure import config
from videotrans.configure.config import params
from videotrans.translator._jiucai import suggest_turns
from videotrans.util.help_ffmpeg import runffmpeg
from videotrans.util.help_srt import get_srt_from_list, get_subtitle_from_srt
from videotrans.util.production_markdown import (
    export_recognition_srt, import_recognition_srt, import_translation_srt, recognition_rows,
)
from videotrans.util.production_project import (
    check_cancelled, episode_name, isolated_work_dir, publish_files, require_stage, snapshot_files,
    stage_execution, update_stage, verify_snapshot,
)


def _sensevoice_fields(items, metadata):
    emotions, events = [], []
    for item in items:
        overlapping = [row for row in metadata if row['end_time'] > item['start_time'] and row['start_time'] < item['end_time']]
        emotions.append(next((row['emotion'] for row in overlapping if row.get('emotion') != 'neutral'),
                             overlapping[0].get('emotion', 'neutral') if overlapping else 'neutral'))
        names = dict.fromkeys(event for row in overlapping for event in row.get('events', []))
        events.append('; '.join([emotions[-1], *names]))
    return emotions, events


def run_project_recognition(project, episode, source_video, cancelled=None):
    project, source_video = Path(project).resolve(), Path(source_video).resolve()
    input_snapshot = snapshot_files((source_video,))
    work = isolated_work_dir(config.TEMP_DIR, project)
    with stage_execution(project, episode, '中文识别'):
        audio = work / 'cache/source.wav'
        runffmpeg(['-y', '-i', source_video.as_posix(), '-vn', '-ar', '16000', '-ac', '1',
                   '-c:a', 'pcm_s16le', audio.as_posix()])
        task_uuid = work.relative_to(Path(config.TEMP_DIR).resolve()).as_posix()
        items = recognition.run(
            recogn_type=recognition.FUNASR_CN, uuid=task_uuid, model_name='SenseVoiceSmall',
            audio_file=audio.as_posix(), detect_language='zh', cache_folder=(work / 'cache').as_posix(),
            is_cuda=False, subtitle_type=0, max_speakers=-1, llm_post=False)
        check_cancelled(cancelled)
        if not items:
            raise RuntimeError('SenseVoice 没有识别出中文台词')
        verify_snapshot(input_snapshot)
        srt = work / 'target/识别.srt'
        srt.write_text(get_srt_from_list(items), encoding='utf-8')
        metadata_file = work / 'cache/sensevoice_metadata.json'
        metadata = json.loads(metadata_file.read_text(encoding='utf-8')) if metadata_file.is_file() else []
        _, events = _sensevoice_fields(items, metadata)
        staged_page = work / 'target/中文识别.md'
        import_recognition_srt(
            project, episode, srt, 'SenseVoiceSmall', events=events, write_derived=False,
            page_file=staged_page, update_state=False)
        page, _ = publish_files((
            (staged_page, project / 'wiki/集数' / episode / '中文识别.md'),
            (srt, project / '.raw/media/文件' / episode / '识别.srt'),
        ), project=project)
        update_stage(project, episode, '中文识别', '待校对', invalidate_downstream=True)
    return work, page


def run_project_translation(project, episode, cancelled=None):
    project = Path(project).resolve()
    require_stage(project, episode, '中文识别', ('已确认',))
    episode = episode_name(episode)
    input_snapshot = snapshot_files((
        project / 'wiki/集数' / episode / '中文识别.md',
    ))
    work = isolated_work_dir(config.TEMP_DIR, project)
    with stage_execution(project, episode, '剧情翻译与轮次'):
        source_file = export_recognition_srt(project, episode, work / 'target/中文-已确认.srt')
        source = get_subtitle_from_srt(source_file)
        target = translator.run(
            translate_type=translator.JIUCAI_DRAMA_INDEX, text_list=source, uuid=work.name,
            source_code='zh-CN', target_code='en')
        check_cancelled(cancelled)
        if not target:
            raise RuntimeError('剧情翻译没有返回英文字幕')
        verify_snapshot(input_snapshot)
        target_file = work / 'target/英文-待校对.srt'
        target_file.write_text(get_srt_from_list(target), encoding='utf-8')
        speakers = [row['音频说话人'] for row in recognition_rows(project, episode)]
        suggestions = suggest_turns(source, target, speakers)
        sound_events = [row['声音事件'].split(';', 1)[0].strip() or 'neutral'
                        for row in recognition_rows(project, episode)]
        staged_page = work / 'target/翻译与轮次.md'
        import_translation_srt(
            project, episode, target_file, params.get('jiucai_model', 'gemini-3.6-flash'),
            assignments=[row['speaker'] for row in suggestions], emotions=sound_events,
            turns=[row['join_previous'] for row in suggestions], page_file=staged_page, update_state=False)
        page, _ = publish_files((
            (staged_page, project / 'wiki/集数' / episode / '翻译与轮次.md'),
            (target_file, project / '.raw/media/文件' / episode / '英文-待校对.srt'),
        ), project=project)
        update_stage(project, episode, '剧情翻译与轮次', '待校对', invalidate_downstream=True)
    return work, page
