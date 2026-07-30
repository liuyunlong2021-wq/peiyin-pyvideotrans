import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from videotrans.configure.config import params
from videotrans.task.taskcfg import SrtItem
from videotrans.translator import JIUCAI_DRAMA_INDEX
from videotrans.translator._jiucai import JiuCaiDrama, parse_turn_suggestions, suggest_turns
from videotrans.tts._jiucaiclone import JiuCaiClone, api_base, api_origin
from videotrans.task._stage_recogn import RecognMixin
from videotrans.util.help_role import role_menu


def srt(line, text):
    return SrtItem(
        line=line, text=text, start_time=(line - 1) * 1000, end_time=line * 1000,
        startraw=f"00:00:0{line - 1},000", endraw=f"00:00:0{line},000",
        time=f"00:00:0{line - 1},000 --> 00:00:0{line},000",
    )


def test_drama_translation_sends_complete_srt_once(monkeypatch):
    monkeypatch.setattr(params, "jiucai_api", "https://example.com/v1")
    monkeypatch.setattr(params, "jiucai_key", "test-key")
    items = [srt(1, "你是谁？"), srt(2, "我是你哥哥。")]
    channel = JiuCaiDrama(
        translate_type=JIUCAI_DRAMA_INDEX, text_list=items, is_test=True,
        source_code="zh-cn", target_code="en", target_language_name="English",
    )
    calls = []

    def translate(value):
        calls.append(value)
        return value.replace("你是谁？", "Who are you?").replace("我是你哥哥。", "I'm your brother.")

    monkeypatch.setattr(channel, "_item_task", translate)
    result = channel.run()
    assert channel.model_name == "gemini-3.6-flash"
    assert channel.aisendsrt is True
    assert channel.trans_thread == 2
    assert len(calls) == 1 and "你是谁？" in calls[0] and "我是你哥哥。" in calls[0]
    assert [item.text for item in result] == ["Who are you?", "I'm your brother."]


def test_drama_translation_restores_missing_srt_block_separator(monkeypatch):
    monkeypatch.setattr(params, "jiucai_api", "https://example.com/v1")
    monkeypatch.setattr(params, "jiucai_key", "test-key")
    channel = JiuCaiDrama(translate_type=JIUCAI_DRAMA_INDEX, text_list=[], is_test=True)
    monkeypatch.setattr(
        "videotrans.translator._openaicompat.OpenAICampat._item_task",
        lambda *_: "1\n00:00:00,000 --> 00:00:01,000\nHello\n2\n00:00:01,000 --> 00:00:02,000\nBye",
    )
    assert channel._item_task("") == "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n2\n00:00:01,000 --> 00:00:02,000\nBye"


def test_turn_suggestions_match_every_subtitle_line():
    result = parse_turn_suggestions(json.dumps([
        {"line": 1, "speaker": "speaker1", "join_previous": False},
        {"line": 2, "speaker": "Speaker2", "join_previous": False},
        {"line": 3, "speaker": "Speaker2", "join_previous": True},
    ]), [1, 2, 3])

    assert result == [
        {"line": 1, "speaker": "Speaker1", "join_previous": False},
        {"line": 2, "speaker": "Speaker2", "join_previous": False},
        {"line": 3, "speaker": "Speaker2", "join_previous": True},
    ]


def test_turn_suggestions_reject_invalid_first_join():
    with pytest.raises(ValueError, match="first subtitle"):
        parse_turn_suggestions(json.dumps([
            {"line": 1, "speaker": "Speaker1", "join_previous": True},
        ]), [1])


def test_turn_suggestions_use_fixed_model_and_audio_hints(monkeypatch):
    monkeypatch.setattr(params, "jiucai_api", "https://example.com/v1")
    monkeypatch.setattr(params, "jiucai_key", "test-key")
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps([
                {"line": 1, "speaker": "Speaker1", "join_previous": False},
                {"line": 2, "speaker": "Speaker1", "join_previous": True},
            ])))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr('videotrans.translator._jiucai.OpenAI', lambda **_: fake_client)

    result = suggest_turns(
        [srt(1, "快走"), srt(2, "别回头")],
        [srt(1, "Go!"), srt(2, "Don't look back.")],
        ['spk7', 'spk7'],
    )

    assert captured['model'] == 'gemini-3.6-flash'
    assert '"audio_speaker": "spk7"' in captured['messages'][1]['content']
    assert result[1]['join_previous'] is True


def test_jiucai_url_normalization():
    assert api_base("https://api.example.com/v1/") == "https://api.example.com/v1"
    assert api_base("https://api.example.com") == "https://api.example.com/v1"
    assert api_origin("https://api.example.com/v1") == "https://api.example.com"


def test_cloud_clone_has_clone_role():
    assert role_menu(34, "en") == ["No", "clone"]


class Response:
    def __init__(self, data=None, content=b"", content_type="application/json", status=200):
        self.data = data
        self.content = content
        self.status_code = status
        self.ok = status < 400
        self.headers = {"Content-Type": content_type}

    def json(self):
        return self.data

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


def test_cloud_clone_contract(monkeypatch, tmp_path):
    key = "must-not-leak"
    monkeypatch.setattr(params, "jiucai_api", "https://api.example.com/v1")
    monkeypatch.setattr(params, "jiucai_key", key)
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"reference")
    output = tmp_path / "line.wav"
    calls = []

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        if url.endswith("app-directory"):
            return Response({"data": [{"label": "声音克隆", "outputType": "audio", "webappId": "app-1", "billingModel": "clone-billing"}]})
        if url.endswith("app-info"):
            return Response({"nodeInfoList": [
                {"nodeId": "4", "fieldName": "file", "fieldType": "AUDIO", "description": "参考音频"},
                {"nodeId": "36", "fieldName": "text", "description": "参考音频文字内容"},
                {"nodeId": "11", "fieldName": "text", "description": "输出音频文字内容"},
                {"nodeId": "1", "fieldName": "语言", "description": "语言"},
            ]})
        if "/rh/tasks/" in url:
            return Response({"status": "success", "results": [{"url": "https://cdn.example.com/result.mp3"}]})
        if url == "https://cdn.example.com/result.mp3":
            return Response(content=b"audio", content_type="audio/mpeg")
        raise AssertionError(url)

    def post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        if url.endswith("/v1/audio/speech"):
            body = kwargs["json"]
            assert body["model"] == "clone-billing"
            assert body["input"] == "I'm your brother."
            assert body["extra_fields"] == {"webappId": "app-1"}
            assert body["voice"].startswith("__rh_nodeinfo__")
            nodes = body["nodeInfoList"]
            assert next(n for n in nodes if n["nodeId"] == "4")["fieldValue"].startswith("data:audio/wav;base64,")
            assert next(n for n in nodes if n["nodeId"] == "36")["fieldValue"] == "我是你哥哥。"
            assert next(n for n in nodes if n["nodeId"] == "11")["fieldValue"] == "I'm your brother."
            return Response({"task_id": "123", "status": "processing", "ai_app": True})
        raise AssertionError(url)

    monkeypatch.setattr("videotrans.tts._jiucaiclone.requests.get", get)
    monkeypatch.setattr("videotrans.tts._jiucaiclone.requests.post", post)
    monkeypatch.setattr("videotrans.tts._jiucaiclone.time.sleep", lambda _: None)
    monkeypatch.setattr(JiuCaiClone, "convert_to_wav", lambda self, source, target: Path(target).write_bytes(Path(source).read_bytes()))

    channel = JiuCaiClone(queue_tts=[{
        "text": "I'm your brother.", "role": "clone", "ref_wav": str(ref),
        "ref_text": "我是你哥哥。", "filename": str(output),
    }], language="en", tts_type=34)
    channel._run(channel.queue_tts[0])
    assert output.read_bytes() == b"audio"
    assert not any(url.endswith("/api/creations/uploads") for _, url, _ in calls)
    assert key not in json.dumps([(method, url) for method, url, _ in calls])


def test_clone_directory_error_uses_registered_app(monkeypatch):
    monkeypatch.setattr(params, "jiucai_api", "https://api.example.com/v1")
    monkeypatch.setattr(params, "jiucai_key", "test-key")
    class Response:
        status_code = 200
        def json(self):
            return {"code": 412, "msg": "TOKEN_INVALID"}
        def raise_for_status(self):
            return None
    def get(url, **kwargs):
        if url.endswith("app-directory"):
            return Response()
        return type("Info", (), {
            "status_code": 200,
            "json": lambda self: {"nodeInfoList": [{"fieldName": "audio", "fieldType": "AUDIO"}]},
            "raise_for_status": lambda self: None,
        })()
    monkeypatch.setattr("videotrans.tts._jiucaiclone.requests.get", get)
    app, nodes = JiuCaiClone(queue_tts=[{"text": "x"}], language="en", tts_type=34)._discover()
    assert app["webappId"] == "2046193597401276417"
    assert app["billingModel"] == "rh-aiapp-voice-clone"
    assert nodes


def test_auth_error_does_not_expose_key(monkeypatch, tmp_path):
    monkeypatch.setattr(params, "jiucai_api", "https://api.example.com/v1")
    monkeypatch.setattr(params, "jiucai_key", "secret-value")
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"reference")
    channel = JiuCaiClone(queue_tts=[{
        "text": "Hello", "role": "clone", "ref_wav": str(ref),
        "ref_text": "你好", "filename": str(tmp_path / "out.wav"),
    }], language="en", tts_type=34)
    with pytest.raises(Exception) as error:
        channel._json(Response({}, status=401))
    assert "secret-value" not in str(error.value)


def test_cloud_clone_reports_missing_reference_before_request(monkeypatch, tmp_path):
    monkeypatch.setattr(params, "jiucai_api", "https://api.example.com/v1")
    monkeypatch.setattr(params, "jiucai_key", "test-key")
    channel = JiuCaiClone(queue_tts=[{
        "line": 3, "text": "Tongtong!", "role": "clone",
        "ref_wav": str(tmp_path / "missing.wav"), "ref_text": "童童",
        "filename": str(tmp_path / "out.wav"),
    }], language="en", tts_type=34)
    with pytest.raises(Exception, match="第 3 句参考音频不存在"):
        channel._run(channel.queue_tts[0])


def test_cloud_clone_keeps_remote_failure_detail(monkeypatch):
    monkeypatch.setattr(params, "jiucai_api", "https://api.example.com/v1")
    monkeypatch.setattr(params, "jiucai_key", "test-key")
    channel = JiuCaiClone(queue_tts=[{"text": "x"}], language="en", tts_type=34)
    monkeypatch.setattr(channel, "_json", lambda _: {"status": "failed", "msg": "reference rejected"})
    monkeypatch.setattr("videotrans.tts._jiucaiclone.requests.get", lambda *_, **__: object())
    monkeypatch.setattr("videotrans.tts._jiucaiclone.time.sleep", lambda _: None)
    with pytest.raises(Exception, match="reference rejected"):
        channel._poll("123")


def test_cloud_clone_extends_short_reference(monkeypatch, tmp_path):
    vocal = tmp_path / "vocal.wav"
    vocal.write_bytes(b"vocal")
    ref = tmp_path / "clone.wav"
    calls = []

    def cut(**kwargs):
        calls.append(kwargs)
        Path(kwargs["out_file"]).write_bytes(b"clip")
        return True

    monkeypatch.setattr("videotrans.task._stage_recogn.cut_from_audio", cut)
    task = SimpleNamespace(
        clone_ref=str(vocal),
        cfg=SimpleNamespace(source_wav=str(vocal), cache_folder=str(tmp_path), name="", tts_type=34),
        queue_tts=[{
            "line": 5, "startraw": "00:00:29,430", "endraw": "00:00:29,890",
            "start_time": 29430, "end_time": 29890,
            "start_time_source": 29430, "end_time_source": 29890,
            "ref_wav": str(ref),
        }],
    )
    RecognMixin._create_ref_from_vocal(task)
    assert (calls[0]["ss"], calls[0]["to"]) == ("00:00:29,360", "00:00:29,960")
