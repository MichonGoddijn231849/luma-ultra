using System;
using System.Runtime.InteropServices;

namespace Viture.XR
{
    internal static partial class VitureNativeApi
    {
        internal static class Capture
        {
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_RegisterCallbacks")]
            internal static extern void RegisterCallbacks(
                Action<int, int, int, float> createCaptureCameraCallback,
                Action<int> destroyCaptureCameraCallback,
                Action createDeviceCameraTextureCallback,
                Action destroyDeviceCameraTextureCallback,
                Action initializeRecordingCompositorContextCallback,
                Action shutdownRecordingCompositorContextCallback,
                Action initializeStreamingCompositorContextCallback,
                Action shutdownStreamingCompositorContextCallback,
                Action<int, float, float, float, float, float, float, float, float> updateAndRenderCallback);

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_OnCaptureCameraCreated")]
            internal static extern void OnCaptureCameraCreated(int type, IntPtr renderTexturePtr);

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetCreateDeviceCameraTextureFunc")]
            internal static extern IntPtr GetCreateDeviceCameraTextureFunc();
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetUpdateDeviceCameraTextureFunc")]
            internal static extern IntPtr GetUpdateDeviceCameraTextureFunc();
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetDestroyDeviceCameraTextureFunc")]
            internal static extern IntPtr GetDestroyDeviceCameraTextureFunc();
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetInitializeRecordingCompositorContextFunc")]
            internal static extern IntPtr GetInitializeRecordingCompositorContextFunc();

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetCompositeRecordingFrameFunc")]
            internal static extern IntPtr GetCompositeRecordingFrameFunc();
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetShutdownRecordingCompositorContextFunc")]
            internal static extern IntPtr GetShutdownRecordingCompositorContextFunc();

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetInitializeStreamingCompositorContextFunc")]
            internal static extern IntPtr GetInitializeStreamingCompositorContextFunc();

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetBlitToEncoderSurfaceFunc")]
            internal static extern IntPtr GetBlitToEncoderSurfaceFunc();

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_GetShutdownStreamingCompositorContextFunc")]
            internal static extern IntPtr GetShutdownStreamingCompositorContextFunc();
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_RegisterRecordingCallbacks")]
            internal static extern void RegisterRecordingCallbacks(
                Action recordingStartSuccessCallback,
                Action<int, string> recordingStartFailureCallback,
                Action<string> recordingSaveSuccessCallback,
                Action<int, string> recordingSaveFailureCallback);
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_StartRecording")]
            internal static extern void StartRecording(
                bool captureVirtualLayer, bool captureRealWorldLayer,
                bool captureAppAudio, bool captureMicrophoneAudio);
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_StopRecording")]
            internal static extern void StopRecording();
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_RegisterViewShareCallback")]
            internal static extern void RegisterViewShareCallbacks(
                Action clientConnectedCallback,
                Action clientDisconnectedCallback,
                Action<int> alignmentCalibrationStartedCallback,
                Action alignmentCalibrationStoppedCallback,
                Action alignmentCheckStartedCallback,
                Action alignmentCheckStoppedCallback,
                Action streamingStartedCallback,
                Action streamingStoppedCallback);
            
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_StartViewShare")]
            internal static extern void StartViewShare();

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_StopViewShare")]
            internal static extern void StopViewShare();

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Capture_SendTrackedMarkerPose")]
            internal static extern void SendTrackedMarkerPose(
                float posX, float posY, float posZ,
                float rotX, float rotY, float rotZ, float rotW);
        }
    }
}
