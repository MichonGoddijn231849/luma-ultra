$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$inairRoot = "C:\Program Files\INAIR Space"
$patchDir = Join-Path $repoRoot "vendor\inair\patches"
$patchFiles = @(
    "inair.api.core.dll",
    "inair.api.dfu.dll",
    "inair.api.pipeserver.dll",
    "LumaUltra.InairPatchSupport.dll"
)
$backupFiles = @(
    "inair.api.core.dll",
    "inair.api.dfu.dll",
    "inair.api.pipeserver.dll"
)
$backupRoot = Join-Path $repoRoot "artifacts\inair-installed-backup"
$backupDir = Join-Path $backupRoot (Get-Date -Format "yyyyMMdd-HHmmss")

$running = Get-Process -Name "INAIR Space" -ErrorAction SilentlyContinue
if ($running) {
    $running | Stop-Process -Force
}

& (Join-Path $repoRoot "build_inair_patch_assets.ps1")

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
foreach ($file in $backupFiles) {
    Copy-Item (Join-Path $inairRoot $file) (Join-Path $backupDir $file)
}

foreach ($file in $patchFiles) {
    Copy-Item (Join-Path $patchDir $file) (Join-Path $inairRoot $file) -Force
}

Write-Host ""
Write-Host "Patched INAIR install for VITURE compatibility." -ForegroundColor Green
Write-Host "Backup saved to $backupDir"
