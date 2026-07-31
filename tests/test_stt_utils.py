import os
import tempfile

from videotrans.process._stt_utils import (
    _remove_unwanted_characters,
    _resegment,
    _write_log,
    sensevoice_metadata,
)


def test_current_recognition_modules_importable():
    from videotrans.process.stt_faster import faster_whisper
    from videotrans.process.stt_funasr import funasr_mlt
    from videotrans.process.stt_openai import openai_whisper
    from videotrans.process.stt_paraformer import paraformer
    from videotrans.process.stt_pipe import pipe_asr
    from videotrans.process.stt_qwen import qwen3asr_fun

    assert all(callable(item) for item in (
        openai_whisper, faster_whisper, pipe_asr,
        paraformer, qwen3asr_fun, funasr_mlt,
    ))


def test_remove_unwanted_characters():
    assert _remove_unwanted_characters('Hello <|en|> world') == 'Hello  world'
    assert _remove_unwanted_characters('测试<|zh|>文本') == '测试文本'
    assert _remove_unwanted_characters('abc 123 !@#') == 'abc 123 !@#'


def test_sensevoice_metadata_keeps_emotion_and_events():
    text, emotion, events = sensevoice_metadata('<|zh|><|ANGRY|><|Speech|><|Cry|>你走开')

    assert text == '你走开'
    assert emotion == 'angry'
    assert events == ['speech', 'cry']


def test_resegment_keeps_short_segment():
    result = _resegment([{
        'text': 'Hello world',
        'start': 0.0,
        'end': 1.0,
        'words': [
            {'word': 'Hello', 'start': 0.0, 'end': 0.5},
            {'word': 'world', 'start': 0.5, 'end': 1.0},
        ],
    }], 'en', 6000)

    assert len(result) == 1
    assert result[0]['text'] == 'Hello world'
    assert result[0]['start_time'] == 0
    assert result[0]['end_time'] == 1000


def test_resegment_chinese_without_spaces():
    result = _resegment([{
        'text': '你好世界',
        'start': 0.0,
        'end': 1.0,
        'words': [
            {'word': '你好', 'start': 0.0, 'end': 0.5},
            {'word': '世界', 'start': 0.5, 'end': 1.0},
        ],
    }], 'zh', 6000)

    assert len(result) == 1
    assert result[0]['text'] == '你好世界'


def test_resegment_splits_long_segment():
    words = [
        {'word': word, 'start': index * 0.6, 'end': (index + 1) * 0.6}
        for index, word in enumerate('one two three four five six seven eight nine ten'.split())
    ]
    result = _resegment([{
        'text': 'one two three four five six seven eight nine ten',
        'start': 0.0,
        'end': 6.0,
        'words': words,
    }], 'en', 3000)

    assert len(result) >= 2
    assert all(item['end_time'] - item['start_time'] <= 3000 for item in result)


def test_resegment_without_word_timestamps():
    result = _resegment([{
        'text': 'Some text without words field',
        'start': 0.0,
        'end': 2.0,
    }], 'en', 6000)

    assert len(result) == 1
    assert result[0]['text'] == 'Some text without words field'


def test_write_log():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as handle:
        log_path = handle.name
    try:
        _write_log(log_path, 'hello')
        assert open(log_path, encoding='utf-8').read() == 'hello'
    finally:
        os.unlink(log_path)
