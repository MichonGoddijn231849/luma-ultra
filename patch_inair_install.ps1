$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$inairRoot = "C:\Program Files\INAIR Space"
$coreProject = Join-Path $repoRoot "artifacts\inair-decomp\core\inair.api.core.csproj"
$dfuProject = Join-Path $repoRoot "artifacts\inair-decomp\dfu\inair.api.dfu.csproj"
$coreBuild = Join-Path $repoRoot "artifacts\inair-decomp\core\bin\Release\net48\inair.api.core.dll"
$dfuBuild = Join-Path $repoRoot "artifacts\inair-decomp\dfu\bin\Release\net48\inair.api.dfu.dll"
$backupRoot = Join-Path $repoRoot "artifacts\inair-installed-backup"
$backupDir = Join-Path $backupRoot (Get-Date -Format "yyyyMMdd-HHmmss")

Get-Process | Where-Object { $_.ProcessName -eq "INAIR Space" } | Stop-Process -Force

dotnet build $coreProject -c Release --source https://api.nuget.org/v3/index.json
dotnet build $dfuProject -c Release --source https://api.nuget.org/v3/index.json

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item (Join-Path $inairRoot "inair.api.core.dll") (Join-Path $backupDir "inair.api.core.dll")
Copy-Item (Join-Path $inairRoot "inair.api.dfu.dll") (Join-Path $backupDir "inair.api.dfu.dll")

Copy-Item $coreBuild (Join-Path $inairRoot "inair.api.core.dll") -Force
Copy-Item $dfuBuild (Join-Path $inairRoot "inair.api.dfu.dll") -Force

Write-Host ""
Write-Host "Patched INAIR install for VITURE compatibility." -ForegroundColor Green
Write-Host "Backup saved to $backupDir"
