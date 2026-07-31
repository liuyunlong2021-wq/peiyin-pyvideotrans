import json
from types import SimpleNamespace

from videotrans.task._stage_dubbing import _merge_clone_turns
from videotrans.task.only_one import _target_dialog_payload
from videotrans.component.onlyone_set_role import joined_line_conflict


def _item(line, speaker, start, end, text):
    return {
        'line': line, 'text': text, 'ref_text': f'原文{text}',
        'start_time': start, 'end_time': end,
        'start_time_source': start, 'end_time_source': end,
        'startraw': str(start), 'endraw': str(end),
        'role': 'clone', '_speaker': speaker,
        'filename': f'/tmp/dubb-{line}.wav', 'ref_wav': f'/tmp/clone-{line}.wav'
    }


def test_merge_consecutive_lines_from_the_same_speaker():
    queue = [
        _item(1, 'spk0', 0, 900, 'One.'),
        _item(2, 'spk0', 1000, 1900, 'Two.'),
        _item(3, 'spk1', 1900, 2600, 'Reply.'),
        _item(4, 'spk1', 4000, 4700, 'Later.'),
    ]

    merged = _merge_clone_turns(queue)

    assert len(merged) == 3
    assert merged[0]['text'] == 'One. Two.'
    assert merged[0]['end_time_source'] == 1900
    assert [item['line'] for item in merged[0]['_subtitle_items']] == [1, 2]
    assert merged[1]['text'] == 'Reply.'
    assert merged[2]['text'] == 'Later.'


def test_manual_turns_override_wrong_speaker_detection():
    queue = [
        _item(1, 'spk0', 0, 900, 'A one.'),
        _item(2, 'spk0', 900, 1800, 'B reply.'),
        _item(3, 'spk0', 1800, 2700, 'A two.'),
        _item(4, 'spk0', 2700, 3600, 'A three.'),
    ]

    merged = _merge_clone_turns(queue, [False, False, False, True])

    assert [item['text'] for item in merged] == ['A one.', 'B reply.', 'A two. A three.']
    assert [item['line'] for item in merged[2]['_subtitle_items']] == [3, 4]


def test_target_dialog_uses_voice_role_frozen_in_task():
    cfg = SimpleNamespace(
        cache_folder='/tmp/task-1', target_language_code='en',
        tts_type=1, voice_role='clone',
    )

    assert _target_dialog_payload(cfg) == '/tmp/task-1<|>en<|>1<|>clone'


def test_joined_line_conflict_reports_exact_row_and_reason():
    turns = [False, True, True]
    assignments = ['Speaker1', 'Speaker1', 'Speaker1']
    emotions = ['neutral', 'neutral', 'angry']

    assert joined_line_conflict(turns, assignments, emotions) == (2, 'emotion')
    assignments[2] = 'Speaker2'
    assert joined_line_conflict(turns, assignments, emotions) == (2, 'character')


def test_clone_review_uses_model_suggestions_and_hides_role_controls(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QWidget
    from videotrans.component.onlyone_set_role import SpeakerAssignmentDialog

    app = QApplication.instance() or QApplication([])
    source = tmp_path / 'source.srt'
    target = tmp_path / 'target.srt'
    source.write_text(
        '1\n00:00:00,000 --> 00:00:01,000\n你好\n\n'
        '2\n00:00:01,000 --> 00:00:02,000\n我知道', encoding='utf-8'
    )
    target.write_text(
        '1\n00:00:00,000 --> 00:00:01,000\nHello\n\n'
        '2\n00:00:01,000 --> 00:00:02,000\nI know', encoding='utf-8'
    )
    (tmp_path / 'speaker.json').write_text(json.dumps(['spk0', 'spk1']), encoding='utf-8')
    (tmp_path / 'turn_suggestions.json').write_text(json.dumps([
        {"line": 1, "speaker": "Speaker1", "join_previous": False},
        {"line": 2, "speaker": "Speaker1", "join_previous": True},
    ]), encoding='utf-8')

    parent = QWidget()
    dialog = SpeakerAssignmentDialog(
        parent=parent, source_sub=str(source), target_sub=str(target),
        cache_folder=str(tmp_path), tts_type=1, voice_role='clone',
        all_voices=['No', 'clone'],
    )
    dialog.show()
    dialog.load_table()
    app.processEvents()
    app.processEvents()

    assert dialog.splitter.orientation() == Qt.Horizontal
    assert dialog.table.isColumnHidden(0)
    assert not dialog.table.isColumnHidden(4)
    assert dialog.table.horizontalHeaderItem(4).text() in {'Emotion', '情绪'}
    assert not dialog.bottom_button_container.isVisible()
    assert dialog.timer is None
    assert dialog.display_data[1]['spk'] == 'Speaker1'
    assert dialog.display_data[0]['time_str'] == '00:00.0–00:01.0'
    assert dialog.table.item(1, 3).checkState() == Qt.Checked

    dialog.hide()
    parent.close()
