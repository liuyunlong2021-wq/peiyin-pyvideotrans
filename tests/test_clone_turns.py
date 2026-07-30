from videotrans.task._stage_dubbing import _merge_clone_turns


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
