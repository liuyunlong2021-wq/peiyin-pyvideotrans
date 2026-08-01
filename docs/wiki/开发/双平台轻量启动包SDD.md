# 双平台轻量启动包 SDD

> 状态：v1.0.0 已发布 Windows/macOS 包；v1.0.1 增加 Intel Mac 原生构建与运行环境验证
> 日期：2026-08-01

## 目标

GitHub Releases 提供 Windows 和 macOS 两个轻量 ZIP。用户解压后双击启动器；首次启动自动准备运行环境，之后直接进入赚钱音浪。模型不进入发布包，用户在 Qwen3-TTS 设置中选择 `0.6B` 或 `1.7B` 后单独下载。

## 发布合同

- Windows：解压 `ZhuanqianYinlang-Windows.zip`，双击 `赚钱音浪.exe`。
- macOS Apple Silicon：解压 `ZhuanqianYinlang-macOS.zip`，双击 `赚钱音浪.app`。
- macOS Intel：解压 `ZhuanqianYinlang-macOS-Intel.zip`，双击 `赚钱音浪.app`。
- ZIP 包含应用源码和启动器，不包含 `.venv/`、`models/`、日志、任务产物和 API Key。
- 首次启动自动安装 `uv`、同步 Python 3.10 与依赖；缺少 FFmpeg 时自动安装或给出明确错误。
- 环境准备完成后直接运行 `sp.py`；重复启动不重复安装。

## 实施

1. 增加 Windows/macOS 自举脚本和原生启动入口。
2. Qwen3-TTS 设置页增加“下载所选模型”按钮，复用现有下载函数。
3. 替换失效的 PyInstaller workflow，使用 GitHub Actions 生成两个轻量 ZIP。
4. 更新 README，说明 Releases 下载和模型边界。

## 验收

- 本地 macOS 从无 `.venv` 的临时发布目录进入安装分支，现有环境进入快速启动分支。
- Windows workflow 能编译启动器并校验 ZIP 内存在启动器、源码和 `pyproject.toml`。
- Intel Mac workflow 在 `macos-15-intel` 原生 runner 同步锁定环境，并导入 PySide6、Torch 和 ONNX Runtime。
- 两个平台发布包均不含模型和虚拟环境。
- Qwen 下载按钮只下载当前所选 Base 模型。
- 全库测试、编译、JSON 和 `git diff --check` 通过。

## 边界

首次安装需要联网并可能持续较长时间。macOS 未配置公证时仍可能需要右键“打开”；Windows 未签名时可能显示 SmartScreen。签名、公证和完全离线大包后续按真实发布需求处理，不阻塞轻量包。
