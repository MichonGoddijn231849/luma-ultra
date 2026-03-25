param(
    [string]$Version,
    [string]$Publisher = "Michon",
    [string]$AppUrl = "https://github.com/your-account/luma-ultra",
    [switch]$SkipExeBuild
)

$ErrorActionPreference = "Stop"

function Resolve-InnoCompiler {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path $_) }

    if ($candidates.Count -gt 0) {
        return @($candidates)[0]
    }

    throw "ISCC.exe was not found. Install Inno Setup 6 first."
}

$repoRoot = $PSScriptRoot
$versionFile = Join-Path $repoRoot "VERSION"
if (-not $Version) {
    $Version = (Get-Content $versionFile -Raw).Trim()
}

if (-not $SkipExeBuild) {
    & (Join-Path $repoRoot "build_exe.ps1")
}

$sourceDir = Join-Path $repoRoot "release\LumaUltraHandViewer"
if (-not (Test-Path $sourceDir)) {
    throw "Packaged application not found at $sourceDir"
}

$outputDir = Join-Path $repoRoot "installer-output"
if (Test-Path $outputDir) {
    cmd /c rmdir /s /q "$outputDir"
}
New-Item -ItemType Directory -Path $outputDir | Out-Null

$iscc = Resolve-InnoCompiler
$scriptPath = Join-Path $repoRoot "installer\LumaUltraHandViewer.iss"

$arguments = @(
    "/DAppVersion=$Version",
    "/DAppPublisher=$Publisher",
    "/DAppUrl=$AppUrl",
    "/DSourceDir=$sourceDir",
    "/DOutputDir=$outputDir",
    $scriptPath
)

& "$iscc" @arguments

if ($LASTEXITCODE -ne 0) {
    throw "ISCC.exe failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Installer created in $outputDir" -ForegroundColor Green
