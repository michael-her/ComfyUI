# Vite dev server with HMR. Open http://localhost:5173 (ComfyUI backend on :8188).
param(
    [string]$FrontendRoot = "$PSScriptRoot\..\frontend\ComfyUI_frontend",
    [string]$OverridesRoot = "$PSScriptRoot\..\frontend\overrides",
    [string]$ComfyUrl = "http://127.0.0.1:8188"
)

. "$PSScriptRoot\lib\frontend-env.ps1"

$env = Initialize-SementicFrontendEnv -FrontendRoot $FrontendRoot
Apply-SementicFrontendOverrides -FrontendRoot $env.FrontendRoot -OverridesRoot $OverridesRoot
Patch-ViteDevExtensionsProxy -FrontendRoot $env.FrontendRoot
Patch-ViteDevScriptsProxy -FrontendRoot $env.FrontendRoot
Patch-ViteDevUsersBypass -FrontendRoot $env.FrontendRoot
Patch-ViteSementicExtensionsPlugin -FrontendRoot $env.FrontendRoot
Install-SementicFrontendDeps -FrontendRoot $env.FrontendRoot -InvokePnpm $env.InvokePnpm

$syncJob = Start-SementicOverrideSync -FrontendRoot $env.FrontendRoot -OverridesRoot $OverridesRoot

$env:DEV_SERVER_COMFYUI_URL = $ComfyUrl
Write-Host ""
Write-Host "Vite dev server -> http://localhost:5173"
Write-Host "ComfyUI API/WS proxy -> $ComfyUrl (backend must be running before opening :5173)."
Write-Host "Edit frontend/overrides or ComfyUI_frontend/src — save to hot-reload."
Write-Host "Start ComfyUI backend without --front-end-root (default pip UI is unused)."
Write-Host "Custom extensions (sjsx.js, sjsxDebug) load via /api/extensions proxy to $ComfyUrl."
Write-Host ""

Push-Location $env.FrontendRoot
try {
    & $env.InvokePnpm dev
} finally {
    Pop-Location
    if ($syncJob) {
        Stop-Job $syncJob -ErrorAction SilentlyContinue
        Remove-Job $syncJob -Force -ErrorAction SilentlyContinue
    }
}
