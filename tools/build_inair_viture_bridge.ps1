param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "bin\\inair_dll.dll")
)

$ErrorActionPreference = "Stop"

function Resolve-CMakeGenerator {
    $generator = "Visual Studio 17 2022"
    $probeDir = Join-Path $env:TEMP "luma-ultra-cmake-probe"
    $probeSourceDir = Join-Path $PSScriptRoot "inair-viture-bridge"
    cmake -G $generator -A x64 -S $probeSourceDir -B $probeDir *> $null
    $success = $LASTEXITCODE -eq 0
    Remove-Item $probeDir -Recurse -Force -ErrorAction SilentlyContinue
    if ($success) {
        return $generator
    }

    throw "The Visual Studio 2022 CMake generator was not available."
}

$sourceDir = Join-Path $PSScriptRoot "inair-viture-bridge"
$outputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDir = Split-Path -Parent $outputPath
$intermediateDir = Join-Path $sourceDir "build"
$cmakeGenerator = Resolve-CMakeGenerator

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$expPath = Join-Path $intermediateDir "inair_dll.exp"
cmake -S $sourceDir -B $intermediateDir -G $cmakeGenerator -A x64
if ($LASTEXITCODE -ne 0) {
    throw "CMake configure failed with exit code $LASTEXITCODE"
}

cmake --build $intermediateDir --config Release
if ($LASTEXITCODE -ne 0) {
    throw "CMake build failed with exit code $LASTEXITCODE"
}

$builtDll = Join-Path $intermediateDir "out\inair_dll.dll"
if (-not (Test-Path $builtDll)) {
    throw "Expected bridge DLL was not produced: $builtDll"
}

Copy-Item $builtDll $outputPath -Force

if (Test-Path $expPath) {
    Remove-Item $expPath -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Built VITURE INAIR bridge in $outputPath" -ForegroundColor Green
