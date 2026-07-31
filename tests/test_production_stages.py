from pathlib import Path
from unittest.mock import patch

import pytest

from videotrans.task.taskcfg import SrtItem
from videotrans.task.production_stages import run_project_recognition, run_project_translation
from videotrans.util.production_project import read_states, scaffold_project, update_stage


def _item(text):
    return SrtItem(
        line=1, text=text, start_time=0, end_time=1000,
        startraw='00:00:00,000', endraw='00:00:01,000',
        time='00:00:00,000 --> 00:00:01,000')


def test_project_recognition_writes_sensevoice_metadata_to_wiki(tmp_path):
    project, video = tmp_path / 'project', tmp_path / 'input.mp4'
    scaffold_project(project, 1)
    video.write_bytes(b'video')

    with patch('videotrans.task.production_stages.config.TEMP_DIR', (tmp_path / 'tasks').as_posix()), \
            patch('videotrans.task.production_stages.runffmpeg') as ffmpeg, \
            patch('videotrans.task.production_stages.recognition.run') as recognize:
        def make_audio(command):
            Path(command[-1]).write_bytes(b'RIFF-audio')
        def result(**kwargs):
            assert kwargs['uuid'].startswith('production-project/')
            Path(kwargs['cache_folder'], 'sensevoice_metadata.json').write_text(
                '[{"start_time":0,"end_time":1000,"emotion":"angry","events":["cry"]}]',
                encoding='utf-8')
            return [_item('你走开')]
        ffmpeg.side_effect, recognize.side_effect = make_audio, result
        _, page = run_project_recognition(project, '第01集', video)

    assert '| angry; cry |' in page.read_text(encoding='utf-8')
    assert read_states(project, 1)['中文识别'][0] == '待校对'


def test_project_translation_requires_confirmation_and_creates_review_page(tmp_path):
    project = tmp_path / 'project'
    scaffold_project(project, 1)
    recognition_page = project / 'wiki/集数/第01集/中文识别.md'
    recognition_page.write_text(
        '# 识别\n\n| 行 | 开始 | 结束 | 中文原文 | 音频说话人 | 声音事件 |\n'
        '|---:|---:|---:|---|---|---|\n'
        '| 1 | 00:00:00,000 | 00:00:01,000 | 你走开 | spk0 | angry; cry |\n', encoding='utf-8')
    update_stage(project, 1, '中文识别', '已确认')

    with patch('videotrans.task.production_stages.config.TEMP_DIR', (tmp_path / 'tasks').as_posix()), \
            patch('videotrans.task.production_stages.translator.run', return_value=[_item('Get out')]), \
            patch('videotrans.task.production_stages.suggest_turns', return_value=[{
                'line': 1, 'speaker': 'Speaker1', 'join_previous': False}]):
        _, page = run_project_translation(project, '第01集')

    text = page.read_text(encoding='utf-8')
    assert '| Speaker1 | angry | 否 | Get out | 你走开 |' in text
    assert read_states(project, 1)['剧情翻译与轮次'][0] == '待校对'


def test_project_recognition_failure_does_not_stay_processing(tmp_path):
    project, video = tmp_path / 'project', tmp_path / 'input.mp4'
    scaffold_project(project, 1)
    video.write_bytes(b'video')

    with patch('videotrans.task.production_stages.config.TEMP_DIR', (tmp_path / 'tasks').as_posix()), \
            patch('videotrans.task.production_stages.runffmpeg'), \
            patch('videotrans.task.production_stages.recognition.run', side_effect=RuntimeError('boom')):
        with pytest.raises(RuntimeError, match='boom'):
            run_project_recognition(project, '第01集', video)

    assert read_states(project, 1)['中文识别'][0] == '失败'


def test_cancelled_recognition_keeps_previous_outputs(tmp_path):
    project, video = tmp_path / 'project', tmp_path / 'input.mp4'
    scaffold_project(project, 1)
    video.write_bytes(b'video')
    page = project / 'wiki/集数/第01集/中文识别.md'
    srt = project / '.raw/media/文件/第01集/识别.srt'
    page.write_text('confirmed page', encoding='utf-8')
    srt.write_text('confirmed srt', encoding='utf-8')

    with patch('videotrans.task.production_stages.config.TEMP_DIR', (tmp_path / 'tasks').as_posix()), \
            patch('videotrans.task.production_stages.runffmpeg'), \
            patch('videotrans.task.production_stages.recognition.run', return_value=[_item('new')]):
        with pytest.raises(InterruptedError, match='未发布'):
            run_project_recognition(project, '第01集', video, cancelled=lambda: True)

    assert page.read_text(encoding='utf-8') == 'confirmed page'
    assert srt.read_text(encoding='utf-8') == 'confirmed srt'
    assert read_states(project, 1)['中文识别'][0] == '失败'
