# Luma Ultra Hand Viewer

A Windows desktop viewer that:

- uses the VITURE XR Glasses SDK on Windows when a compatible device is connected,
- reads the Luma Ultra camera feed through the native callbacks,
- runs MediaPipe hand landmark tracking on top of that feed,
- overlays the hand skeleton, pinch distance, and pose stats in real time.

If no VITURE device is detected, the app falls back to your default webcam so you can still validate the UI and hand-tracking pipeline.

## Run

```powershell
.\run_viewer.ps1
```

## Build EXE

```powershell
.\build_exe.ps1
```

The packaged app is created at `artifacts\release\LumaUltraHandViewer\LumaUltraHandViewer.exe`.

Important: run the EXE from `artifacts\release\...`, not from any temporary build folder.

## Build Installer

```powershell
.\build_installer.ps1
```

The installer is created at `artifacts\installer\LumaUltraHandViewer-Setup-<version>.exe`.

It installs the app into `Program Files`, adds a Start menu shortcut, optionally adds a desktop shortcut, and creates a normal Windows uninstall entry.

## INAIR Tab

The app now includes an `INAIR` tab that can:

- launch the installed `INAIR Space` app,
- patch the installed INAIR DLLs for VITURE compatibility and then launch it,
- restore the latest backed-up original DLLs.

Patch and restore actions require Windows elevation because `INAIR Space` is installed under `Program Files`.

## GitHub Release Downloads

This repository includes a GitHub Actions workflow at `.github\workflows\release-installer.yml`.

Once the folder is pushed to GitHub:

1. Create a repository.
2. Push this project.
3. Push a tag like `v0.1.0`.

That workflow will:

- build the EXE,
- compile the Windows installer,
- upload the installer as a workflow artifact,
- attach the installer to the matching GitHub Release.

You can also run the workflow manually with `workflow_dispatch`.

If you want a one-command publish path after signing into GitHub CLI, use:

```powershell
gh auth login
.\publish_github.ps1 -Repository your-account/luma-ultra
```

That script initializes git if needed, creates the GitHub repository, pushes `main`, and pushes the `v<version>` tag so the installer workflow can publish a release asset.

## Notes

- The VITURE Windows SDK does not expose a public hand-tracking API in the native headers or DLL exports, so this app derives hand tracking from the camera feed rather than calling a built-in gesture API.
- The app currently assumes the Carina camera callback delivers an 8-bit grayscale frame for each eye and uses the `left0` image as the tracking input.
- Hardware-specific tuning may still be needed once you test with the glasses connected, especially around exposure, confidence thresholds, and whether the stereo frames need a different decode path.
- Only the Windows runtime DLLs used by this app are kept under `vendor\viture\windows`; the unused Unity SDK and Windows SDK documentation were removed during cleanup.
