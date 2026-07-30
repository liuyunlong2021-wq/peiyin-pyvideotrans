import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from videotrans.configure.config import params
from videotrans.configure.excepts import StopTask
from videotrans.tts._base import BaseTTS


def api_base(value):
    value = str(value or "").strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise StopTask("韭菜盒子 API URL 无效")
    return value if urlsplit(value).path.rstrip("/").endswith("/v1") else value + "/v1"


def api_origin(value):
    parts = urlsplit(api_base(value))
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def _url(data):
    if isinstance(data, str):
        return data if data.startswith(("http://", "https://")) else ""
    if isinstance(data, list):
        return next((url for item in data if (url := _url(item))), "")
    if isinstance(data, dict):
        for key in ("url", "audio_url", "audioUrl", "result_url", "output"):
            if url := _url(data.get(key)):
                return url
        for key in ("data", "result", "results", "content", "audio", "file"):
            if url := _url(data.get(key)):
                return url
    return ""


def _task_id(data):
    if not isinstance(data, dict):
        return ""
    for value in (data.get("rh_task_id"), data.get("task_id"), data.get("taskId"), data.get("id")):
        if value:
            return str(value)
    return _task_id(data.get("data"))


@dataclass
class JiuCaiClone(BaseTTS):
    def __post_init__(self):
        super().__post_init__()
        self.api_url = api_base(params.get("jiucai_api"))
        self.api_key = str(params.get("jiucai_key") or "").strip()
        if not self.api_key:
            raise StopTask("请先配置韭菜盒子 API Key")
        self.dub_nums = 1
        self.headers = {"Authorization": f"Bearer {self.api_key}", "x-api-key": self.api_key}

    def _json(self, response):
        if response.status_code in (401, 403):
            raise StopTask("韭菜盒子 API Key 无效或无权限")
        if response.status_code == 429:
            raise StopTask("韭菜盒子 API 请求过于频繁")
        try:
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise StopTask(f"韭菜盒子 API 请求失败 ({response.status_code})") from exc
        except ValueError as exc:
            raise StopTask("韭菜盒子 API 返回了无效数据") from exc

    def _discover(self):
        directory = self._json(requests.get(
            f"{api_origin(self.api_url)}/api/runninghub/app-directory",
            headers=self.headers, timeout=30,
        ))
        raw_apps = directory.get("data", []) if isinstance(directory, dict) else directory
        apps = raw_apps if isinstance(raw_apps, list) else (
            raw_apps.get("records", []) if isinstance(raw_apps, dict) else []
        )
        app = next((item for item in apps if item.get("outputType") == "audio" and
                    any(word in str(item.get("label", "")).lower() for word in ("声音克隆", "voice clone", "voice-clone"))), None)
        if not app:
            # ponytail: directory currently returns TOKEN_INVALID; use the registered clone app until directory auth is fixed.
            app = {"webappId": "2046193597401276417", "billingModel": "rh-aiapp-voice-clone", "outputType": "audio"}
        info = self._json(requests.get(
            f"{api_origin(self.api_url)}/api/runninghub/app-info",
            params={"webappId": app["webappId"]}, headers=self.headers, timeout=30,
        ))
        return app, info.get("nodeInfoList", [])

    @staticmethod
    def _nodes(nodes, audio_url, ref_text, text):
        result = []
        mapped = {"audio": False, "text": False}
        for source in nodes:
            node = dict(source)
            field = str(node.get("fieldName", "")).lower()
            label = " ".join(str(node.get(key, "")).lower()
                             for key in ("fieldName", "fieldType", "description", "nodeName"))
            if "参考" in label and any(word in label for word in ("文字", "文本", "内容", "text")):
                node["fieldValue"] = ref_text
            elif field == "audio" or "audio" in label or "参考音频" in label:
                node["fieldValue"] = audio_url
                mapped["audio"] = True
            elif field == "text" or any(word in label for word in ("输出", "合成", "文稿")):
                node["fieldValue"] = text
                mapped["text"] = True
            elif field in ("语言", "language") or "语言" in label:
                node["fieldValue"] = "English"
            result.append(node)
        if not all(mapped.values()):
            raise StopTask("声音克隆应用缺少参考音频或输出文本节点")
        return result

    def _poll(self, task_id):
        deadline = time.time() + 600
        path = f"/v1/videos/{task_id}" if task_id.startswith("task_") else f"/rh/tasks/{task_id}?ai_app=true"
        while time.time() < deadline:
            data = self._json(requests.get(f"{api_origin(self.api_url)}{path}", headers=self.headers, timeout=30))
            if url := _url(data):
                return url
            status = str(data.get("status", "")).lower()
            if status in ("failed", "failure", "error", "cancelled", "canceled"):
                detail = str(data.get("message") or data.get("msg") or data.get("error") or "").strip()
                raise StopTask(f"声音克隆任务执行失败{': ' + detail[:300] if detail else ''}")
            time.sleep(5)
        raise StopTask("声音克隆任务等待超时")

    def _run(self, data_item, idx=-1):
        ref_wav = data_item.get("ref_wav", "")
        if not ref_wav or not Path(ref_wav).is_file():
            raise StopTask(f"第 {data_item.get('line', idx + 1)} 句参考音频不存在，请重新开始任务")
        ref_text = str(data_item.get("ref_text") or "").strip()
        app, discovered_nodes = self._discover()
        ref_data = "data:audio/wav;base64," + base64.b64encode(Path(ref_wav).read_bytes()).decode()
        nodes = self._nodes(discovered_nodes, ref_data, ref_text, data_item["text"].strip())
        encoded = base64.b64encode(json.dumps(nodes, ensure_ascii=False).encode()).decode()
        response = requests.post(
            f"{self.api_url}/audio/speech",
            json={
                "model": app["billingModel"],
                "input": data_item["text"].strip(),
                "voice": "__rh_nodeinfo__" + encoded,
                "nodeInfoList": nodes,
                "extra_fields": {"webappId": app["webappId"]},
            },
            headers={**self.headers, "Content-Type": "application/json"}, timeout=120,
        )
        content_type = response.headers.get("Content-Type", "")
        tmp = data_item["filename"] + ".jiucai.audio"
        if response.ok and content_type.startswith("audio/"):
            Path(tmp).write_bytes(response.content)
        else:
            submitted = self._json(response)
            audio_url = _url(submitted) or (self._poll(_task_id(submitted)) if _task_id(submitted) else "")
            if not audio_url:
                raise StopTask("声音克隆任务未返回音频地址或任务 ID")
            downloaded = requests.get(audio_url, timeout=120)
            downloaded.raise_for_status()
            Path(tmp).write_bytes(downloaded.content)
        self.convert_to_wav(tmp, data_item["filename"])
