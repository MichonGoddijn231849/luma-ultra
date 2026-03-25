$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$coreProject = Join-Path $repoRoot "artifacts\inair-decomp\core\inair.api.core.csproj"
$dfuProject = Join-Path $repoRoot "artifacts\inair-decomp\dfu\inair.api.dfu.csproj"
$helperProject = Join-Path $repoRoot "tools\inair-patch-support\LumaUltra.InairPatchSupport.csproj"
$coreBuild = Join-Path $repoRoot "artifacts\inair-decomp\core\bin\Release\net48\inair.api.core.dll"
$dfuBuild = Join-Path $repoRoot "artifacts\inair-decomp\dfu\bin\Release\net48\inair.api.dfu.dll"
$helperBuild = Join-Path $repoRoot "tools\inair-patch-support\bin\Release\net48\LumaUltra.InairPatchSupport.dll"
$patchDir = Join-Path $repoRoot "vendor\inair\patches"
$tempDir = Join-Path $repoRoot "artifacts\inair-patches"
$sourcePipeServerCopy = Join-Path $tempDir "inair.api.pipeserver.source.dll"
$patchedPipeServer = Join-Path $tempDir "inair.api.pipeserver.dll"
$installedPipeServer = "C:\Program Files\INAIR Space\inair.api.pipeserver.dll"
$pipeServerPatchScript = Join-Path $repoRoot "tools\patch-inair-pipeserver.ps1"

if (-not (Test-Path $installedPipeServer)) {
    throw "INAIR pipeserver DLL was not found at $installedPipeServer"
}

dotnet build $coreProject -c Release --source https://api.nuget.org/v3/index.json
dotnet build $dfuProject -c Release --source https://api.nuget.org/v3/index.json
dotnet build $helperProject -c Release --source https://api.nuget.org/v3/index.json

if (Test-Path $tempDir) {
    cmd /c rmdir /s /q "$tempDir"
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

Copy-Item $installedPipeServer $sourcePipeServerCopy -Force
& $pipeServerPatchScript -InputAssembly $sourcePipeServerCopy -HelperAssembly $helperBuild -OutputAssembly $patchedPipeServer

if (Test-Path $patchDir) {
    Remove-Item (Join-Path $patchDir "*") -Force -ErrorAction SilentlyContinue
} else {
    New-Item -ItemType Directory -Path $patchDir -Force | Out-Null
}

Copy-Item $coreBuild (Join-Path $patchDir "inair.api.core.dll") -Force
Copy-Item $dfuBuild (Join-Path $patchDir "inair.api.dfu.dll") -Force
Copy-Item $patchedPipeServer (Join-Path $patchDir "inair.api.pipeserver.dll") -Force
Copy-Item $helperBuild (Join-Path $patchDir "LumaUltra.InairPatchSupport.dll") -Force

Write-Host ""
Write-Host "Built INAIR patch assets in $patchDir" -ForegroundColor Green
