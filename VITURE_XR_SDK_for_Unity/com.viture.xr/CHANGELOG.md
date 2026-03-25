# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-03-11

### Added

- **RGB Camera API** - Access the built-in RGB camera on supported VITURE glasses via `VitureXR.Camera.RGB`. Start the camera at a specific resolution or use the per-model default, and receive frame callbacks. Add `VitureRGBCameraManager` to a GameObject for automatic RenderTexture display and async frame capture. Includes a demo sample and a Building Block for one-click setup.
- **Hand Aim Sensitivity** - Controls how the hand aim ray responds to wrist movement in 6DoF mode. Low (default) uses arm direction only for stability; High blends arm and wrist for more responsive aiming. Configurable in project settings or at runtime via code.
- **Default XR Dependencies** - XR Hands and XR Interaction Toolkit are now included as package dependencies, removing the need to install them separately.

### Changed

- **VitureGlassesModel enum updated** - `Luma` and `LumaPro` are now distinguished as separate values (previously grouped together). Added `LumaCyber` (6). `LumaUltra` changed from 4 to 5, `Beast` changed from 5 to 7.

### Fixed

- **Quick Actions Interaction** - Fixed a bug where the Quick Actions prefab could not be interacted with when the XR Origin's world position was not at the origin.

## [0.6.0] - 2026-02-12

### Added

- **Third-Person View Share** - Third-person mixed reality streaming using a mobile device as a spectator camera. Connect over Wi-Fi, align coordinate systems with hands, and stream AR content in real-time. Perfect for demos, content creation, or just seeing how cool you look in MR. Reimport Viture Quick Actions prefab into your scene to get started!
- **Interaction Simulator** - Test HMD and hand interaction directly in the Unity Editor with FPS-style mouse and keyboard controls. No more build-deploy-test cycles for basic interaction testing.

### Fixed

- **Recording Stutter** - Further reduced the stutter when stopping a long recording.

## [0.5.0] - 2026-01-28

### Added

- **Marker Tracking** - Track ArUco markers in the real world and place virtual objects on top of them. The virtual and real spaces are now bridged! 
- **New Hand Model** - Updated the default hand model with sleeker visuals.
- **Adjustable Hand Filter Mode** - You can now choose between responsive (fast, lower latency) and stable (smooth, filtered) hand tracking modes.
- **Building Blocks** - One-click setup for common VITURE features. Automatically handles package dependencies, sample imports, and scene configuration. Includes XR Origin, Hands, Quick Actions, Canvas Interaction, and Marker Tracking.

### Fixed

- **Longer Recordings** - No more 5-minute recording limit. Plus, fixed the freeze issue when completing long sessions.

### Removed

- **Hand State Demo** - Not particularly useful.
- **Error Codes and Hand Tracking Callbacks** - Simplified. The system now handles failures internally, so you don't need to.

## [0.4.1] - 2025-12-17

### Fixed

- Fixed compile error when Unity XR Hands package is not installed in the project.

## [0.4.0] - 2025-12-16

### Compatibility Notice

This is a beta release. Apps built with SDK 0.4.0 require VITURE Neckband OS 0.1.0 or later. OS 0.1.0 cannot run apps built with SDK older than 0.4.0.

### Added

- **Supported Glasses Setting** - Configure which VITURE glasses your app supports (6DoF only or both 3DoF and 6DoF) in project settings. The system prevents incompatible apps from launching.
- **SDK & OS Version Validation** - System-level version compatibility checks prevent apps with incompatible SDK versions from launching.

### Changed

- **Hand Tracking API** - `VitureXR.HandTracking.Start()` now uses callbacks with error codes and messages instead of boolean return value for better async handling.
- **Recording Callbacks** - Now also include error codes and messages for improved error diagnostics.

## [0.3.0] - 2025-11-28

### Added

- **Capture API** - Record first-person mixed reality experiences with both virtual and real-world layers. Capture and share the experiences you create with others!
- **Setup Wizard** - Streamlined project configuration tool.
- **Project Validation System** - Checks required and recommended settings and provides one-click fix.
- **Glasses Electrochromic Control** - Programmatically adjust glasses lens darkness level.
- **Quick Actions UI Panel** - System-level UI that activates when looking up, providing intuitive hand-tracked controls for recording and navigation.

### Removed

- **Deprecated UI Components** - Removed Viture Hand Menu and Recenter Indicator prefabs in favor of the new Quick Actions prefab.

### Compatibility Notice

This is a beta release. SDK 0.3.0 requires VITURE Neckband OS 2.0.5.21127 or later.

- Apps built with SDK 0.3.0 cannot run on older OS versions
- Apps built with older SDKs cannot run on OS 2.0.5.21127 or later

We're working to establish stable cross-version compatibility in upcoming releases.

## [0.2.1] - 2025-10-09

### Removed

- Remove XR Hands HandVisualizer sample dependency for Starter Asset and Hand State Demo samples.

## [0.2.0] - 2025-09-30

### Added

- New 3D hand models for hand tracking visualization.
- `VitureHandVisualizer` component providing basic hand tracking visualization functionality.
- `VitureHandRayController` component to automatically control XRI `NearFarInteractor` hand ray visibility.
- Boolean return value for `VitureXR.HandTracking.Start()` method to indicate whether hand tracking started successfully.

### Changed

- Hand tracking joint count changed to 21.

### Fixed

- Fixed hand tracking joint local rotations, which caused incorrect hand ray direction and hand menu issues.

## [0.1.0] - 2025-09-19

### Added

- 3DoF and 6DoF head tracking.
- Hand tracking with Unity XR Hand Subsystem integration.
- VitureXR API.
- Starter Assets sample with pre-configured assets.
- Hand State Demo sample.
