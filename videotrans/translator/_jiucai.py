import json
import re
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from videotrans.configure.config import ROOT_DIR, params
from videotrans.translator._openaicompat import OpenAICampat


def parse_turn_suggestions(content, expected_lines):
    content = re.sub(r'<think>.*?</think>', '', content or '', flags=re.I | re.S).strip()
    content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content, flags=re.I | re.S).strip()
    data = json.loads(content)
    if isinstance(data, dict):
        data = data.get('items')
    if not isinstance(data, list) or len(data) != len(expected_lines):
        raise ValueError('Turn suggestion count does not match subtitles')

    result = []
    for index, (item, expected_line) in enumerate(zip(data, expected_lines)):
        if not isinstance(item, dict) or item.get('line') != expected_line:
            raise ValueError('Turn suggestion line does not match subtitles')
        speaker = str(item.get('speaker', '')).strip()
        match = re.fullmatch(r'speaker([1-9]\d*)', speaker, flags=re.I)
        if not match or not isinstance(item.get('join_previous'), bool):
            raise ValueError('Turn suggestion fields are invalid')
        join_previous = item['join_previous']
        if index == 0 and join_previous:
            raise ValueError('The first subtitle cannot join a previous subtitle')
        result.append({
            'line': expected_line,
            'speaker': f'Speaker{match.group(1)}',
            'join_previous': join_previous,
        })
    return result


def suggest_turns(source_items, target_items, speaker_hints=None):
    speaker_hints = speaker_hints or []
    episode_items = []
    for index, (source, target) in enumerate(zip(source_items, target_items)):
        episode_items.append({
            'line': source['line'],
            'time': source['time'],
            'source': source['text'],
            'translation': target['text'],
            'audio_speaker': speaker_hints[index] if index < len(speaker_hints) else '',
        })

    prompt = Path(f'{ROOT_DIR}/videotrans/prompts/turns/jiucai_drama.txt').read_text(encoding='utf-8')
    response = OpenAI(
        api_key=params.get('jiucai_key', ''),
        base_url=params.get('jiucai_api', ''),
    ).chat.completions.create(
        model='gemini-3.6-flash',
        timeout=300,
        temperature=0,
        max_tokens=max(2048, len(episode_items) * 80),
        messages=[
            {'role': 'system', 'content': 'You identify dialogue speakers and continuous speaking turns.'},
            {'role': 'user', 'content': prompt.replace(
                '{episode_items}', json.dumps(episode_items, ensure_ascii=False)
            )},
        ],
    )
    if not response.choices or not response.choices[0].message.content:
        raise ValueError('Turn suggestion response is empty')
    return parse_turn_suggestions(
        response.choices[0].message.content,
        [item['line'] for item in source_items],
    )


@dataclass
class JiuCaiDrama(OpenAICampat):
    def __post_init__(self):
        self.ainame = "jiucai_drama"
        self.api_key = params.get("jiucai_key", "")
        self.api_url = params.get("jiucai_api", "")
        self.model_name = "gemini-3.6-flash"
        self.max_tokens = 16384
        super().__post_init__()

    def _get_key(self, data):
        return super()._get_key(data) + "-srt-v2"

    def _item_task(self, data):
        result = super()._item_task(data)
        return re.sub(r"\n(?=\d+\n\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->)", "\n\n", result)
