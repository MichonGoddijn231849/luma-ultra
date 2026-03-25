param(
    [string]$BackupDir
)

$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$inairRoot = "C:\Program Files\INAIR Space"
$backupRoot = Join-Path $repoRoot "artifacts\inair-installed-backup"
$backupFiles = @(
    "inair.api.core.dll",
    "inair.api.dfu.dll",
    "inair.api.pipeserver.dll"
)

if (-not $BackupDir) {
    $latest = Get-ChildItem -Path $backupRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) {
        throw "No INAIR backups were found in $backupRoot"
    }
    $BackupDir = $latest.FullName
}

$running = Get-Process -Name "INAIR Space" -ErrorAction SilentlyContinue
if ($running) {
    $running | Stop-Process -Force
}

foreach ($file in $backupFiles) {
    $source = Join-Path $BackupDir $file
    if (-not (Test-Path $source)) {
        throw "Backup folder does not contain $file: $BackupDir"
    }
    Copy-Item $source (Join-Path $inairRoot $file) -Force
}

$helperPath = Join-Path $inairRoot "LumaUltra.InairPatchSupport.dll"
if (Test-Path $helperPath) {
    Remove-Item $helperPath -Force
}

Write-Host ""
Write-Host "Restored INAIR install from $BackupDir" -ForegroundColor Yellow
