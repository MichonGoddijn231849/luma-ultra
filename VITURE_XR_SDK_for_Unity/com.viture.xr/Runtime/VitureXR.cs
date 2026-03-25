using System;
using System.Collections;
using System.Threading;
using System.Net;
using System.Net.Sockets;
using UnityEngine;
using UnityEngine.XR.Management;

namespace Viture.XR
{
    /// <summary>
    /// Central hub providing static access to VITURE XR functionality.
    /// All APIs are organized into logical categories for easy discovery and use.
    /// </summary>
    public static class VitureXR
    {
        internal static SynchronizationContext s_MainThreadContext;
        
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        private static void Initialize()
        {
            s_MainThreadContext = SynchronizationContext.Current;

            Application.quitting += OnApplicationQuitting;
            Application.focusChanged += OnApplicationFocusChanged;

#if UNITY_ANDROID && !UNITY_EDITOR
            VitureNativeApi.Capture.RegisterRecordingCallbacks(
                Capture.RecordingStartSuccessCallback,
                Capture.RecordingStartFailureCallback,
                Capture.RecordingSaveSuccessCallback,
                Capture.RecordingSaveFailureCallback);

            VitureNativeApi.Capture.RegisterViewShareCallbacks(
                Capture.ClientConnectedCallback,
                Capture.ClientDisconnectedCallback,
                Capture.AlignmentCalibrationStartedCallback,
                Capture.AlignmentCalibrationStoppedCallback,
                Capture.AlignmentCheckStartedCallback,
                Capture.AlignmentCheckStoppedCallback,
                Capture.StreamingStartedCallback,
                Capture.StreamingStoppedCallback);

            VitureNativeApi.Camera.RGB.RegisterFrameAvailableCallback(Camera.RGB.FrameAvailableCallback);
#endif
        }

        /// <summary>
        /// Gets the active VITURE XR loader instance.
        /// </summary>
        /// <returns>The active VitureLoader instance, or null if no VITURE loader is active.</returns>
        public static VitureLoader GetLoader()
        {
            return XRGeneralSettings.Instance?.Manager?.activeLoader as VitureLoader;
        }

        private static void OnApplicationQuitting()
        {
            if (Capture.isRecording)
                Capture.StopRecording();

            if (Capture.isSharingView)
                Capture.StopViewShare();

            if (Camera.RGB.isActive)
                Camera.RGB.Stop();
        }

        private static void OnApplicationFocusChanged(bool hasFocus)
        {
            if (!hasFocus)
            {
                if (Capture.isRecording)
                    Capture.StopRecording();

                if (Capture.isSharingView)
                    Capture.StopViewShare();
            
                if (Camera.RGB.isActive)
                    Camera.RGB.Stop();
            }
        }
        
        /// <summary>
        /// Provides information and control for connected VITURE glasses.
        /// </summary>
        public static class Glasses
        {
            /// <summary>
            /// Gets the model of the currently connected VITURE glasses.
            /// </summary>
            /// <returns>Connected model, or Unknown if no glasses are connected.</returns>
            public static VitureGlassesModel GetGlassesModel()
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                return (VitureGlassesModel)VitureNativeApi.Glasses.GetGlassesModel();
#else
                Debug.LogWarning("VitureXR.Glasses.GetGlassesModel() is only available on VITURE Neckband");
                return VitureGlassesModel.Unknown;
#endif
            }

            /// <summary>
            /// Sets the electrochromic darkness level of the glasses lenses.
            /// Current glasses models treat this as on/off: 0.0 = off, any other value = on.
            /// Future models will support multiple darkness levels.
            /// </summary>
            /// <param name="level">Darkness from 0.0 (transparent) to 1.0 (dark). Values outside this range are clamped.</param>
            public static void SetElectrochromicLevel(float level)
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                VitureNativeApi.Glasses.SetElectrochromicLevel(Mathf.Clamp01(level));
#else
                Debug.LogWarning("VitureXR.Glasses.SetElectrochromicLevel(float) is only available on VITURE Neckband");
#endif
            }
        }
        
        /// <summary>
        /// Advanced rendering controls
        /// </summary>
        public static class Rendering
        {
            /// <summary>
            /// Enables or disables half frame rate rendering for performance optimization.
            /// When enabled, reduces rendering frame rate by half (e.g., 90fps to 45fps).
            /// Animation will appear less smooth.
            /// </summary>
            /// <param name="enabled">True to enable half frame rate, false to disable.</param>
            public static void SetHalfFrameRate(bool enabled)
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                VitureNativeApi.Rendering.SetHalfFrameRate(enabled);
#else
                Debug.LogWarning("VitureXR.Rendering.SetHalfFrameRate(bool) is only available on VITURE Neckband");
#endif
            }
            
            /// <summary>
            /// Enables or disables time warp only rendering mode.
            /// When enabled, stops Unity rendering and uses only time warp
            /// to display the last rendered frame with head tracking compensation.
            /// This is only for testing purposes.
            /// </summary>
            /// <param name="enabled">True to enable time warp only mode, false to disable.</param>
            public static void SetTimeWarpOnlyMode(bool enabled)
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                VitureNativeApi.Rendering.SetTimeWarpOnlyMode(enabled);
#else
                Debug.LogWarning("VitureXR.Rendering.SetTimeWarpOnlyMode(bool) is only available on VITURE Neckband");
#endif
            }
        }
        
        /// <summary>
        /// Controls head tracking functionality and provides device capability information.
        /// </summary>
        public static class HeadTracking
        {
            /// <summary>
            /// Gets the head tracking capability of the currently connected glasses.
            /// </summary>
            /// <returns>Head tracking capability (3DoF or 6DoF) based on the connected glasses model.</returns>
            public static VitureHeadTrackingCapability GetHeadTrackingCapability()
            {
                switch (Glasses.GetGlassesModel())
                {
                    case VitureGlassesModel.One:
                        return VitureHeadTrackingCapability.ThreeDoF;
                    case VitureGlassesModel.Pro:
                        return VitureHeadTrackingCapability.ThreeDoF;
                    case VitureGlassesModel.Luma:
                    case VitureGlassesModel.LumaPro:
                    case VitureGlassesModel.LumaCyber:
                        return VitureHeadTrackingCapability.ThreeDoF;
                    case VitureGlassesModel.LumaUltra:
                        return VitureHeadTrackingCapability.SixDoF;
                    case VitureGlassesModel.Beast:
                        return VitureHeadTrackingCapability.ThreeDoF;
                    default:
                        return VitureHeadTrackingCapability.ThreeDoF;
                }
            }

            /// <summary>
            /// Resets the SLAM origin to the current head position and orientation.
            /// This recalibrates the tracking reference and may take a few seconds.
            /// </summary>
            public static void ResetOrigin()
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                VitureNativeApi.HeadTracking.ResetOrigin();
#else
                Debug.LogWarning("VitureXR.HeadTracking.ResetOrigin() is only available on VITURE Neckband");
#endif
            }
        }
        
        /// <summary>
        /// Controls the hand tracking algorithm.
        /// Unity XR Hands package must be installed to use this feature.
        /// </summary>
        public static class HandTracking
        {
            /// <summary>
            /// Gets whether hand tracking is currently active.
            /// </summary>
            public static bool IsActive => s_IsActive;
            
            private static bool s_IsActive;

            private static VitureHandAimSensitivity s_AimSensitivity;

            /// <summary>
            /// Sets the hand tracking filter mode.
            /// Responsive has lower latency but more jitter. Stable is smoother but slightly delayed.
            /// </summary>
            public static VitureHandFilterMode filterMode
            {
#if INCLUDE_UNITY_XR_HANDS
                set => VitureHandFilter.SetMode(value);
#else
                set => Debug.LogWarning("XR Hands package (com.unity.xr.hands) is required");
#endif
            }

            /// <summary>
            /// Controls the sensitivity of the hand aim ray direction.
            /// Only takes effect in 6DoF mode.
            /// </summary>
            public static VitureHandAimSensitivity aimSensitivity
            {
#if INCLUDE_UNITY_XR_HANDS
                get => s_AimSensitivity;
                set
                {
                    s_AimSensitivity = value;
                    VitureHandSubsystem.VitureHandProvider.SetAimSensitivity(value);
                }
#else
                get => s_AimSensitivity;
                set => Debug.LogWarning("XR Hands package (com.unity.xr.hands) is required");
#endif
            }

            /// <summary>
            /// Starts the VITURE XR hand algorithm.
            /// </summary>
            public static void Start()
            {
#if UNITY_EDITOR
                Debug.LogWarning("VitureXR.HandTracking.Start() is only available on VITURE Neckband");
                s_IsActive = true;
#elif INCLUDE_UNITY_XR_HANDS
                if (s_IsActive)
                    return;

                s_IsActive = true;
                VitureNativeApi.HandTracking.Start();
#else
                Debug.LogError("XR Hands package (com.unity.xr.hands) is required to use XR Hand Subsystem");
#endif
            }

            /// <summary>
            /// Stops the VITURE XR hand algorithm.
            /// </summary>
            public static void Stop()
            {
#if UNITY_EDITOR
                Debug.LogWarning("VitureXR.HandTracking.Stop() is only available on VITURE Neckband");
                s_IsActive = false;
#elif INCLUDE_UNITY_XR_HANDS
                if (!s_IsActive)
                    return;
                
                VitureNativeApi.HandTracking.Stop();
                s_IsActive = false;
#else
                Debug.LogError("XR Hands package (com.unity.xr.hands) is required to use XR Hand Subsystem");
#endif
            }
        }

        /// <summary>
        /// Groups all physical camera APIs on VITURE glasses.
        /// </summary>
        public static class Camera
        {
            /// <summary>
            /// Provides access to the RGB camera on VITURE glasses.
            /// Use Start/Stop to acquire the camera; add <see cref="VitureRGBCameraManager"/> to a GameObject for RenderTexture display and frame capture.
            /// Supports dynamic resolution via GetSupportedResolutions. To change resolution, Stop then Start with the desired resolution.
            /// </summary>
            public static class RGB
            {
                /// <summary>
                /// Gets whether the RGB camera is supported on the current device.
                /// </summary>
                public static bool isSupported
                {
                    get
                    {
#if UNITY_ANDROID && !UNITY_EDITOR
                        return VitureNativeApi.Camera.RGB.IsSupported();
#else
                        return false;
#endif
                    }
                }

                /// <summary>
                /// Gets whether the RGB camera is currently streaming.
                /// </summary>
                public static bool isActive =>
#if UNITY_ANDROID && !UNITY_EDITOR
                    VitureNativeApi.Camera.RGB.IsAcquired((int)VitureNativeApi.Camera.RGB.Consumer.DeveloperApi);
#else
                    false;
#endif

                /// <summary>
                /// Current output resolution of the camera. Returns the default resolution when inactive.
                /// </summary>
                public static Vector2Int currentResolution
                {
                    get
                    {
#if UNITY_ANDROID && !UNITY_EDITOR
                        VitureNativeApi.Camera.RGB.GetCurrentResolution(out int width, out int height);
                        var r = new Vector2Int(width, height);
                        if (r.x > 0 && r.y > 0) return r;
#endif
                        return GetDefaultResolution();
                    }
                }

                /// <summary>
                /// Gets the default camera resolution for the connected glasses model.
                /// Check whether a custom resolution is active via <c>currentResolution == GetDefaultResolution()</c>.
                /// To reset to default, call <c>Stop()</c> then <c>Start()</c>.
                /// </summary>
                public static Vector2Int GetDefaultResolution()
                {
#if UNITY_ANDROID && !UNITY_EDITOR
                    VitureNativeApi.Camera.RGB.GetDefaultResolution(out int width, out int height);
                    if (width > 0 && height > 0) return new Vector2Int(width, height);
#endif
                    return new Vector2Int(1920, 1080);
                }

                /// <summary>
                /// Invoked when a new camera frame becomes available. Parameter: frame timestamp in nanoseconds.
                /// </summary>
                public static event Action<long> frameAvailable;

                /// <summary>
                /// Starts the RGB camera at the default resolution for the connected glasses model.
                /// Check <see cref="isActive"/> or listen to <see cref="frameAvailable"/> to know when ready.
                /// </summary>
                public static void Start()
                {
#if UNITY_ANDROID && !UNITY_EDITOR
                    GL.IssuePluginEvent(VitureNativeApi.Camera.RGB.GetAcquireOnGLThreadFunc(), 0);
#else
                    Debug.LogWarning("[VitureXR] Camera.RGB.Start() is only available on VITURE Neckband");
#endif
                }

                /// <summary>
                /// Starts the RGB camera at the specified resolution.
                /// Check <see cref="isActive"/> or listen to <see cref="frameAvailable"/> to know when ready.
                /// To change resolution while running, call <see cref="Stop"/> then Start with the new resolution.
                /// </summary>
                /// <param name="width">Desired width in pixels. Must be a supported resolution.</param>
                /// <param name="height">Desired height in pixels. Must be a supported resolution.</param>
                public static void Start(int width, int height)
                {
#if UNITY_ANDROID && !UNITY_EDITOR
                    if (Capture.isRecording && new Vector2Int(width, height) != GetDefaultResolution())
                    {
                        Debug.LogWarning("[VitureXR] Cannot start RGB camera with non-default resolution while recording is active.");
                        return;
                    }
                    VitureNativeApi.Camera.RGB.SetDesiredResolution(width, height);
                    GL.IssuePluginEvent(VitureNativeApi.Camera.RGB.GetAcquireOnGLThreadFunc(), 0);
#else
                    Debug.LogWarning("[VitureXR] Camera.RGB.Start() is only available on VITURE Neckband");
#endif
                }

                /// <summary>
                /// Stops the RGB camera.
                /// </summary>
                public static void Stop()
                {
#if UNITY_ANDROID && !UNITY_EDITOR
                    GL.IssuePluginEvent(VitureNativeApi.Camera.RGB.GetReleaseOnGLThreadFunc(), 0);
#else
                    Debug.LogWarning("[VitureXR] Camera.RGB.Stop() is only available on VITURE Neckband");
#endif
                }

                /// <summary>
                /// Gets supported resolutions for the camera.
                /// </summary>
                public static Vector2Int[] GetSupportedResolutions()
                {
#if UNITY_ANDROID && !UNITY_EDITOR
                    int count = VitureNativeApi.Camera.RGB.GetSupportedResolutionCount();
                    var result = new Vector2Int[count];
                    for (int i = 0; i < count; i++)
                    {
                        VitureNativeApi.Camera.RGB.GetSupportedResolution(i, out int w, out int h);
                        result[i] = new Vector2Int(w, h);
                    }
                    return result;
#else
                    return new[] { new Vector2Int(1920, 1080) };
#endif
                }

                /// <summary>
                /// Gets the native texture ID for the camera frame. Use with Texture2D.CreateExternalTexture or custom pipelines.
                /// </summary>
                public static int GetNativeTextureId()
                {
#if UNITY_ANDROID && !UNITY_EDITOR
                    return VitureNativeApi.Camera.RGB.GetNativeTextureId();
#else
                    return 0;
#endif
                }

                [AOT.MonoPInvokeCallback(typeof(Action<long>))]
                internal static void FrameAvailableCallback(long timestampNs)
                {
                    s_MainThreadContext.Post(_ =>
                    {
                        try
                        {
#if UNITY_ANDROID && !UNITY_EDITOR
                            GL.IssuePluginEvent(VitureNativeApi.Camera.RGB.GetUpdateNativeTextureFunc(), 0);
#endif
                            frameAvailable?.Invoke(timestampNs);
                        }
                        catch (Exception ex)
                        {
                            Debug.LogError($"[VitureXR] Camera.RGB frame callback error: {ex.Message}");
                        }
                    }, null);
                }
            }
        }

        /// <summary>
        /// Controls XR content capture functionality.
        /// Currently supports first-person mixed reality recording with both virtual and real-world layers.
        /// </summary>
        public static class Capture
        {
            /// <summary>
            /// Gets whether a recording is currently in progress.
            /// </summary>
            public static bool isRecording => s_IsRecording;

            /// <summary>
            /// Gets whether a view share session is currently active.
            /// </summary>
            public static bool isSharingView => s_IsSharingView;
            
            /// <summary>
            /// Invoked when recording starts successfully.
            /// </summary>
            public static event Action recordingStartSuccess;

            /// <summary>
            /// Invoked when recording fails to start.
            /// Parameters: errorCode, errorMessage.
            /// </summary>
            public static event Action<int, string> recordingStartFailure;

            /// <summary>
            /// Invoked when recording is saved successfully.
            /// Parameter: filePath.
            /// </summary>
            public static event Action<string> recordingSaveSuccess;

            /// <summary>
            /// Invoked when recording fails to save.
            /// Parameters: errorCode, errorMessage.
            /// </summary>
            public static event Action<int, string> recordingSaveFailure;

            /// <summary>
            /// Invoked when the neckband starts advertising and becomes discoverable to mobile devices.
            /// </summary>
            public static event Action advertisingStarted;

            /// <summary>
            /// Invoked when the neckband stops advertising.
            /// </summary>
            public static event Action advertisingStopped;

            /// <summary>
            /// Invoked when a mobile device connects to the neckband.
            /// </summary>
            public static event Action clientConnected;

            /// <summary>
            /// Invoked when the connected mobile device disconnects.
            /// </summary>
            public static event Action clientDisconnected;

            /// <summary>
            /// Invoked when an alignment calibration session starts with the selected alignment mode.
            /// </summary>
            public static event Action<ViewShareAlignmentMode> alignmentCalibrationStarted;

            /// <summary>
            /// Invoked when the current alignment calibration session stops.
            /// </summary>
            public static event Action alignmentCalibrationStopped;

            /// <summary>
            /// Invoked when an alignment check session starts.
            /// </summary>
            public static event Action alignmentCheckStarted;

            /// <summary>
            /// Invoked when the current alignment check session stops.
            /// </summary>
            public static event Action alignmentCheckStopped;

            /// <summary>
            /// Invoked when a streaming session starts.
            /// </summary>
            public static event Action streamingStarted;

            /// <summary>
            /// Invoked when the current streaming session stops.
            /// </summary>
            public static event Action streamingStopped;
            
            private static bool s_IsRecording;

            private static bool s_IsSharingView;

            private static ViewShareAlignmentMode s_AlignmentMode;

            private static Coroutine s_AutoStopShareCoroutine;

            private static CoroutineRunner s_CoroutineRunner;
            
            private const float k_AutoStopShareTimeoutSeconds = 3f * 60f;
            
            /// <summary>
            /// Starts recording XR content with the specified capture options.
            /// At least one visual layer (virtual or real-world) must be enabled.
            /// Real-world layer capture requires VITURE Luma Pro, Luma Ultra, Luma Cyber, or Beast glasses.
            /// Note: Audio capture (captureAppAudio and captureMicrophoneAudio) is not currently supported and will be
            /// available in future releases.
            /// </summary>
            /// <param name="captureVirtualLayer">If true, captures Unity-rendered content.</param>
            /// <param name="captureRealWorldLayer">If true, captures physical RGB camera feed.</param>
            /// <param name="captureAppAudio">If true, captures application audio output. (Not currently supported)</param>
            /// <param name="captureMicrophoneAudio">If true, captures microphone audio input. (Not currently supported)</param>
            public static void StartRecording(bool captureVirtualLayer = true,
                                              bool captureRealWorldLayer = true,
                                              bool captureAppAudio = false,
                                              bool captureMicrophoneAudio = false)
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                if (s_IsRecording)
                {
                    Debug.LogWarning("[VitureXR] Recording already started, ignoring start request");
                    return;
                }

                if (captureRealWorldLayer)
                {
                    if (!Camera.RGB.isSupported)
                    {
                        Debug.LogWarning("[VitureXR] Cannot capture real-world layer: RGB camera is not supported on current glasses.");
                        captureRealWorldLayer = false;
                    }
                    if (captureRealWorldLayer && Camera.RGB.currentResolution != Camera.RGB.GetDefaultResolution())
                    {
                        Debug.LogError("[VitureXR] Recording with real-world layer is not supported when RGB camera uses custom resolution.");
                        recordingStartFailure?.Invoke(-1, "Recording with real-world layer is not supported when RGB camera uses custom resolution.");
                        return;
                    }
                }
                
                if (!captureVirtualLayer && !captureRealWorldLayer)
                {
                    Debug.LogError("[VitureXR] Cannot start recording: At least one visual layer must be enabled (captureVirtualLayer or captureRealWorldLayer)");
                    recordingStartFailure?.Invoke(-1, "At least one visual layer must be enabled");
                    return;
                }
                
                s_IsRecording = true;
                VitureNativeApi.Capture.StartRecording(captureVirtualLayer,
                                                       captureRealWorldLayer,
                                                       captureAppAudio,
                                                       captureMicrophoneAudio);
#else
                s_IsRecording = true;
                RecordingStartSuccessCallback();
                Debug.LogWarning("VitureXR.Capture.StartRecording() is only available on VITURE Neckband");
#endif
            }

            /// <summary>
            /// Stops the current recording and saves the video file.
            /// </summary>
            public static void StopRecording()
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                if (!s_IsRecording)
                {
                    Debug.LogWarning("Recording not started yet, ignoring stop request");
                    return;
                }

                s_IsRecording = false;
                VitureNativeApi.Capture.StopRecording();
#else
                s_IsRecording = false;
                RecordingSaveSuccessCallback("/default/");
                Debug.LogWarning("VitureXR.Capture.StopRecording() is only available on VITURE Neckband");
#endif
            }

            /// <summary>
            /// Starts advertising to nearby mobile devices on the same local network.
            /// </summary>
            /// <remarks>
            /// View Share allows a mobile device to capture a third-person view of the mixed reality experience.
            /// The typical workflow is:
            /// <list type="number">
            ///     <item><description>Connection: Mobile device connects to the neckband.</description></item>
            ///     <item><description>Alignment calibration: Both devices align their coordinate systems.</description></item>
            ///     <item><description>Alignment check: User visually verifies alignment accuracy.</description></item>
            ///     <item><description>Streaming: AR content is streamed to the mobile device.</description></item>
            /// </list>
            /// Call <see cref="StopViewShare"/> to stop advertising and disconnect any connected client.
            /// </remarks>
            public static void StartViewShare()
            {
                if (s_IsSharingView)
                    return;
                
                s_IsSharingView = true;
                StartAutoStopShareCoroutine();
                advertisingStarted?.Invoke();
#if UNITY_ANDROID && !UNITY_EDITOR
                VitureNativeApi.Capture.StartViewShare();
#else
                Debug.LogWarning("VitureXR.Capture.StartViewShare() is only available on VITURE Neckband");
#endif
            }

            /// <summary>
            /// Stops advertising and disconnects any connected mobile device.
            /// </summary>
            public static void StopViewShare()
            {
                if (!s_IsSharingView)
                    return;
                
                s_IsSharingView = false;
                StopAutoStopShareCoroutine();
                advertisingStopped?.Invoke();
#if UNITY_ANDROID && !UNITY_EDITOR
                VitureNativeApi.Capture.StopViewShare();
#else
                Debug.LogWarning("VitureXR.Capture.StopViewShare() is only available on VITURE Neckband");
#endif
            }
            
            /// <summary>
            /// Sends the tracked marker pose to the mobile device for marker-based alignment calibration.
            /// </summary>
            /// <param name="position">The marker position in the neckband's coordinate system.</param>
            /// <param name="rotation">The marker rotation in the neckband's coordinate system.</param>
            public static void SendTrackedMarkerPose(Vector3 position, Quaternion rotation)
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                VitureNativeApi.Capture.SendTrackedMarkerPose(
                    position.x, position.y, position.z, 
                    rotation.x, rotation.y, rotation.z, rotation.w);
#else
                Debug.LogWarning("VitureXR.Capture.SendTrackedMarkerPose(Vector3, Quaternion) is only available on VITURE Neckband");
#endif
            }
            
            /// <summary>
            /// Gets the local IPv4 address of this device.
            /// </summary>
            /// <returns>The first IPv4 address found.</returns>
            public static string GetLocalIpAddress()
            {
                var host = Dns.GetHostEntry(Dns.GetHostName());
                foreach (var ip in host.AddressList)
                {
                    if (ip.AddressFamily == AddressFamily.InterNetwork)
                    {
                        return ip.ToString();
                    }
                }

                return null;
            }
            
            private static void StartAutoStopShareCoroutine()
            {
                StopAutoStopShareCoroutine();

                var runner = GetOrCreateCoroutineRunner();
                if (runner != null)
                    s_AutoStopShareCoroutine = runner.StartCoroutine(AutoStopShareCoroutine());
            }

            private static void StopAutoStopShareCoroutine()
            {
                if (s_AutoStopShareCoroutine == null)
                    return;

                var runner = GetOrCreateCoroutineRunner();
                if (runner != null)
                    runner.StopCoroutine(s_AutoStopShareCoroutine);

                s_AutoStopShareCoroutine = null;
            }

            private static IEnumerator AutoStopShareCoroutine()
            {
                yield return new WaitForSeconds(k_AutoStopShareTimeoutSeconds);

                s_AutoStopShareCoroutine = null;
                StopViewShare();
            }

            private static CoroutineRunner GetOrCreateCoroutineRunner()
            {
                if (s_CoroutineRunner != null)
                    return s_CoroutineRunner;

                var go = new GameObject("[VitureXR] CoroutineRunner");
                UnityEngine.Object.DontDestroyOnLoad(go);
                go.hideFlags = HideFlags.HideAndDontSave;
                s_CoroutineRunner = go.AddComponent<CoroutineRunner>();
                return s_CoroutineRunner;
            }
            
            private class CoroutineRunner : MonoBehaviour {}

            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void RecordingStartSuccessCallback()
            {
                s_MainThreadContext.Post(_ =>
                {
                    recordingStartSuccess?.Invoke();
                }, null);
            }

            [AOT.MonoPInvokeCallback(typeof(Action<int, string>))]
            internal static void RecordingStartFailureCallback(int errorCode, string errorMessage)
            {
                s_MainThreadContext.Post(_ =>
                {
                    s_IsRecording = false;
                    recordingStartFailure?.Invoke(errorCode, errorMessage);
                }, null);
            }

            [AOT.MonoPInvokeCallback(typeof(Action<string>))]
            internal static void RecordingSaveSuccessCallback(string filePath)
            {
                s_MainThreadContext.Post(_ =>
                {
                    recordingSaveSuccess?.Invoke(filePath);
                }, null);
            }

            [AOT.MonoPInvokeCallback(typeof(Action<int, string>))]
            internal static void RecordingSaveFailureCallback(int errorCode, string errorMessage)
            {
                s_MainThreadContext.Post(_ =>
                {
                    recordingSaveFailure?.Invoke(errorCode,errorMessage);
                }, null);
            }
            
            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void ClientConnectedCallback()
            {
                s_MainThreadContext.Post(_ =>
                {
                    StopAutoStopShareCoroutine();
                    clientConnected?.Invoke();
                }, null);
            }
            
            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void ClientDisconnectedCallback()
            {
                s_MainThreadContext.Post(_ =>
                {
                    if (s_IsSharingView)
                        StartAutoStopShareCoroutine();
                        
                    clientDisconnected?.Invoke();
                }, null);
            }

            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void AlignmentCalibrationStartedCallback(int mode)
            {
                s_MainThreadContext.Post(_ =>
                {
                    s_AlignmentMode = (ViewShareAlignmentMode)mode;
                    switch (s_AlignmentMode)
                    {
                        case ViewShareAlignmentMode.BruteForce:
                            break;
                        case ViewShareAlignmentMode.MarkerSync:
                            break;
                        case ViewShareAlignmentMode.FingerSync:
                            if (!HandTracking.IsActive)
                                HandTracking.Start();
                            break;
                    }
                    
                    alignmentCalibrationStarted?.Invoke(s_AlignmentMode);
                }, null);
            }
            
            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void AlignmentCalibrationStoppedCallback()
            {
                s_MainThreadContext.Post(_ =>
                {
                    switch (s_AlignmentMode)
                    {
                        case ViewShareAlignmentMode.BruteForce:
                            break;
                        case ViewShareAlignmentMode.MarkerSync:
                            break;
                        case ViewShareAlignmentMode.FingerSync:
                            break;
                    }
                    
                    alignmentCalibrationStopped?.Invoke();
                }, null);
            }

            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void AlignmentCheckStartedCallback()
            {
                s_MainThreadContext.Post(_ =>
                {
                    alignmentCheckStarted?.Invoke();
                }, null);
            }

            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void AlignmentCheckStoppedCallback()
            {
                s_MainThreadContext.Post(_ =>
                {
                    alignmentCheckStopped?.Invoke();
                }, null);
            }

            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void StreamingStartedCallback()
            {
                s_MainThreadContext.Post(_ =>
                {
                    streamingStarted?.Invoke();
                }, null);
            }

            [AOT.MonoPInvokeCallback(typeof(Action))]
            internal static void StreamingStoppedCallback()
            {
                s_MainThreadContext.Post(_ =>
                {
                    streamingStopped?.Invoke();
                }, null);
            }
        }
    }
}
