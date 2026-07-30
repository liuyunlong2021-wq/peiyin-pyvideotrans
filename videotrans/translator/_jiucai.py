import re
from dataclasses import dataclass

from videotrans.configure.config import params
from videotrans.translator._openaicompat import OpenAICampat


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
