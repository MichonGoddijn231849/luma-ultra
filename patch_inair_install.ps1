$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$inairRoot = "C:\Program Files\INAIR Space"
$patchDir = Join-Path $repoRoot "vendor\inair\patches"
$pluginRelativeDir = "INAIRSpace\INAIR SpaceDesktop_Data\Plugins\x86_64"
$patchItems = @(
    @{ Asset = "inair.api.core.dll"; Install = "inair.api.core.dll"; Backup = $true },
    @{ Asset = "inair.api.dfu.dll"; Install = "inair.api.dfu.dll"; Backup = $true },
    @{ Asset = "inair.api.pipeserver.dll"; Install = "inair.api.pipeserver.dll"; Backup = $true },
    @{ Asset = "LumaUltra.InairPatchSupport.dll"; Install = "LumaUltra.InairPatchSupport.dll"; Backup = $false },
    @{ Asset = "unity-plugin\inair_dll.dll"; Install = "$pluginRelativeDir\inair_dll.dll"; Backup = $true },
    @{ Asset = "unity-plugin\glasses.dll"; Install = "$pluginRelativeDir\glasses.dll"; Backup = $false },
    @{ Asset = "unity-plugin\carina_vio.dll"; Install = "$pluginRelativeDir\carina_vio.dll"; Backup = $false },
    @{ Asset = "unity-plugin\glew32.dll"; Install = "$pluginRelativeDir\glew32.dll"; Backup = $false },
    @{ Asset = "unity-plugin\libusb-1.0.dll"; Install = "$pluginRelativeDir\libusb-1.0.dll"; Backup = $false },
    @{ Asset = "unity-plugin\opencv_world4100.dll"; Install = "$pluginRelativeDir\opencv_world4100.dll"; Backup = $false }
)
$backupRoot = Join-Path $repoRoot "artifacts\inair-installed-backup"
$backupDir = Join-Path $backupRoot (Get-Date -Format "yyyyMMdd-HHmmss")

$running = Get-Process -Name "INAIR Space" -ErrorAction SilentlyContinue
if ($running) {
    $running | Stop-Process -Force
}

& (Join-Path $repoRoot "build_inair_patch_assets.ps1")

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

foreach ($item in $patchItems) {
    $assetPath = Join-Path $patchDir $item.Asset
    if (-not (Test-Path $assetPath)) {
        throw "Patch asset not found: $assetPath"
    }

    $installPath = Join-Path $inairRoot $item.Install
    $installParent = Split-Path -Parent $installPath
    if (-not (Test-Path $installParent)) {
        throw "INAIR install path not found: $installParent"
    }

    if ($item.Backup) {
        $backupPath = Join-Path $backupDir $item.Install
        $backupParent = Split-Path -Parent $backupPath
        New-Item -ItemType Directory -Path $backupParent -Force | Out-Null
        Copy-Item $installPath $backupPath -Force
    }

    Copy-Item $assetPath $installPath -Force
}

Write-Host ""
Write-Host "Patched INAIR install for VITURE compatibility." -ForegroundColor Green
Write-Host "Backup saved to $backupDir"
