$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    py -3.13 -m venv .venv
}

$depsReady = & $python -c "import PySide6, mediapipe, cv2, numpy" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -r requirements.txt
}

$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
& $python -m luma_ultra_hand_viewer.app
