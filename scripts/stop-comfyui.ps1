# Stop ComfyUI / main.py processes for this workspace (pre/post debug cleanup).
$ErrorActionPreference = 'SilentlyContinue'

$workspace = Split-Path -Parent $PSScriptRoot
$workspaceNorm = ($workspace -replace '\\', '/').ToLowerInvariant()

Get-NetTCPConnection -LocalPort 8188 -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object {
        $cmd = $_.CommandLine
        $cmd -and $cmd -match 'main\.py' -and ($cmd.ToLowerInvariant() -like "*$($workspaceNorm)*")
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

exit 0
