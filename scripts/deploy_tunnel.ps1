# deploy_tunnel.ps1 — 一键启动本地 Flask + Cloudflare Quick Tunnel（免账号）
#
# 用途：用 cloudflared 的 Quick Tunnel 把本地 Flask 暴露成一个公网 https 链接，
#       用于演示/验收，无需云服务器、无需注册。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\deploy_tunnel.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\deploy_tunnel.ps1 -Port 5000
#   powershell -ExecutionPolicy Bypass -File scripts\deploy_tunnel.ps1 -CloudflaredPath C:\path\to\cloudflared.exe
#
# 前置：
#   - 已装 Python 依赖（`pip install -r backend/requirements.txt`，全局或 venv）
#   - 前端 dist 不存在时脚本会自动 `npm run build`
#   - 已配置 .env（QWEN_API_KEY / QWEN_BASE_URL / TEXT_PROVIDER 等）
#
# 注意：Quick Tunnel 是临时链接，电脑关机或进程结束后失效；重跑本脚本会得到新链接。

[CmdletBinding()]
param(
    [int]$Port = 5000,
    [string]$CloudflaredPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot   # scripts/ 的上一级（仓库根）

Write-Host "== HKU Recycling Helper — 部署（Quick Tunnel）==" -ForegroundColor Cyan

# 1. 定位 cloudflared.exe
if (-not $CloudflaredPath) {
    $candidates = @(
        (Join-Path $RepoRoot "..\cloudflared.exe"),
        (Join-Path $RepoRoot "cloudflared.exe")
    )
    foreach ($c in $candidates) {
        $full = Resolve-Path $c -ErrorAction SilentlyContinue
        if ($full) { $CloudflaredPath = $full.Path; break }
    }
}
if (-not $CloudflaredPath -or -not (Test-Path $CloudflaredPath)) {
    Write-Host "[!] 未找到 cloudflared.exe。请下载后放到仓库上一级目录，或用 -CloudflaredPath 指定：" -ForegroundColor Red
    Write-Host "    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    exit 1
}
Write-Host "[1/5] cloudflared: $CloudflaredPath"

# 2. 前端构建（缺失时自动构建）
$distIndex = Join-Path $RepoRoot "frontend\dist\index.html"
if (-not (Test-Path $distIndex)) {
    Write-Host "[2/5] 前端未构建，正在 npm run build ..."
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[2/5] 前端已构建（dist 存在）"
}

# 3. 启动 Flask
$flaskOut = Join-Path $env:TEMP "recycling_flask_out.log"
$flaskErr = Join-Path $env:TEMP "recycling_flask_err.log"
$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[3/5] 端口 $Port 已被占用（PID $($existing.OwningProcess)），跳过 Flask 启动"
} else {
    Write-Host "[3/5] 启动 Flask（127.0.0.1:$Port）..."
    $flaskProc = Start-Process -FilePath "python" -ArgumentList @("-m","flask","--app","backend.app","run","--host","127.0.0.1","--port","$Port") `
        -WorkingDirectory $RepoRoot -RedirectStandardOutput $flaskOut -RedirectStandardError $flaskErr -WindowStyle Hidden -PassThru
    Write-Host "      Flask PID: $($flaskProc.Id)"
}

# 4. 等待健康检查
Write-Host "[4/5] 等待 Flask 就绪（首次加载模型可能需要 30–60 秒）..."
$health = $null
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3 -ErrorAction Stop
        if ($health.status -eq "ok") { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    Write-Host "[!] Flask 未就绪，请查看日志：$flaskErr" -ForegroundColor Red
    exit 1
}
Write-Host "      Flask 就绪（provider=$($health.text_provider), reachable=$($health.text_provider_reachable)）"

# 5. 启动隧道并提取链接
Write-Host "[5/5] 启动 Cloudflare Quick Tunnel ..."
$tunnelOut = Join-Path $env:TEMP "recycling_tunnel_out.log"
$tunnelErr = Join-Path $env:TEMP "recycling_tunnel_err.log"
$tunnelProc = Start-Process -FilePath $CloudflaredPath -ArgumentList @("tunnel","--url","http://127.0.0.1:$Port","--no-autoupdate") `
    -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr -WindowStyle Hidden -PassThru

$url = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $log = Get-Content $tunnelErr -Raw -ErrorAction SilentlyContinue
    if ($log -and $log -match "https://[a-z0-9-]+\.trycloudflare\.com") {
        $url = $Matches[0]
        break
    }
}

if (-not $url) {
    Write-Host "[!] 未获取到隧道链接，请查看日志：$tunnelErr" -ForegroundColor Red
    Write-Host "    （Flask 与 cloudflared 进程仍在运行，可手动查看日志获取链接）"
    exit 1
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  部署完成！公开访问链接："
Write-Host "  $url" -ForegroundColor Cyan
Write-Host ""
Write-Host "  说明：链接为临时 Quick Tunnel，电脑关机/进程结束后失效。"
Write-Host "  停止服务：结束 python 与 cloudflared 进程（或重启电脑）。"
Write-Host "======================================================" -ForegroundColor Green
