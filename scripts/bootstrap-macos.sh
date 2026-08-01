#!/bin/zsh
set -eu
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/bootstrap.log"
exec > >(tee -a "$LOG") 2>&1
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  /usr/bin/osascript -e 'display notification "首次启动正在安装运行环境，请保持联网" with title "赚钱音浪"' || true
fi

show_error() {
  /usr/bin/osascript -e "display alert \"赚钱音浪启动失败\" message \"$1\n\n详细日志：$LOG\"" || true
  exit 1
}

if ! command -v uv >/dev/null 2>&1; then
  /usr/bin/curl -LsSf https://astral.sh/uv/install.sh | /bin/sh || show_error "无法安装 uv，请检查网络。"
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    /bin/bash -c "$(/usr/bin/curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || show_error "无法安装 Homebrew。"
    export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  fi
  brew install ffmpeg libsndfile || show_error "无法安装 FFmpeg。"
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  uv sync --locked || show_error "运行环境安装失败，请检查网络和磁盘空间。"
fi

/usr/bin/open "$ROOT/赚钱音浪.app"
