# ComfyUI backend (:8188) first, then Vite dev (:5173). Open http://localhost:5173
param(
    [string]$ComfyUrl = "http://127.0.0.1:8188",
    [int]$BackendTimeoutSec = 180
)

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path "$PSScriptRoot\..").Path

. "$PSScriptRoot\lib\frontend-env.ps1"

& "$PSScriptRoot\stop-comfyui.ps1"

$python = if ($env:SEMENTIC_PYTHON) {
    $env:SEMENTIC_PYTHON
} else {
    (Get-Command python -ErrorAction Stop).Source
}

Write-Host ""
Write-Host "Starting ComfyUI backend on :8188 ..."
$env:PYTHONUNBUFFERED = "1"
$backend = Start-Process -FilePath $python `
    -ArgumentList "main.py", "--disable-auto-launch" `
    -WorkingDirectory $workspace `
    -PassThru `
    -NoNewWindow

try {
    Wait-SementicComfyUiBackend -ComfyUrl $ComfyUrl -TimeoutSec $BackendTimeoutSec

    Write-Host ""
    Write-Host "Backend ready. Starting Vite dev -> http://localhost:5173"
    Write-Host ""

    & "$PSScriptRoot\dev-sementic-frontend.ps1" -ComfyUrl $ComfyUrl
} finally {
    Write-Host ""
    Write-Host "Stopping ComfyUI backend ..."
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
    & "$PSScriptRoot\stop-comfyui.ps1"
}
