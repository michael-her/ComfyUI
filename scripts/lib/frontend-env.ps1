# Shared ComfyUI frontend toolchain (Node 22 + pnpm 11 + SJAX overrides).

function Initialize-SementicFrontendEnv {
    param(
        [string]$FrontendRoot = "$PSScriptRoot\..\..\frontend\ComfyUI_frontend",
        [string]$Tag = "v1.45.15"
    )

    $ErrorActionPreference = "Stop"

    $NodeExe = if ($env:SEMENTIC_NODE) { $env:SEMENTIC_NODE } else {
        $cursorNode = Join-Path $env:LOCALAPPDATA "Programs\cursor\resources\app\resources\helpers\node.exe"
        if (-not (Test-Path $cursorNode)) {
            $cursorNode = "g:\ide\cursor\resources\app\resources\helpers\node.exe"
        }
        if (Test-Path $cursorNode) { $cursorNode } else { (Get-Command node -ErrorAction Stop).Source }
    }

    $ToolsRoot = Join-Path (Split-Path $FrontendRoot -Parent) ".tools"
    $PnpmCjs = Join-Path $ToolsRoot "node_modules\pnpm\bin\pnpm.cjs"
    if (-not (Test-Path $PnpmCjs)) {
        Write-Host "Bootstrapping pnpm 11 with $NodeExe ..."
        New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null
        Push-Location $ToolsRoot
        try {
            & $NodeExe -e "const {execSync}=require('child_process'); execSync('npm install pnpm@11.1.1', {stdio:'inherit'})"
        } finally {
            Pop-Location
        }
    }

    $ShimDir = Join-Path $ToolsRoot "shim"
    New-Item -ItemType Directory -Force -Path $ShimDir | Out-Null
    $PnpmShim = Join-Path $ShimDir "pnpm.cmd"
    @"
@echo off
"$NodeExe" "$PnpmCjs" %*
"@ | Set-Content -Path $PnpmShim -Encoding ASCII
    $env:Path = "$ShimDir;$(Split-Path $NodeExe -Parent);$env:Path"

    if (-not (Test-Path $FrontendRoot)) {
        Write-Host "Cloning ComfyUI_frontend $Tag ..."
        git clone --depth 1 --branch $Tag https://github.com/Comfy-Org/ComfyUI_frontend.git $FrontendRoot
    }

    return [PSCustomObject]@{
        NodeExe       = $NodeExe
        PnpmCjs       = $PnpmCjs
        FrontendRoot  = (Resolve-Path $FrontendRoot).Path
        InvokePnpm    = {
            param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
            & $NodeExe $PnpmCjs @Args
        }.GetNewClosure()
    }
}

function Apply-SementicFrontendOverrides {
    param(
        [string]$FrontendRoot,
        [string]$OverridesRoot = "$PSScriptRoot\..\..\frontend\overrides"
    )

    Write-Host "Applying overrides from $OverridesRoot ..."
    Get-ChildItem -Path $OverridesRoot -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($OverridesRoot.Length + 1)
        $target = Join-Path $FrontendRoot $relative
        $targetDir = Split-Path $target -Parent
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        }
        Copy-Item $_.FullName $target -Force
    }

    function Add-SjsxLocaleKey {
        param([string]$Path, [string]$AfterPattern, [string]$InsertLine)
        if (-not (Test-Path $Path)) { return }
        $content = Get-Content -Path $Path -Raw -Encoding UTF8
        if ($content -match '"sjsx"\s*:') { return }
        $content = [regex]::Replace($content, $AfterPattern, { param($m) "$($m.Value)`n$InsertLine" }, 1)
        Set-Content -Path $Path -Value $content -Encoding UTF8 -NoNewline
    }

    function Set-SjsxLocaleReplacement {
        param([string]$Path, [string]$Old, [string]$New)
        if (-not (Test-Path $Path)) { return }
        $content = Get-Content -Path $Path -Raw -Encoding UTF8
        if ($content -notmatch [regex]::Escape($Old)) { return }
        $content = $content.Replace($Old, $New)
        Set-Content -Path $Path -Value $content -Encoding UTF8 -NoNewline
    }

    function Apply-SementicSjsxParamLocale {
        param([string]$FrontendRoot)
        $patchPath = Join-Path $OverridesRoot "locales\sjsx-param-locale.json"
        if (-not (Test-Path $patchPath)) { return }
        $patch = Get-Content -Path $patchPath -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($locale in @('ko', 'en')) {
            $mainPath = Join-Path $FrontendRoot "src\locales\$locale\main.json"
            if (-not (Test-Path $mainPath)) { continue }
            $content = Get-Content -Path $mainPath -Raw -Encoding UTF8
            $replacements = $patch.$locale
            if (-not $replacements) { continue }
            foreach ($entry in $replacements) {
                if ($content.Contains($entry.from)) {
                    $content = $content.Replace($entry.from, $entry.to)
                }
            }
            Set-Content -Path $mainPath -Value $content -Encoding UTF8 -NoNewline
        }
    }

    Add-SjsxLocaleKey -Path (Join-Path $FrontendRoot "src\locales\en\main.json") `
        -AfterPattern '"allNodes": "All",' -InsertLine '      "sjsx": "SJAX",'
    Add-SjsxLocaleKey -Path (Join-Path $FrontendRoot "src\locales\ko\main.json") `
        -AfterPattern '"allNodes": "모든 노드",' -InsertLine '      "sjsx": "SJAX",'

    Apply-SementicSjsxParamLocale -FrontendRoot $FrontendRoot

    $staleRelativePaths = @(
        "src\utils\sjsxPropertyUtil.ts",
        "src\composables\sjsx\useSjsxPropertyCatalog.ts",
        "src\composables\sjsx\useSjsxNodeProperties.ts",
        "src\renderer\extensions\vueNodes\components\SjsxPropertySearch.vue"
    )
    foreach ($relative in $staleRelativePaths) {
        $stale = Join-Path $FrontendRoot $relative
        if (Test-Path $stale) {
            Remove-Item $stale -Force
        }
    }

    $mainTs = Join-Path $FrontendRoot "src\main.ts"
    if (Test-Path $mainTs) {
        $mainContent = Get-Content -Path $mainTs -Raw -Encoding UTF8
        if ($mainContent -notmatch 'devComfyApiBridge') {
            $mainContent = $mainContent -replace "(import \{ i18n \} from '\./i18n')", "`$1`nimport '@/platform/sementic/devComfyApiBridge'"
            Set-Content -Path $mainTs -Value $mainContent -Encoding UTF8 -NoNewline
        }
    }
}

function Install-SementicFrontendDeps {
    param(
        [string]$FrontendRoot,
        [scriptblock]$InvokePnpm
    )

    Push-Location $FrontendRoot
    try {
        "engine-strict=false" | Out-File -FilePath ".npmrc" -Encoding ascii -Force
        if (-not (Test-Path "node_modules")) {
            Write-Host "Installing frontend dependencies ..."
            & $InvokePnpm install --config.engine-strict=false
        }
    } finally {
        Pop-Location
    }
}

function Test-SementicFrontendOutputLink {
    param(
        [string]$OutputRoot,
        [string]$DistDir
    )

    if (-not (Test-Path -LiteralPath $OutputRoot)) { return $false }

    $item = Get-Item -LiteralPath $OutputRoot -Force
    if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return $false }

    $target = $item.Target
    if ($target -is [array]) { $target = $target[0] }

    return (
        [System.IO.Path]::GetFullPath($target) -eq
        [System.IO.Path]::GetFullPath($DistDir)
    )
}

function Publish-SementicFrontendDist {
    param(
        [string]$OutputRoot,
        [string]$DistDir
    )

    $OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
    $DistDir = [System.IO.Path]::GetFullPath($DistDir)

    if (Test-SementicFrontendOutputLink -OutputRoot $OutputRoot -DistDir $DistDir) {
        Write-Host "Output junction already points to dist — skipping copy."
        return
    }

    if (Test-Path -LiteralPath $OutputRoot) {
        $item = Get-Item -LiteralPath $OutputRoot -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Remove-Item -LiteralPath $OutputRoot -Force
        } else {
            Remove-Item -LiteralPath $OutputRoot -Recurse -Force
        }
    }

    $parent = Split-Path $OutputRoot -Parent
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    Copy-Item -Path (Join-Path $DistDir "*") -Destination $OutputRoot -Recurse -Force
}

function Set-SementicFrontendOutputLink {
    param(
        [string]$OutputRoot,
        [string]$DistDir
    )

    $OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
    $DistDir = [System.IO.Path]::GetFullPath($DistDir)

    if (-not (Test-Path $DistDir)) {
        New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
    }

    if (Test-Path $OutputRoot) {
        $item = Get-Item -LiteralPath $OutputRoot -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Remove-Item -LiteralPath $OutputRoot -Force
        } else {
            Remove-Item -LiteralPath $OutputRoot -Recurse -Force
        }
    }

    $parent = Split-Path $OutputRoot -Parent
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    cmd /c mklink /J "$OutputRoot" "$DistDir" | Out-Null
    Write-Host "Linked $OutputRoot -> $DistDir"
}

function Wait-SementicComfyUiBackend {
    param(
        [string]$ComfyUrl = "http://127.0.0.1:8188",
        [int]$TimeoutSec = 180
    )

    $probe = "$ComfyUrl/system_stats"
    Write-Host "Waiting for ComfyUI backend ($probe) ..."
    $deadline = (Get-Date).AddSeconds($TimeoutSec)

    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $probe -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                Write-Host "ComfyUI backend is ready."
                return
            }
        } catch {
            # Backend still booting
        }
        Start-Sleep -Milliseconds 500
    }

    throw "ComfyUI backend did not become ready within ${TimeoutSec}s at $ComfyUrl"
}

function Patch-ViteDevExtensionsProxy {
    param([string]$FrontendRoot)

    $viteConfig = Join-Path $FrontendRoot "vite.config.mts"
    if (-not (Test-Path $viteConfig)) { return }

    $content = Get-Content -Path $viteConfig -Raw -Encoding UTF8
    if ($content -match 'SEMENTIC: /api/extensions proxied') { return }

    $pattern = '(?ms)\r?\n\s*// Return empty array for extensions API as these modules\r?\n\s*// are not on vite''s dev server\.\r?\n\s*if \(req\.url === ''/api/extensions''\) \{\r?\n\s*res\.end\(JSON\.stringify\(\[\]\)\)\r?\n\s*return false\r?\n\s*\}\r?\n'
    $replacement = "`n          // SEMENTIC: /api/extensions proxied to ComfyUI (custom_nodes extensions)`n"

    $newContent = [regex]::Replace($content, $pattern, $replacement, 1)
    if ($newContent -eq $content) {
        Write-Warning "Could not patch vite.config.mts — /api/extensions may still return []."
        return
    }

    Set-Content -Path $viteConfig -Value $newContent -Encoding UTF8 -NoNewline
    Write-Host "Patched vite.config.mts: custom node extensions load in Vite dev."
}

function Patch-ViteDevScriptsProxy {
    param([string]$FrontendRoot)

    $viteConfig = Join-Path $FrontendRoot "vite.config.mts"
    if (-not (Test-Path $viteConfig)) { return }

    $content = Get-Content -Path $viteConfig -Raw -Encoding UTF8
    if ($content -match "SEMENTIC: legacy extension imports") { return }

    $pattern = "(?ms)(\r?\n\s*'/extensions': \{.*?\},\r?\n)(\s*'/docs':)"
    $insert = @"
`$1
      // SEMENTIC: legacy extension imports (../../../scripts/app.js)
      '/scripts': {
        target: DEV_SERVER_COMFYUI_URL,
        changeOrigin: true,
        ...cloudProxyConfig
      },

`$2
"@

    $newContent = [regex]::Replace($content, $pattern, $insert, 1)
    if ($newContent -eq $content) {
        Write-Warning "Could not patch vite.config.mts — /scripts proxy missing."
        return
    }

    Set-Content -Path $viteConfig -Value $newContent -Encoding UTF8 -NoNewline
    Write-Host "Patched vite.config.mts: /scripts proxied for legacy extensions."
}

function Patch-ViteDevUsersBypass {
    param([string]$FrontendRoot)

    $viteConfig = Join-Path $FrontendRoot "vite.config.mts"
    if (-not (Test-Path $viteConfig)) { return }

    $content = Get-Content -Path $viteConfig -Raw -Encoding UTF8
    if ($content -match 'SEMENTIC: localhost /api/users stub') { return }

    $pattern = "(?ms)// Bypass multi-user auth check from staging \(cloud only\)\r?\n\s*if \(DISTRIBUTION === 'cloud' && req\.url === '/api/users'\) \{\r?\n\s*res\.setHeader\('Content-Type', 'application/json'\)\r?\n\s*res\.end\(JSON\.stringify\(\{\}\)\) // Return empty object to simulate single-user mode\r?\n\s*return false\r?\n\s*\}"
    $replacement = @"
// SEMENTIC: localhost /api/users stub (single-user dev)
          if (
            (DISTRIBUTION === 'cloud' || DISTRIBUTION === 'localhost') &&
            req.url === '/api/users'
          ) {
            res.setHeader('Content-Type', 'application/json')
            res.end(JSON.stringify({})) // Return empty object to simulate single-user mode
            return false
          }
"@

    $newContent = [regex]::Replace($content, $pattern, $replacement, 1)
    if ($newContent -eq $content) {
        Write-Warning "Could not patch vite.config.mts — /api/users localhost stub missing."
        return
    }

    Set-Content -Path $viteConfig -Value $newContent -Encoding UTF8 -NoNewline
    Write-Host "Patched vite.config.mts: /api/users stubbed for localhost dev."
}

function Patch-ViteSementicExtensionsPlugin {
    param([string]$FrontendRoot)

    $viteConfig = Join-Path $FrontendRoot "vite.config.mts"
    if (-not (Test-Path $viteConfig)) { return }

    $content = Get-Content -Path $viteConfig -Raw -Encoding UTF8
    if ($content -match 'sementicExtensionsDevPlugin') { return }

    if ($content -notmatch "import path from 'path'") {
        $content = $content.Replace(
            "import { execSync } from 'child_process'",
            "import path from 'path'`r`nimport { execSync } from 'child_process'"
        )
    }

    $content = $content.Replace(
        "import { comfyAPIPlugin } from './build/plugins'",
        "import { comfyAPIPlugin } from './build/plugins'`r`nimport { sementicExtensionsDevPlugin } from './build/sementicExtensionsDevPlugin'"
    )

    $content = $content.Replace(
        "    comfyAPIPlugin(IS_DEV),",
        @"
    comfyAPIPlugin(IS_DEV),
    ...(IS_DEV ? [sementicExtensionsDevPlugin(path.resolve(__dirname, '../..'))] : []),
"@
    )

    if ($content -notmatch 'sementicExtensionsDevPlugin') {
        Write-Warning "Could not patch vite.config.mts — extensions dev plugin missing."
        return
    }

    Set-Content -Path $viteConfig -Value $content -Encoding UTF8 -NoNewline
    Write-Host "Patched vite.config.mts: serve custom_nodes extensions in Vite dev."
}

function Start-SementicOverrideSync {
    param(
        [string]$FrontendRoot,
        [string]$OverridesRoot = "$PSScriptRoot\..\..\frontend\overrides",
        [string]$LibPath = "$PSScriptRoot\frontend-env.ps1"
    )

    return Start-Job -Name "SementicOverrideSync" -ArgumentList $LibPath, $FrontendRoot, $OverridesRoot -ScriptBlock {
        param($LibPath, $FrontendRoot, $OverridesRoot)
        . $LibPath
        $lastWrite = [datetime]::MinValue
        while ($true) {
            Start-Sleep -Milliseconds 400
            $files = Get-ChildItem -Path $OverridesRoot -Recurse -File -ErrorAction SilentlyContinue
            if (-not $files) { continue }
            $latest = ($files | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
            if ($latest -gt $lastWrite) {
                $lastWrite = $latest
                Apply-SementicFrontendOverrides -FrontendRoot $FrontendRoot -OverridesRoot $OverridesRoot
                Write-Output "[overrides] synced"
            }
        }
    }
}
