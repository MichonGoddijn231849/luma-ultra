using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace Viture.XR
{
    internal static partial class VitureNativeApi
    {
        internal static class Camera
        {
            internal static class RGB
            {
                /// <summary>
                /// Consumer type for RGB camera acquisition.
                /// </summary>
                internal enum Consumer { Recording = 0, DeveloperApi = 1, Screenshot = 2 }

                #region Camera Control

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_IsAcquired")]
                internal static extern bool IsAcquired(int consumer);

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetActiveConsumerCount")]
                internal static extern int GetActiveConsumerCount();

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetSharedTextureId")]
                internal static extern int GetNativeTextureId();

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetAcquireOnGLThreadFunc")]
                internal static extern IntPtr GetAcquireOnGLThreadFunc();

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetReleaseOnGLThreadFunc")]
                internal static extern IntPtr GetReleaseOnGLThreadFunc();

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetUpdateTextureFunc")]
                internal static extern IntPtr GetUpdateNativeTextureFunc();

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_SetDesiredResolution")]
                internal static extern void SetDesiredResolution(int width, int height);

                #endregion

                #region Camera Data

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetCurrentResolution")]
                internal static extern void GetCurrentResolution(out int width, out int height);

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetDefaultResolution")]
                internal static extern void GetDefaultResolution(out int width, out int height);

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetLatestFrameTimestamp")]
                internal static extern long GetLatestFrameTimestamp();

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_IsSupported")]
                internal static extern bool IsSupported();

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetSupportedResolutionCount")]
                internal static extern int GetSupportedResolutionCount();

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_GetSupportedResolution")]
                internal static extern void GetSupportedResolution(int index, out int width, out int height);

                #endregion

                #region Callbacks

                [DllImport(k_LibName, EntryPoint = "VitureUnityXR_Camera_RGB_RegisterCallbacks")]
                internal static extern void RegisterFrameAvailableCallback(Action<long> frameAvailable);
                
                #endregion
            }
        }
    }
}
