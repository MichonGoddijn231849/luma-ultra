param(
    [string]$BackupDir
)

$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$inairRoot = "C:\Program Files\INAIR Space"
$backupRoot = Join-Path $repoRoot "artifacts\inair-installed-backup"
$pluginRelativeDir = "INAIRSpace\INAIR SpaceDesktop_Data\Plugins\x86_64"
$patchItems = @(
    @{ Install = "inair.api.core.dll"; Backup = $true },
    @{ Install = "inair.api.dfu.dll"; Backup = $true },
    @{ Install = "inair.api.pipeserver.dll"; Backup = $true },
    @{ Install = "LumaUltra.InairPatchSupport.dll"; Backup = $false },
    @{ Install = "$pluginRelativeDir\inair_dll.dll"; Backup = $true },
    @{ Install = "$pluginRelativeDir\glasses.dll"; Backup = $false },
    @{ Install = "$pluginRelativeDir\carina_vio.dll"; Backup = $false },
    @{ Install = "$pluginRelativeDir\glew32.dll"; Backup = $false },
    @{ Install = "$pluginRelativeDir\libusb-1.0.dll"; Backup = $false },
    @{ Install = "$pluginRelativeDir\opencv_world4100.dll"; Backup = $false }
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

foreach ($item in $patchItems) {
    $installPath = Join-Path $inairRoot $item.Install
    if ($item.Backup) {
        $source = Join-Path $BackupDir $item.Install
        if (-not (Test-Path $source)) {
            throw "Backup folder does not contain $($item.Install): $BackupDir"
        }
        Copy-Item $source $installPath -Force
    } elseif (Test-Path $installPath) {
        Remove-Item $installPath -Force
    }
}

Write-Host ""
Write-Host "Restored INAIR install from $BackupDir" -ForegroundColor Yellow
