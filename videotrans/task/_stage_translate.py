import copy
import json
import shutil
import time
from pathlib import Path

from videotrans.configure.config import tr, logger
from videotrans.translator import run as run_trans
from videotrans.util.help_misc import vail_file
from videotrans.util.help_srt import get_subtitle_from_srt, delete_punc


class TranslateMixin:

    def _create_turn_suggestions(self, source_srt, target_srt):
        from videotrans import translator
        from videotrans.tts import QWEN3LOCAL_TTS

        if not self.should_dubbing \
                or self.cfg.translate_type != translator.JIUCAI_DRAMA_INDEX \
                or self.cfg.tts_type != QWEN3LOCAL_TTS \
                or str(self.cfg.voice_role).strip().lower() != 'clone':
            return

        suggestion_file = Path(self.cfg.cache_folder) / 'turn_suggestions.json'
        if suggestion_file.is_file():
            try:
                from videotrans.translator._jiucai import parse_turn_suggestions
                parse_turn_suggestions(
                    suggestion_file.read_text(encoding='utf-8'),
                    [item['line'] for item in source_srt],
                )
                return
            except (OSError, ValueError, json.JSONDecodeError):
                pass

        speaker_hints = []
        speaker_file = Path(self.cfg.cache_folder) / 'speaker.json'
        try:
            if speaker_file.is_file():
                speaker_hints = json.loads(speaker_file.read_text(encoding='utf-8'))
                if not isinstance(speaker_hints, list):
                    speaker_hints = []
        except (OSError, json.JSONDecodeError):
            pass

        try:
            from videotrans.translator._jiucai import suggest_turns
            suggestions = suggest_turns(source_srt, target_srt, speaker_hints)
            suggestion_file.write_text(
                json.dumps(suggestions, ensure_ascii=False, indent=2), encoding='utf-8'
            )
        except Exception as error:
            logger.warning(f'人物与发言轮次建议失败，回退音频说话人判断: {type(error).__name__}')

    def trans(self) -> None:
        _st=time.time()
        if self._exit() or not self.should_trans: return

        self.precent += 3
        self.signal(text=tr('starttrans'))

        if vail_file(self.cfg.target_sub):
            source_srt = get_subtitle_from_srt(self.cfg.source_sub, is_file=True)
            target_srt = get_subtitle_from_srt(self.cfg.target_sub, is_file=True)
            self._create_turn_suggestions(source_srt, target_srt)
            self.signal(
                text=Path(self.cfg.target_sub).read_text(encoding="utf-8", errors="ignore"),
                type='replace_subtitle'
            )
            return

        rawsrt = get_subtitle_from_srt(self.cfg.source_sub, is_file=True)
        self.signal(text=tr('kaishitiquhefanyi'))

        target_srt = run_trans(
            translate_type=self.cfg.translate_type,
            text_list=copy.deepcopy(rawsrt),
            uuid=self.uuid,
            source_code=self.cfg.source_language_code,
            target_code=self.cfg.target_language_code
        )
        if self._exit():  return

        target_srt = self.check_target_sub(rawsrt, target_srt)
        if not self.should_dubbing:
            for it in target_srt:
                it['text']=it['text'].strip('...')

        if self.cfg.app_mode=='tiqu':
            if self.cfg.fix_punc==2:
                logger.debug('仅提取模式下，移除所有标点')
                for it in rawsrt:
                    it['text']=delete_punc(it['text'])
                for it in target_srt:
                    it['text']=delete_punc(it['text'])
            self._save_srt_target(rawsrt, f"{self.cfg.target_dir}/{self.cfg.noextname}-{self.cfg.source_language_code}.srt")
            if self.cfg.output_srt > 0 and self.cfg.source_language_code != self.cfg.target_language_code:
                _source_srt_len = len(rawsrt)
                for i, it in enumerate(target_srt):
                    if i < _source_srt_len and self.cfg.output_srt == 1:
                        it['text'] = ("\n".join([rawsrt[i]['text'].strip(), it['text'].strip()])).strip()
                    elif i < _source_srt_len and self.cfg.output_srt == 2:
                        it['text'] = ("\n".join([it['text'].strip(), rawsrt[i]['text'].strip()])).strip()

        self._save_srt_target(target_srt, self.cfg.target_sub)
        self._create_turn_suggestions(rawsrt, target_srt)

        if self.cfg.app_mode == 'tiqu':
            _output_file = f"{self.cfg.target_dir}/{self.cfg.noextname}.srt"
            if self.cfg.copysrt_rawvideo:
                p = Path(self.cfg.name)
                _output_file = f'{p.parent.as_posix()}/{p.stem}.srt'
            if not Path(_output_file).exists():
                shutil.copy2(self.cfg.target_sub, _output_file)

        self.signal(text=tr('endtrans'))
        logger.debug(f'[字幕翻译阶段结束耗时]:{time.time()-_st}s')
