# 赚钱音浪

<div align="center">

**本地短剧翻译与声音克隆工作台**

版本 `1.0.0` · [English](docs/README_EN.md) · [开发 Wiki](docs/wiki/CLAUDE.md)

[![License](https://img.shields.io/badge/License-GPL_v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10-green.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-489%20passed-brightgreen.svg)](tests)

<img src="videotrans/styles/logo.png" width="560" alt="赚钱音浪">

</div>

赚钱音浪基于开源项目 [pyVideoTrans](https://github.com/jianchang512/pyvideotrans) 开发，面向短剧出海配音场景：识别中文对白，结合整集上下文翻译成自然英文，再使用本地 Qwen3-TTS 克隆原演员音色，最终生成英文配音和字幕视频。

项目聚焦桌面端短剧字幕翻译主链，并保留必要的字幕处理、CLI 兼容、人工发言轮次校对、角色声音参考库和 Wiki 分阶段制作能力。

## 核心能力

- **整集剧情翻译**：不是逐句孤立翻译，而是把整集上下文交给大模型，生成更自然的美式口语对白。
- **本地声音克隆**：根据电脑性能选择 Qwen3-TTS 0.6B 或 1.7B，首次使用时只下载所选模型。
- **人工校对工作台**：同时查看视频、中文原文、英文字幕、人物建议、情绪和“接上句”关系。
- **完整发言轮次克隆**：同一角色连续说话时合并克隆，减少短参考音导致的音色漂移和开头瑕疵。
- **角色声音参考库**：保存同一角色不同情绪的已确认参考音，后续集数可继续复用。
- **字幕处理**：支持人工修正字幕、烧录英文硬字幕和音画同步。
- **两种制作方式**：保留稳定的一条龙完整流程，同时提供实验性的 Wiki 分阶段制作项目。

## 推荐工作流

```text
导入中文短剧视频
  -> 识别并校对中文字幕
  -> 按整集上下文翻译英文对白
  -> 校对人物、情绪、英文字幕和发言轮次
  -> 选择配音渠道并生成英文配音
  -> 校准字幕与时间轴
  -> 合成英文成片
```

翻译错误必须在开始配音前修正。遇到 `A -> B -> A` 的对话时，应人工确认人物和“接上句”，避免把不同角色错误合并成同一段配音。

主仓库不再包含去除原视频硬字幕功能。需要该预处理时，请单独部署[去硬字幕项目](https://github.com/liuyunlong2021-wq/qushuiyin-video-subtitle-remover)，处理完成后再把视频导入赚钱音浪。两个项目由各自的依赖清单管理环境；操作系统已经安装的 FFmpeg 等工具通常无需重复安装，Python 包仍由各自虚拟环境隔离。

## 小白本地部署教程

### 最简单方法：下载桌面启动包

打开 [GitHub Releases](https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans/releases/latest)，下载对应系统的文件：

- Windows：`赚钱音浪-Windows.zip`
- macOS：`赚钱音浪-macOS.zip`

解压后双击 `赚钱音浪.exe` 或 `赚钱音浪.app`。首次启动会自动准备 Python 3.10 和运行依赖，需要保持联网并等待完成；以后双击即可启动，不需要手动执行 Git、`uv sync` 或安装 Python。

发布包不包含模型。进入软件后，在 Qwen3-TTS 设置中选择 `0.6B` 或 `1.7B`，点击“下载所选模型”；软件只下载当前选择的模型。

### 推荐方法：让 AI 工具一键部署

电脑上已经安装 [Codex](https://openai.com/codex/) 或 Claude Code 的用户，打开工具后，把下面整段指令复制进去并发送。AI 会检查电脑环境、安装缺少的工具、下载项目并启动应用：

```text
请帮我在这台电脑上本地部署“赚钱音浪”，项目地址是：
https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans

请直接执行部署，不要只给我教程，并按以下要求操作：
1. 先检查我的操作系统，以及 Git、uv、FFmpeg 和 libsndfile 是否已经安装，只安装缺少的工具。
2. 不需要我手动安装 Python；使用 uv 根据项目 pyproject.toml 自动安装 Python 3.10 和全部必需依赖。
3. Windows 把项目克隆到 D:\peiyin-pyvideotrans；macOS 或 Linux 克隆到 Documents（文稿）目录。进入包含 pyproject.toml 的项目根目录后再执行 uv sync。
4. 不要修改项目源代码，不要填写或输出任何 API Key。
5. macOS 安装完成后启动项目根目录的“赚钱音浪.app”；Windows 或 Linux 执行 uv run sp.py。
6. 如果系统需要管理员权限、电脑密码或安全确认，先明确告诉我应该点击或输入什么。
7. 启动后确认出现“赚钱音浪 1.0.0”主窗口；如果失败，继续检查并修复，直到应用成功启动。
8. 最后用中文告诉我：安装到了哪个目录，以及以后如何再次启动。不要主动下载任何本地 TTS 模型。
```

执行过程中，系统如果弹出安装授权或密码窗口，需要用户本人确认。不要把 API Key、电脑密码发送给 AI；密码只在系统自己的密码窗口或终端提示中输入。

### 备用方法：手动部署

只有 AI 部署失败，或者电脑没有安装 AI 编程工具时，才需要阅读下面的手动教程。展开与你电脑系统对应的一项即可。

不需要提前安装 Python。项目执行 `uv sync` 时，会自动安装项目需要的 Python 3.10 和依赖。

<details>
<summary><strong>展开 macOS（苹果电脑）手动部署步骤</strong></summary>

### macOS（苹果电脑）

#### 第 1 步：打开终端

1. 同时按下 `Command + 空格`。
2. 输入“终端”。
3. 按回车，打开黑色或白色的终端窗口。

后面的命令都粘贴到这个窗口中。

#### 第 2 步：检查 Homebrew

粘贴并回车：

```bash
brew --version
```

- 如果出现 `Homebrew` 和版本号，直接进入第 3 步。
- 如果出现 `command not found: brew`，粘贴下面的官方安装命令：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装过程中可能要求输入电脑开机密码。输入密码时屏幕不会显示字符，这是正常现象，输入完成后按回车。安装结束后，按照终端最后显示的 `Next steps` 执行提示命令，然后关闭并重新打开终端，再执行一次 `brew --version`。

#### 第 3 步：安装基础工具

粘贴并回车：

```bash
brew install git uv ffmpeg libsndfile
```

等待命令执行结束，重新出现可以输入命令的一行后，再逐条检查：

```bash
git --version
```

```bash
uv --version
```

```bash
ffmpeg -version
```

三条命令都显示版本号，就可以继续。

#### 第 4 步：下载赚钱音浪

下面的命令会把项目下载到电脑的“文稿（Documents）”目录。逐条粘贴并回车：

```bash
cd ~/Documents
```

```bash
git clone https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans.git
```

```bash
cd peiyin-pyvideotrans
```

#### 第 5 步：安装项目依赖

```bash
uv sync
```

首次安装需要下载 Python 3.10 和项目依赖，时间取决于网络。不要关闭终端；命令执行完毕并重新出现可输入命令的一行，就表示安装完成。

#### 第 6 步：启动应用

确保终端仍在 `peiyin-pyvideotrans` 目录，然后执行：

```bash
open "赚钱音浪.app"
```

也可以打开“访达 -> 文稿 -> peiyin-pyvideotrans”，双击里面的 `赚钱音浪.app`。

首次启动如果 macOS 提示无法验证开发者，请不要把应用移走：在访达中右键 `赚钱音浪.app`，选择“打开”，再确认一次“打开”。看到“赚钱音浪 1.0.0”主窗口就表示部署成功。

以后启动时无需重复安装，直接双击仓库里的 `赚钱音浪.app` 即可。这个应用必须留在项目根目录，因为它需要使用项目里的 `.venv` 环境。

</details>

<details>
<summary><strong>展开 Windows 10 / 11 手动部署步骤</strong></summary>

### Windows 10 / 11

#### 第 1 步：打开 PowerShell

1. 点击开始菜单。
2. 输入 `PowerShell`。
3. 点击“Windows PowerShell”打开窗口。

后面的命令都粘贴到这个窗口中。

#### 第 2 步：检查基础工具

逐条粘贴并回车：

```powershell
git --version
```

```powershell
uv --version
```

```powershell
ffmpeg -version
```

显示版本号的工具已经安装，不需要重复安装。出现“无法将……识别为命令”时，按照下一步安装对应工具。

#### 第 3 步：安装缺少的工具

没有 Git 时执行：

```powershell
winget install --id Git.Git -e
```

没有 uv 时执行：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

没有 FFmpeg 时执行：

```powershell
winget install --id Gyan.FFmpeg -e
```

安装完成后，关闭 PowerShell，再重新打开。然后重新执行第 2 步的三条检查命令，确认它们都能显示版本号。

#### 第 4 步：下载赚钱音浪

逐条粘贴并回车：

```powershell
cd D:\
```

```powershell
git clone https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans.git D:\peiyin-pyvideotrans
```

```powershell
cd D:\peiyin-pyvideotrans
```

#### 第 5 步：安装项目依赖

```powershell
uv sync
```

首次安装需要下载 Python 3.10 和项目依赖。不要关闭 PowerShell；命令执行完毕并重新出现可输入命令的一行，就表示安装完成。

#### 第 6 步：启动应用

```powershell
uv run sp.py
```

看到“赚钱音浪 1.0.0”主窗口就表示部署成功。以后启动只需要打开 PowerShell，并依次执行：

```powershell
cd D:\peiyin-pyvideotrans
uv run sp.py
```

项目必须放在包含 `pyproject.toml` 的目录中；建议使用这个较短的英文路径，不要只在 `D:\` 根目录执行 `uv sync`。

</details>

<details>
<summary><strong>展开 Linux（Ubuntu / Debian）手动部署步骤</strong></summary>

### Linux（Ubuntu / Debian）

其他 Linux 发行版也可以使用，但需要用本系统的包管理器安装 Git、FFmpeg 和 libsndfile。下面以 Ubuntu / Debian 为例。

#### 第 1 步：打开终端

同时按下 `Ctrl + Alt + T`。后面的命令都粘贴到这个终端中。

#### 第 2 步：安装基础工具

逐条粘贴并回车：

```bash
sudo apt-get update
```

```bash
sudo apt-get install -y git ffmpeg libsndfile1-dev curl
```

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装过程中如果要求输入密码，输入电脑登录密码并按回车。安装完成后关闭终端，再重新打开。

#### 第 3 步：检查安装结果

逐条执行：

```bash
git --version
```

```bash
uv --version
```

```bash
ffmpeg -version
```

三条命令都显示版本号，就可以继续。

#### 第 4 步：下载赚钱音浪

逐条执行：

```bash
cd ~/Documents
```

如果系统提示没有 `Documents` 目录，先执行 `mkdir -p ~/Documents`，再执行上面的命令。

```bash
git clone https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans.git
```

```bash
cd peiyin-pyvideotrans
```

#### 第 5 步：安装并启动

```bash
uv sync
```

等待安装完成，然后执行：

```bash
uv run sp.py
```

看到“赚钱音浪 1.0.0”主窗口就表示部署成功。以后启动只需要打开终端，并依次执行：

```bash
cd ~/Documents/peiyin-pyvideotrans
uv run sp.py
```

</details>

### 可选的本地声音模型

安装应用时不会下载 Qwen3-TTS 模型。需要本地声音克隆时，再根据电脑性能选择：默认 `0.6B`，配置较高并追求质量可选择 `1.7B`。只有首次实际使用时才下载所选模型，部署工具不要预先替用户下载。界面中的“内置”表示软件原生支持，不表示模型权重已经放进仓库。

### 常见安装问题

- **提示 `command not found` 或“无法识别为命令”**：对应工具没有安装成功，或安装后没有重新打开终端。先重新打开终端，再检查版本。
- **`uv sync` 下载中断**：保持网络连接，在项目目录重新执行 `uv sync`，已经下载的内容通常不需要从头开始。
- **PowerShell 提示 `No pyproject.toml found`**：当前目录不是项目根目录。Windows 默认安装到 `D:\peiyin-pyvideotrans`，先执行 `cd D:\peiyin-pyvideotrans`，确认 `dir pyproject.toml` 能看到文件，再执行 `uv sync`。如果还没有克隆项目，执行 `git clone https://github.com/liuyunlong2021-wq/peiyin-pyvideotrans.git D:\peiyin-pyvideotrans`。
- **macOS 提示无法验证开发者**：在访达中右键应用选择“打开”，再确认一次；不要把 `.app` 单独移出项目目录。
- **双击 `.app` 提示需要先完成本地部署**：在该项目根目录执行 `uv sync`，并确认项目中已经生成 `.venv` 目录。
- **选择本地 Qwen3-TTS 后首次配音等待很久**：软件可能正在下载所选模型。保持网络连接；下载完成后不会重复下载。
- **出现 FFmpeg 相关错误**：重新执行 `ffmpeg -version`。如果没有版本信息，请按当前系统的安装步骤重新安装 FFmpeg。

## 首次配置

### 1. 翻译 API

在应用设置中填写：

- API URL，例如：`https://api.jiucaihezi.studio/v1`
- API Key
- 翻译模型

当前可选模型包括：

- `gemini-3.6-flash`
- `claude-fable-5`
- `claude-opus-5`
- `gpt-5.6-sol`
- `deepseek-v4-pro`

API Key 只保存在本机配置中。`videotrans/params.json` 和 `videotrans/cfg.json` 已被 Git 忽略，不要把真实 Key 写入 README、Wiki、Issue 或日志。

### 2. 本地声音克隆

本地声音克隆需要 Qwen3-TTS。默认选择 `0.6B`；性能足够并更看重质量时可选择 `1.7B`。模型首次使用时才会下载，且不会自动下载另一尺寸。

## 如何选择制作入口

### 翻译视频或音频

这是当前稳定的一条龙流程，适合直接完成一整集：

1. 选择视频或音频。
2. 选择识别、翻译和配音渠道。
3. 按提示校对中文字幕。
4. 校对英文字幕、人物、情绪和“接上句”。
5. 确认后开始配音和合成。

### 制作项目（实验）

这是 Wiki 驱动的分阶段入口，适合按集数保存并分别执行：

1. 中文识别（先选择并导入原视频）
2. 剧情翻译与轮次
3. 英文克隆配音
4. 配音字幕校准
5. 最终合成

每一步的人工文本写入项目 Wiki，媒体文件放在项目 `.raw/media/`。该入口已经完成短样片和自动测试，但仍保留“实验”标记；正式生产优先使用原完整流程。

## 可选入口

### CLI

```bash
# 音视频识别为字幕
uv run cli.py --task stt --name "./audio.wav" --model_name large-v3

# 翻译字幕
uv run cli.py --task sts --name "./subs.srt" --target_language_code en

# 视频翻译
uv run cli.py --task vtv --name "./video.mp4" \
  --source_language_code zh-cn --target_language_code en \
  --voice_role "en-US-GuyNeural"
```

完整参数见 [CLI 文档](docs/cli.md)。

## 字幕默认规范

- 字体：华康黑体 W9
- 字号：92 px
- 颜色：白色
- 描边：4 px，`#151210`
- 阴影：2 px
- 位置：画面底部 25%，水平居中
- 文本：去除标点

字体文件位于 `videotrans/styles/fonts/`，字幕样式可以在应用中继续调整。

## 验证状态

- macOS Apple Silicon 桌面应用启动通过
- Dock 名称、图标、版本和 Bundle ID 验证通过
- SenseVoice 中文识别通过
- 整集上下文剧情翻译通过
- 本地 Qwen3-TTS 1.7B 英文声音克隆通过；0.6B/1.7B 单选下载合同通过
- 字幕烧录、音画对齐和最终合成通过
- 全库自动测试：`490 passed`
- 当前 Git 跟踪内容约 19 MB；模型和 `.venv` 均不进入普通 GitHub 克隆

尚未完成 Intel Mac、Windows、Linux、Docker、CUDA 的本轮真机验收；不同平台首次安装和模型下载仍需单独验证。

## 文档

- [English README](docs/README_EN.md)
- [开发 Wiki 总入口](docs/wiki/CLAUDE.md)
- [部署与入口](docs/wiki/运维/部署与入口.md)
- [常见问题](docs/wiki/排障/常见问题.md)
- [剧情翻译与声音克隆 SDD](docs/wiki/开发/韭菜盒子剧情翻译与逐句声音克隆SDD.md)
- [Wiki 分阶段制作 SDD](docs/wiki/开发/Wiki驱动的分阶段配音制作SDD.md)
- [1.0.0 发布一致性检查](docs/wiki/巡检报告/赚钱音浪1.0.0发布一致性检查.md)

## 开源与致谢

本项目采用 [GPL-v3](LICENSE) 开源协议。赚钱音浪基于 [pyVideoTrans](https://github.com/jianchang512/pyvideotrans) 继续开发，并使用 FFmpeg、PySide6、SenseVoice、Qwen3-TTS 和 emotion2vec 等开源项目。

使用本软件处理视频、音频、字幕或调用第三方 API 时，请确保你拥有相应内容的合法使用权，并遵守所在地法律与服务商条款。
