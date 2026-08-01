$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Log = Join-Path $Root "bootstrap.log"
Set-Location $Root
Start-Transcript -Path $Log -Append | Out-Null

try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    }

    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw "电脑缺少 FFmpeg 和 winget，请先安装 FFmpeg。"
        }
        winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    }

    if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) {
        uv sync --locked
    }

    & (Join-Path $Root ".venv\Scripts\python.exe") (Join-Path $Root "sp.py")
}
catch {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("$($_.Exception.Message)`n`n详细日志：$Log", "赚钱音浪启动失败") | Out-Null
    exit 1
}
finally {
    Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
}
