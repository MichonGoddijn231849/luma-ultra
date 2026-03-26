$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    py -3.13 -m venv .venv
}

& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $repoRoot "requirements.txt") pyinstaller

$env:PYTHONPATH = Join-Path $repoRoot "src"

$running = Get-Process -Name "LumaUltraHandViewer" -ErrorAction SilentlyContinue
if ($running) {
    $running | Stop-Process -Force
    $running | Wait-Process -Timeout 10 -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

function Remove-Tree {
    param([string]$PathToRemove)

    if (-not (Test-Path $PathToRemove)) {
        return
    }

    for ($attempt = 0; $attempt -lt 5; $attempt++) {
        cmd /c rmdir /s /q "$PathToRemove"
        if (-not (Test-Path $PathToRemove)) {
            return
        }

        Start-Sleep -Seconds 1
    }

    throw "Failed to remove path after retries: $PathToRemove"
}

$workPath = Join-Path $repoRoot "artifacts\.pyinstaller-build"
$distPath = Join-Path $repoRoot "artifacts\release"

Remove-Tree $workPath
Remove-Tree $distPath

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --name LumaUltraHandViewer `
  --workpath "$workPath" `
  --distpath "$distPath" `
  --paths src `
  --collect-all mediapipe `
  --collect-all cv2 `
  --hidden-import PySide6.QtSvg `
  --hidden-import PySide6.QtOpenGLWidgets `
  --add-data "assets;assets" `
  --add-data "VERSION;." `
  --add-data "vendor;vendor" `
  src\run_app.py
