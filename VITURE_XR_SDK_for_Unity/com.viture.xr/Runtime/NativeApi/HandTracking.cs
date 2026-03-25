using System;
using System.Runtime.InteropServices;

namespace Viture.XR
{
    internal static partial class VitureNativeApi
    {
        internal static class HandTracking
        {
            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_HandTracking_Start")]
            internal static extern void Start();

            [DllImport(k_LibName, EntryPoint = "VitureUnityXR_HandTracking_Stop")]
            internal static extern void Stop();

            [DllImport(k_LibName, CallingConvention = CallingConvention.Cdecl, EntryPoint = "VitureUnityXR_HandTracking_ReadData")]
            internal static extern bool ReadData(
                [Out] [MarshalAs(UnmanagedType.LPArray, SizeConst = VitureHandTrackingData.k_HandDataLength)] float[] dataPtr);
        }
    }
}
