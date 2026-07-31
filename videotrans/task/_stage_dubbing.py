import copy
import json
import re
import shutil
import time
from pathlib import Path

from videotrans.configure.config import tr, app_cfg, settings, logger, ROOT_DIR
from videotrans.configure.excepts import DubbingSrtError
from videotrans.tts import run as run_tts, SUPPORT_CLONE, QWEN3LOCAL_TTS
from videotrans.util.help_misc import get_md5
from videotrans.util.help_srt import get_subtitle_from_srt, delete_punc


def _merge_clone_turns(queue_tts, joins=None):
    merged = []
    for index, item in enumerate(queue_tts):
        current = copy.deepcopy(item)
        current['_subtitle_items'] = [{
            'line': current['line'], 'text': current['text'],
            'start_time': current['start_time'], 'end_time': current['end_time']
        }]
        previous = merged[-1] if merged else None
        gap = current['start_time_source'] - previous['end_time_source'] if previous else 0
        same_turn = joins[index] if joins is not None else (
            current.get('_speaker') and current.get('_speaker') == previous.get('_speaker')
            and 0 <= gap <= 1000
        ) if previous else False
        if previous and same_turn \
                and str(current['role']).strip().lower() == str(previous['role']).strip().lower() == 'clone':
            previous['text'] += ' ' + current['text']
            previous['ref_text'] = f"{previous['ref_text']} {current['ref_text']}".strip()
            previous['end_time'] = current['end_time']
            previous['endraw'] = current['endraw']
            previous['end_time_source'] = current['end_time_source']
            previous['_subtitle_items'].extend(current['_subtitle_items'])
            continue
        merged.append(current)

    for item in merged:
        if len(item['_subtitle_items']) < 2:
            continue
        first, last = item['_subtitle_items'][0]['line'], item['_subtitle_items'][-1]['line']
        folder = Path(item['filename']).parent
        key = get_md5(f"{item['text']}-{item['ref_text']}-{item.get('_speaker', '')}")
        item['filename'] = (folder / f'dubb-turn-{first}-{last}-{key}.wav').as_posix()
        item['ref_wav'] = (folder / f'clone-turn-{first}-{last}.wav').as_posix()
    return merged


class DubbingMixin:

    def prepare_clone_review(self):
        """Analyze provisional full turns before the human review dialog opens."""
        if self.cfg.tts_type != QWEN3LOCAL_TTS \
                or str(self.cfg.voice_role).strip().lower() != 'clone':
            return
        source = get_subtitle_from_srt(self.cfg.source_sub)
        if not source:
            return
        joins = [False] * len(source)
        speakers = [''] * len(source)
        suggestion_file = Path(self.cfg.cache_folder) / 'turn_suggestions.json'
        try:
            from videotrans.translator._jiucai import parse_turn_suggestions
            suggestions = parse_turn_suggestions(
                suggestion_file.read_text(encoding='utf-8'), [item['line'] for item in source])
            joins = [item['join_previous'] for item in suggestions]
            speakers = [item['speaker'] for item in suggestions]
        except (OSError, ValueError, json.JSONDecodeError):
            speaker_file = Path(self.cfg.cache_folder) / 'speaker.json'
            try:
                saved = json.loads(speaker_file.read_text(encoding='utf-8'))
                if isinstance(saved, list) and len(saved) == len(source):
                    speakers = [str(value) for value in saved]
            except (OSError, json.JSONDecodeError):
                pass
        queue = []
        for index, item in enumerate(source):
            if index and joins[index] and queue[-1]['_speaker'] == speakers[index]:
                queue[-1]['end_time_source'] = item['end_time']
                queue[-1]['endraw'] = item['endraw']
                queue[-1]['ref_text'] += ' ' + item['text']
                queue[-1]['line_end'] = item['line']
                continue
            queue.append({
                'line': item['line'], 'line_end': item['line'], '_speaker': speakers[index],
                'ref_text': item['text'], 'start_time_source': item['start_time'],
                'end_time_source': item['end_time'], 'startraw': item['startraw'],
                'endraw': item['endraw'],
                'ref_wav': f'{self.cfg.cache_folder}/emotion-turn-{item["line"]}.wav',
            })
        vocal = self.clone_ref if self.clone_ref and Path(self.clone_ref).is_file() else self.cfg.source_wav
        from videotrans.util.help_ffmpeg import cut_from_audio
        for item in queue:
            if not Path(item['ref_wav']).is_file():
                cut_from_audio(audio_file=vocal, ss=item['startraw'], to=item['endraw'],
                               out_file=item['ref_wav'])
        model_dir = f'{ROOT_DIR}/models/emotion2vec_plus_large'
        from videotrans.util.help_down import check_and_down_ms
        check_and_down_ms('iic/emotion2vec_plus_large',
                          callback=self._process_callback, local_dir=model_dir)
        queue_file = Path(self.cfg.cache_folder) / 'emotion-review-queue.json'
        queue_file.write_text(json.dumps(queue, ensure_ascii=False), encoding='utf-8')
        from videotrans.process.emotion_reference import analyze_and_select
        self._new_process(callback=analyze_and_select, title='Analyze voice emotion', kwargs={
            'queue_file': str(queue_file), 'model_dir': model_dir,
        })
        analyzed = json.loads(queue_file.read_text(encoding='utf-8'))
        emotions = ['neutral'] * len(source)
        line_indexes = {int(item['line']): index for index, item in enumerate(source)}
        for item in analyzed:
            start = line_indexes.get(int(item['line']))
            end = line_indexes.get(int(item.get('line_end', item['line'])))
            if start is not None and end is not None:
                for index in range(start, end + 1):
                    emotions[index] = item.get('emotion', 'neutral')
        (Path(self.cfg.target_dir) / 'emotion_suggestions.json').write_text(
            json.dumps(emotions, ensure_ascii=False, indent=2), encoding='utf-8')

    def dubbing(self) -> None:
        _st=time.time()
        if self._exit() or self.cfg.app_mode == 'tiqu':
            return
        if self.should_dubbing:
            self.signal(text=tr('kaishipeiyin'))
        self.precent += 3
        self._tts()
        if Path(self.cfg.target_sub).exists():
            subs = get_subtitle_from_srt(self.cfg.target_sub)
            if self.cfg.fix_punc==2:
                logger.debug('配音结束后，移除目标字幕中所有标点')
            for it in subs:
                it['text']=it['text'].strip('...')
                if self.cfg.fix_punc==2:
                    it['text']=delete_punc(it['text'])
            self._save_srt_target(subs, self.cfg.target_sub)

        if  self.cfg.fix_punc==2 and Path(self.cfg.source_sub).exists():
            logger.debug('配音结束后，移除原始字幕中所有标点')
            subs = get_subtitle_from_srt(self.cfg.source_sub)
            for it in subs:
                it['text']=delete_punc(it['text'])
            self._save_srt_target(subs, self.cfg.source_sub)
        if self.should_dubbing:
            self.signal(text=tr('The dubbing is finished'))
            logger.debug(f'[语音合成阶段结束耗时]:{time.time()-_st}s')

    def _tts(self) -> None:
        if not self.should_dubbing:
            self.signal(text='Skip tts')
            return
        queue_tts = []
        subs = get_subtitle_from_srt(self.cfg.target_sub)
        source_subs = get_subtitle_from_srt(self.cfg.source_sub)
        if len(subs) < 1:
            raise DubbingSrtError(f"SRT file error:{self.cfg.target_sub}")
        try:
            rate = int(str(self.cfg.voice_rate).replace('%', ''))
        except (ValueError,TypeError):
            rate = 0

        rate = f"+{rate}%" if rate >= 0 else f"{rate}%"

        line_roles = app_cfg.line_roles
        voice_role = self.cfg.voice_role
        speakers = []
        assignments = []
        turns = None
        speaker_file = Path(self.cfg.cache_folder) / 'speaker.json'
        if self.cfg.tts_type == QWEN3LOCAL_TTS and speaker_file.is_file():
            try:
                speakers = json.loads(speaker_file.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                logger.warning(f'无法读取说话人数据，保持逐句配音: {speaker_file}')
        turns_file = Path(self.cfg.target_dir) / 'turns.json'
        assignments_file = Path(self.cfg.target_dir) / 'speaker_assignments.json'
        if self.cfg.tts_type == QWEN3LOCAL_TTS and assignments_file.is_file():
            try:
                saved_assignments = json.loads(assignments_file.read_text(encoding='utf-8'))
                if isinstance(saved_assignments, list) and len(saved_assignments) == len(subs):
                    assignments = [str(value).strip() for value in saved_assignments]
            except (OSError, json.JSONDecodeError):
                logger.warning(f'无法读取稳定人物数据，改用本集说话人标签: {assignments_file}')
        if self.cfg.tts_type == QWEN3LOCAL_TTS and turns_file.is_file():
            try:
                saved_turns = json.loads(turns_file.read_text(encoding='utf-8'))
                if isinstance(saved_turns, list) and len(saved_turns) == len(subs) \
                        and all(isinstance(value, bool) for value in saved_turns):
                    turns = saved_turns
                else:
                    logger.warning(f'发言轮次数据与字幕不匹配，改用自动分组: {turns_file}')
            except (OSError, json.JSONDecodeError):
                logger.warning(f'无法读取发言轮次数据，改用自动分组: {turns_file}')
        logger.debug(f'{line_roles=}')
        queue_joins = []
        previous_sub_index = -2
        for i, it in enumerate(subs):
            if it['end_time'] < it['start_time'] or not it['text'].strip():
                continue
            voice = line_roles.get(f'{it["line"]}', voice_role) if line_roles else voice_role

            _key = get_md5(f"{self.cfg.target_language_code}-{it['text']}-{voice}-{rate}-{self.cfg.volume}-{self.cfg.pitch}-{self.cfg.tts_type}")

            tmp_dict = {
                "text": it['text'],
                "line": it['line'],
                "start_time": it['start_time'],
                "end_time": it['end_time'],
                "startraw": it['startraw'],
                "endraw": it['endraw'],
                "ref_text": source_subs[i]['text'] if source_subs and i < len(source_subs) else '',
                "start_time_source": source_subs[i]['start_time'] if source_subs and i < len(source_subs) else it[
                    'start_time'],
                "end_time_source": source_subs[i]['end_time'] if source_subs and i < len(source_subs) else it[
                    'end_time'],
                "role": voice,
                "rate": rate,
                "volume": self.cfg.volume,
                "pitch": self.cfg.pitch,
                "tts_type": self.cfg.tts_type,
                "filename": f"{self.cfg.cache_folder}/dubb-{i}-{_key}.wav"
            }
            if i < len(assignments) and assignments[i]:
                tmp_dict['_speaker'] = assignments[i]
            elif i < len(speakers):
                tmp_dict['_speaker'] = speakers[i]
            if str(voice).strip().lower() == 'clone' and self.cfg.tts_type in SUPPORT_CLONE:
                tmp_dict['ref_wav'] = f"{self.cfg.cache_folder}/clone-{i}.wav"
                tmp_dict['ref_language'] = self.cfg.detect_language[:2]
            queue_tts.append(tmp_dict)
            same_character = i > 0 and i < len(assignments) and assignments[i] == assignments[i - 1]
            queue_joins.append(bool(turns[i]) and previous_sub_index == i - 1
                               and (not assignments or same_character) if turns is not None else False)
            previous_sub_index = i

        if self.cfg.tts_type == QWEN3LOCAL_TTS and (turns is not None or speakers):
            queue_tts = _merge_clone_turns(queue_tts, queue_joins if turns is not None else None)
        self.queue_tts = copy.deepcopy(queue_tts)

        if not self.queue_tts or len(self.queue_tts) < 1:
            raise RuntimeError(f'字幕长度为0，无法继续配音')

        if len([it.get("ref_wav") for it in self.queue_tts if it.get("ref_wav")]) > 0:
            self._create_ref_from_vocal()
            self._apply_voice_library()

        run_tts(
            queue_tts=self.queue_tts,
            language=self.cfg.target_language_code,
            uuid=self.uuid,
            tts_type=self.cfg.tts_type,
            is_cuda=self.cfg.is_cuda
        )
        if settings.get('save_segment_audio', False):
            outname = self.cfg.target_dir + f'/segment_audio_{self.cfg.noextname}'
            Path(outname).mkdir(parents=True, exist_ok=True)
            for it in self.queue_tts:
                text = re.sub(r'["\'*?\\/|:<>\r\n\t]+', '', it['text'], flags=re.I | re.S)
                name = f'{outname}/{it["line"]}-{text[:60]}.wav'
                if Path(it['filename']).exists():
                    shutil.copy2(it['filename'], name)

    def _apply_voice_library(self):
        pointer = Path(self.cfg.target_dir) / 'voice_library.json'
        if self.cfg.tts_type != QWEN3LOCAL_TTS or not pointer.is_file():
            return
        try:
            library = json.loads(pointer.read_text(encoding='utf-8'))
            library_dir = str(library.get('path', '')).strip()
            if not library_dir:
                return
            from videotrans.util.help_down import check_and_down_ms
            model_dir = f'{ROOT_DIR}/models/emotion2vec_plus_large'
            check_and_down_ms('iic/emotion2vec_plus_large',
                              callback=self._process_callback, local_dir=model_dir)
            queue_file = Path(self.cfg.cache_folder) / 'emotion-reference-queue.json'
            queue_file.write_text(json.dumps(self.queue_tts, ensure_ascii=False), encoding='utf-8')
            from videotrans.process.emotion_reference import analyze_and_select
            self._new_process(
                callback=analyze_and_select,
                title='Analyze voice emotion',
                kwargs={
                    'queue_file': str(queue_file),
                    'library_dir': library_dir,
                    'add_current': bool(library.get('add_current')),
                    'model_dir': model_dir,
                    'episode': self.cfg.noextname,
                    'emotion_file': str(Path(self.cfg.target_dir) / 'emotion_overrides.json'),
                })
            self.queue_tts = json.loads(queue_file.read_text(encoding='utf-8'))
        except Exception as error:
            if self.strict_voice_reference:
                raise DubbingSrtError(f'角色参考库处理失败，已阻止配音：{error}') from error
            logger.warning(f'角色参考库不可用，继续使用当前原声: {type(error).__name__}: {error}')
