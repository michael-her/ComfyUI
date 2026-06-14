# Incremental rebuild on save; refresh http://localhost:8188 to pick up changes.
param(
    [string]$FrontendRoot = "$PSScriptRoot\..\frontend\ComfyUI_frontend",
    [string]$OverridesRoot = "$PSScriptRoot\..\frontend\overrides",
    [string]$OutputRoot = "$PSScriptRoot\..\web\comfyui-frontend"
)

. "$PSScriptRoot\lib\frontend-env.ps1"

$env = Initialize-SementicFrontendEnv -FrontendRoot $FrontendRoot
Apply-SementicFrontendOverrides -FrontendRoot $env.FrontendRoot -OverridesRoot $OverridesRoot
Install-SementicFrontendDeps -FrontendRoot $env.FrontendRoot -InvokePnpm $env.InvokePnpm

$dist = Join-Path $env.FrontendRoot "dist"
Set-SementicFrontendOutputLink -OutputRoot $OutputRoot -DistDir $dist | Out-Null

$syncJob = Start-SementicOverrideSync -FrontendRoot $env.FrontendRoot -OverridesRoot $OverridesRoot

Write-Host ""
Write-Host "Watch build -> $OutputRoot (junction to dist)"
Write-Host "ComfyUI: --front-end-root $OutputRoot then refresh browser after each rebuild."
Write-Host ""

Push-Location $env.FrontendRoot
try {
    & $env.InvokePnpm exec cross-env NODE_OPTIONS="--max-old-space-size=8192" vite build --watch --config vite.config.mts
} finally {
    Pop-Location
    if ($syncJob) {
        Stop-Job $syncJob -ErrorAction SilentlyContinue
        Remove-Job $syncJob -Force -ErrorAction SilentlyContinue
    }
}
