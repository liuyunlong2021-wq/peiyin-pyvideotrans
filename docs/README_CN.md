> Sponsors: **[Recall.ai](https://www.recall.ai/product/meeting-transcription-api?utm_source=github&utm_medium=sponsorship&utm_campaign=jianchang512-pyvideotrans) - Meeting Transcription API**
>
> If you’re looking for a transcription API for meetings, consider checking out **[Recall.ai](https://www.recall.ai/product/meeting-transcription-api?utm_source=github&utm_medium=sponsorship&utm_campaign=jianchang512-pyvideotrans)** , an API that works with Zoom, Google Meet, Microsoft Teams, and more


---

# 赚钱音浪

<div align="center">

**赚钱音浪 1.0.0 - 本地短剧翻译与声音克隆工作台**

[English](../README.md) | [**文档**](https://pyvideotrans.com) | [**在线问答**](https://bbs.pyvideotrans.com) 

[![License](https://img.shields.io/badge/License-GPL_v3-blue.svg)](../LICENSE) [![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/) [![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

</div>

**赚钱音浪** 基于 GPL-v3 开源项目 pyVideoTrans 开发，新增整集上下文剧情翻译、人工发言轮次校对、本地 Qwen3-TTS 声音克隆、Wiki 分阶段制作和 macOS 品牌启动，同时保留原项目的 GUI、CLI 与 WebUI 能力。

<img width="1566" height="912" alt="image" src="https://github.com/user-attachments/assets/2d5bd178-3dc0-45ee-bc1c-dbb5f6705cf4" />

---

## ✨ 核心功能

> [技术架构与原理](architecture.md)

- **🎥 全自动视频翻译**: 一键完成：语音识别(ASR) → 字幕翻译 → 语音合成(TTS) → 视频合成。
- **🎙️ 语音转录 / 字幕生成**: 批量将音视频转为 SRT 字幕，支持 **说话人分离**，区分不同角色。
- **🗣️ 多角色 AI 配音**: 支持根据不同说话人分配不同的 AI 配音角色。
- **🧬 声音克隆**: 集成 **F5-TTS, CosyVoice, GPT-SoVITS** 等模型，支持零样本声音克隆。
- **🧠 强大的模型支持**:
  - **ASR**: Faster-Whisper (本地), OpenAI Whisper, 阿里 Qwen, 字节火山, Azure, Google 等。
  - **LLM 翻译**: DeepSeek, ChatGPT, Claude, Gemini, MiniMax, Ollama (本地), 阿里百炼等。
  - **TTS**: Edge-TTS (免费), OpenAI, Azure, Minimaxi, ChatTTS, ChatterBox 等。
- **🖥️ 交互式编辑**: 支持在识别、翻译、配音的每个阶段暂停并人工校对，确保精准度。
- **🛠️ 实用工具集**: 包含人声分离、视频/字幕合并、音画对齐、文稿匹配等辅助工具。
- **💻 命令行模式 (CLI)**: 支持无头模式运行，方便服务器部署或批处理。
- **🌐 Web 界面 (WebUI)**: 基于浏览器的界面，适合远程访问或局域网部署。

### 剧情翻译与声音克隆工作流

桌面 GUI 还支持面向短剧的整集上下文翻译和本地声音克隆：先校对中文字幕，再校对英文与“接上句”发言轮次，最后用本地 Qwen3-TTS 按完整发言段克隆。字幕仍逐句保留，适合人工修正个别翻译或拆分 `A → B → A` 的轮次。翻译和人物建议使用配置的韭菜盒子 API 和同一个可选模型；API Key 保存在本地配置中。

菜单中的“制作项目”提供实验性的 Wiki 分阶段入口：识别、翻译、配音、字幕确认和合成可以按集数保存并从人工确认处继续。项目媒体保存在项目的 `.raw/media/`，人工文本保存在 `wiki/`；阶段会在发布前核对输入快照，输入被修改时放弃临时结果，上游更新后下游状态会自动失效。该入口尚未替代原有完整流程，生产任务仍优先使用原流程。设计和当前验证边界见 [Wiki 驱动的分阶段配音制作 SDD](wiki/开发/Wiki驱动的分阶段配音制作SDD.md)。


---

## 🚀 上游 Windows 安装包

上游项目为 Windows 10/11 提供预打包 `.exe`，但它**不包含本仓库的全部定制功能**。使用赚钱音浪请按下方源码部署。

1. **下载**: [点击下载最新预打包版本](https://github.com/jianchang512/pyvideotrans/releases)
2. **解压**: 将压缩包解压到一个**不包含中文、空格**的路径下 (例如 `D:\pyVideoTrans`)。
3. **运行**: 双击文件夹内的 `sp.exe` 启动。

> **注意**:
> * 请勿直接在压缩包内运行。
> * 如需使用 GPU 加速，请确保安装 **CUDA 12.8** 和 **cuDNN 9.11**。

---

## 🛠️ 源码部署 (macOS / Linux / Windows 开发者)

推荐使用 **[`uv`](https://docs.astral.sh/uv/)** 进行包管理，速度更快且环境隔离更好。

### 1. 前置准备

* **Python**: 建议版本 3.10
* **FFmpeg**: 必须安装并配置到环境变量。
  * **macOS**: 
  ```
    brew install libsndfile  git  python@3.10
	
	brew uninstall --ignore-dependencies ffmpeg
	
	brew tap homebrew-ffmpeg/ffmpeg
	
	brew install homebrew-ffmpeg/ffmpeg/ffmpeg
  ```
  * **Linux (Ubuntu/Debian)**: `sudo apt-get install ffmpeg libsndfile1-dev`
  * **Windows**: [下载 FFmpeg](https://ffmpeg.org/download.html) 并配置 Path，或者直接将 ffmpeg.exe 和 ffprobe.exe 放在项目目录下

### 2. 安装 uv (如果尚未安装)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. 克隆与安装

```bash
git clone https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans.git
cd peiyin-pyvideotrans
uv sync
```

> 默认不安装 `whisper.net` 本地渠道，若需要全部安装请执行 `uv sync --all-extras`
> - 单独安装 `whisper.net`：`uv sync --extra dotnet`

这就是“赚钱音浪 1.0.0”的本地部署方式：仓库源码 + uv 虚拟环境，不需要安装 Python 全局包，也不需要预编译安装包。

### 4. 启动软件

**macOS 桌面应用**:
```bash
open "赚钱音浪.app"
```

执行 `uv sync` 后，可直接双击仓库根目录的 `赚钱音浪.app`。不要把 `.app` 单独移出仓库，它会读取当前仓库的 `.venv`；启动器同时支持 Apple Silicon 和 Intel Mac。

这个最小应用壳没有 Apple 开发者签名。若 macOS 首次拦截，请右键点击应用，选择“打开”，再确认一次“打开”。

**跨平台 GUI / 备用启动方式**:
```bash
uv run sp.py
```

启动后会打开桌面 GUI。macOS/Linux 使用上面的命令；Windows 使用同样的 `uv run sp.py`，或在已激活的虚拟环境中运行 `python sp.py`。

启动后，在设置中填写韭菜盒子 API URL/Key；声音克隆模式还需要本地 Qwen3-TTS 模型。完整设计与校对规则见 [剧情翻译与声音克隆 SDD](wiki/开发/韭菜盒子剧情翻译与逐句声音克隆SDD.md)。

**使用 CLI 命令行**:

```bash
# 视频翻译示例
uv run cli.py --task vtv --name "./video.mp4" --source_language_code zh-cn --target_language_code en --voice_role "en-US-GuyNeural"

# 语音转字幕示例
uv run cli.py --task stt --name "./audio.wav" --model_name large-v3

# 字幕翻译示例
uv run cli.py --task sts --name "./subs.srt" --target_language_code en

# 文字配音示例
uv run cli.py --task tts --name "./subs.srt" --voice_role "zh-CN-YunyangNeural"
```

> [CLI 详细参数说明](cli.md)

**启动 WebUI** (适合远程访问或局域网部署):
```bash
uv sync --extra webui
uv run webui.py
```


**Docker 部署** (容器化部署):
```bash
# 构建镜像
docker build -t pyvideotrans-webui .

# 运行
docker run -d -p 7860:7860 --name pyvideotrans pyvideotrans-webui

# 持久化配置和输出
docker run -d -p 7860:7860 \
  -v ./data/output:/app/output \
  -v ./data/config:/app/videotrans \
  --name pyvideotrans pyvideotrans-webui
```

> [WebUI 使用说明](webui.md)


### 5. (可选) GPU 加速配置

1. 如果您拥有 NVIDIA 显卡，请执行以下命令以安装支持 CUDA 的 PyTorch 版本：

```bash
# 卸载 CPU 版本
uv remove torch torchaudio

# 安装 CUDA 版本 (以 CUDA 12.x 为例)
uv add torch==2.7 torchaudio==2.7 --index-url https://download.pytorch.org/whl/cu128
uv add nvidia-cublas-cu12 nvidia-cudnn-cu12
```

2. [如果你使用 AMD 显卡，可查看该文档尝试加速](whisper_net_setup.md)

---

## 🧩 支持的渠道与模型 (部分)

| 类别 | 渠道/模型 | 说明 |
| :--- | :--- | :--- |
| **语音识别 (ASR)** | **Faster-Whisper** (本地) | 推荐，速度快，精度高 |
| | WhisperX / Parakeet | 支持时间轴对齐与说话人分离 |
| | 阿里 Qwen3-ASR / 字节火山 | 在线 API，中文效果极佳 |
| **翻译 (LLM/MT)** | **DeepSeek** / ChatGPT | 支持上下文理解，翻译更自然 |
| | MiniMax AI | MiniMax M3 大模型，最新旗舰模型，OpenAI兼容接口 |
| | Google / Microsoft | 传统机器翻译，速度快 |
| | Ollama / M2M100 | 完全本地离线翻译 |
| **语音合成 (TTS)** | **Edge-TTS** | 微软免费接口，效果自然 |
| | **F5-TTS / CosyVoice** | 支持 **声音克隆**，需本地部署 |
| | GPT-SoVITS / ChatTTS | 高质量开源 TTS |
| | 302.AI / OpenAI / Azure | 高质量商业 API |

---

## 📚 文档与支持

* **官方文档**: [https://pyvideotrans.com](https://pyvideotrans.com) (包含详细教程、API配置指南、常见问题)
* **在线问答社区**: [https://bbs.pyvideotrans.com](https://bbs.pyvideotrans.com) (提交报错日志，AI 自动分析回答)
* **GitHub Wiki**: [架构说明](architecture.md) | [CLI 文档](cli.md) | [WebUI 说明](webui.md) | [音画对齐原理](Synchronize.md) | [常见问题](faq.md)

## ⚠️ 免责声明

本软件为开源免费非商业项目，使用者需自行承担因使用本软件（包括但不限于调用第三方 API、处理受版权保护的视频内容）所产生的一切法律后果。请遵守当地法律法规及相关服务商的使用协议。

## 🙏 致谢

本项目主要依赖以下开源项目 (部分)：

* [FFmpeg](https://github.com/FFmpeg/FFmpeg)
* [PySide6](https://pypi.org/project/PySide6/)
* [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
* [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
* [openai-whisper](https://github.com/openai/whisper)
* [edge-tts](https://github.com/rany2/edge-tts)
* [F5-TTS](https://github.com/SWivid/F5-TTS)
* [Confucius4-TTS](https://github.com/netease-youdao/Confucius4-TTS)
* [OmniVoice](https://github.com/k2-fsa/omnivoice)
* [CosyVoice](https://github.com/FunAudioLLM/CosyVoice)
* [Gradio](https://www.gradio.app/) (WebUI)

---

*Created by [jianchang512](https://github.com/jianchang512)*
