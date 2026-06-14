# Build ComfyUI frontend with Sementic UI SJAX tab overrides.
param(
    [string]$FrontendRoot = "$PSScriptRoot\..\frontend\ComfyUI_frontend",
    [string]$OverridesRoot = "$PSScriptRoot\..\frontend\overrides",
    [string]$OutputRoot = "$PSScriptRoot\..\web\comfyui-frontend",
    [string]$Tag = "v1.45.15",
    [switch]$Fast
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\lib\frontend-env.ps1"

function Write-StepTime {
    param([string]$Label, [Diagnostics.Stopwatch]$Timer)
    $Timer.Stop()
    Write-Host "$Label finished in $([int]$Timer.Elapsed.TotalSeconds)s"
}

$total = [Diagnostics.Stopwatch]::StartNew()

$env = Initialize-SementicFrontendEnv -FrontendRoot $FrontendRoot -Tag $Tag

$step = [Diagnostics.Stopwatch]::StartNew()
Apply-SementicFrontendOverrides -FrontendRoot $env.FrontendRoot -OverridesRoot $OverridesRoot
Write-StepTime "Overrides" $step

$step = [Diagnostics.Stopwatch]::StartNew()
Install-SementicFrontendDeps -FrontendRoot $env.FrontendRoot -InvokePnpm $env.InvokePnpm
Write-StepTime "Dependencies" $step

$dist = Join-Path $env.FrontendRoot "dist"

Push-Location $env.FrontendRoot
try {
    if (-not $Fast) {
        Write-Host "Typecheck (vue-tsc) ..."
        $step = [Diagnostics.Stopwatch]::StartNew()
        & $env.InvokePnpm run typecheck
        if ($LASTEXITCODE -ne 0) {
            throw "Typecheck failed with exit code $LASTEXITCODE"
        }
        Write-StepTime "Typecheck" $step
    } else {
        Write-Host "Skipping typecheck (-Fast). Use full build before release."
    }

    if (Test-Path $dist) {
        Write-Host "Cleaning dist ..."
        Remove-Item -LiteralPath $dist -Recurse -Force
    }

    Write-Host "Vite production build ..."
    $step = [Diagnostics.Stopwatch]::StartNew()
    & $env.InvokePnpm exec cross-env NODE_OPTIONS="--max-old-space-size=8192" vite build --config vite.config.mts
    if ($LASTEXITCODE -ne 0) {
        throw "Vite build failed with exit code $LASTEXITCODE"
    }
    Write-StepTime "Vite build" $step
} finally {
    Pop-Location
}

if (-not (Test-Path $dist)) {
    throw "Build output not found at $dist"
}

Write-Host "Publishing dist -> $OutputRoot ..."
$step = [Diagnostics.Stopwatch]::StartNew()
Publish-SementicFrontendDist -OutputRoot $OutputRoot -DistDir $dist
Write-StepTime "Publish" $step

$total.Stop()
Write-Host "Done in $([int]$total.Elapsed.TotalSeconds)s. Launch ComfyUI with: --front-end-root $OutputRoot"
