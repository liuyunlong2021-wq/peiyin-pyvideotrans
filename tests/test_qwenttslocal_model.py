from unittest.mock import patch

from videotrans.tts._qwenttslocal import QwenttsLocal, download_qwen_base, selected_qwen_model


def test_qwen_local_uses_selected_model_and_downloads_only_its_base():
    task = object.__new__(QwenttsLocal)
    task.model_name = "0.6B"
    task.queue_tts = [{"role": "clone"}]
    task._process_callback = lambda _data: None

    with patch("videotrans.util.help_down.check_and_down_ms") as download:
        task._download()

    assert download.call_count == 1
    assert download.call_args.args[0] == "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

    with patch("videotrans.tts._qwenttslocal.params.get", return_value="1.7B"):
        assert selected_qwen_model() == "1.7B"
    with patch("videotrans.tts._qwenttslocal.params.get", return_value="unknown"):
        assert selected_qwen_model() == "0.6B"


def test_download_button_downloads_only_selected_base_model():
    with patch("videotrans.tts._qwenttslocal.defaulelang", "zh"), patch(
        "videotrans.util.help_down.check_and_down_ms"
    ) as download:
        local_dir = download_qwen_base("1.7B")

    assert local_dir.endswith("Qwen3-TTS-12Hz-1.7B-Base")
    download.assert_called_once()
    assert download.call_args.args[0] == "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
