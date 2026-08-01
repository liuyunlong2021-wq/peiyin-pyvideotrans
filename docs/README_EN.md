# 赚钱音浪

**赚钱音浪 1.0.0** is a desktop workstation for short-drama translation and local voice cloning, built on [pyVideoTrans](https://github.com/jianchang512/pyvideotrans).

[中文说明](../README.md) | [Development Wiki](wiki/CLAUDE.md)

## Main Workflow

```text
Import video
  -> recognize and proofread Chinese subtitles with SenseVoice
  -> translate the full episode with a cloud model
  -> review characters, emotions, English lines, and speaking turns
  -> clone English speech with local Qwen3-TTS
  -> calibrate subtitles and timing
  -> compose the final video
```

Hard-subtitle removal is not included in this repository. Use the separate [subtitle-remover repository](https://github.com/liuyunlong2021-wq/qushuiyin-video-subtitle-remover) when needed, then import the processed video here.

## Source Installation

The simplest installation is to download `赚钱音浪-Windows.zip` or `赚钱音浪-macOS.zip` from [GitHub Releases](https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans/releases/latest), extract it, and open the launcher. The first launch prepares Python and runtime dependencies automatically. Model weights are still downloaded separately from the Qwen3-TTS settings.

Install Git, `uv`, FFmpeg, and libsndfile, then run:

```bash
git clone https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans.git
cd peiyin-pyvideotrans
uv sync
uv run sp.py
```

On Windows, use a project directory such as `D:\peiyin-pyvideotrans` and run `uv sync` there. `uv sync` must be run from the directory that contains `pyproject.toml`, not from `D:\` itself.

On macOS, after `uv sync`, you can also open `赚钱音浪.app` from the repository root. The app uses the repository's `.venv`; it does not bundle Python, dependencies, or model weights.

Configure the cloud API URL and key locally in Settings. Do not commit API keys or include them in logs and issues.

## Local Models

Qwen3-TTS defaults to `0.6B`; users with more capable hardware may select `1.7B`. Only the selected Base model is downloaded on first use. “Built-in” means the channel is supported by the application code, not that its model weights are part of the GitHub clone.

SenseVoice and emotion2vec models are also downloaded when their stages first need them. The tracked repository content is about 19 MB; `.venv/`, `models/`, logs, and task output are ignored by Git.

## Production Project

The experimental staged project has five stages:

1. Chinese recognition
2. Drama translation and speaking turns
3. English clone dubbing
4. Dubbing subtitle calibration
5. Final composition

The full automated test suite currently passes on macOS Apple Silicon (`490 passed`). Intel macOS, Windows, Linux, CUDA, and first-time model downloads still require verification on their target environments.

## License

This project is licensed under [GPL-v3](../LICENSE). Ensure that you have the right to process the source media and comply with the terms of any external API provider.
