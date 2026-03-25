param(
    [string]$BackupDir
)

$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$inairRoot = "C:\Program Files\INAIR Space"
$backupRoot = Join-Path $repoRoot "artifacts\inair-installed-backup"

if (-not $BackupDir) {
    $latest = Get-ChildItem -Path $backupRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) {
        throw "No INAIR backups were found in $backupRoot"
    }
    $BackupDir = $latest.FullName
}

$coreBackup = Join-Path $BackupDir "inair.api.core.dll"
$dfuBackup = Join-Path $BackupDir "inair.api.dfu.dll"

if (-not (Test-Path $coreBackup) -or -not (Test-Path $dfuBackup)) {
    throw "Backup folder does not contain both original DLLs: $BackupDir"
}

Get-Process | Where-Object { $_.ProcessName -eq "INAIR Space" } | Stop-Process -Force

Copy-Item $coreBackup (Join-Path $inairRoot "inair.api.core.dll") -Force
Copy-Item $dfuBackup (Join-Path $inairRoot "inair.api.dfu.dll") -Force

Write-Host ""
Write-Host "Restored INAIR install from $BackupDir" -ForegroundColor Yellow
