using System.Collections.Generic;
#if INCLUDE_UNITY_XR_HANDS
using UnityEngine.XR.Hands;
#endif

namespace Viture.XR
{
    internal enum VitureHandJointID
    {
        ThumbTip = 0,
        IndexTip = 1,
        MiddleTip = 2,
        RingTip = 3,
        LittleTip = 4,
        Wrist = 5,
        ThumbProximal = 6,
        ThumbDistal = 7,
        IndexProximal = 8,
        IndexIntermediate = 9,
        IndexDistal = 10,
        MiddleProximal = 11,
        MiddleIntermediate = 12,
        MiddleDistal = 13,
        RingProximal = 14,
        RingIntermediate = 15,
        RingDistal = 16,
        LittleProximal = 17,
        LittleIntermediate = 18,
        LittleDistal = 19,
        Palm = 20,
        None = 21
    }

    internal static class VitureHandTrackingData
    {
        internal const int k_HandDataLength = 374;
        internal const int k_HandJointCount = 26;
        internal const int k_PalmFacingOffset = 185;
        internal const int k_GestureOffset = 186;
        
#if INCLUDE_UNITY_XR_HANDS
        internal static readonly Dictionary<VitureHandJointID, XRHandJointID> s_JointMapping = new()
        {
            { VitureHandJointID.Wrist, XRHandJointID.Wrist },
            { VitureHandJointID.Palm, XRHandJointID.Palm },

            { VitureHandJointID.ThumbProximal, XRHandJointID.ThumbProximal },
            { VitureHandJointID.ThumbDistal, XRHandJointID.ThumbDistal },
            { VitureHandJointID.ThumbTip, XRHandJointID.ThumbTip },

            { VitureHandJointID.IndexProximal, XRHandJointID.IndexProximal },
            { VitureHandJointID.IndexIntermediate, XRHandJointID.IndexIntermediate },
            { VitureHandJointID.IndexDistal, XRHandJointID.IndexDistal },
            { VitureHandJointID.IndexTip, XRHandJointID.IndexTip },

            { VitureHandJointID.MiddleProximal, XRHandJointID.MiddleProximal },
            { VitureHandJointID.MiddleIntermediate, XRHandJointID.MiddleIntermediate },
            { VitureHandJointID.MiddleDistal, XRHandJointID.MiddleDistal },
            { VitureHandJointID.MiddleTip, XRHandJointID.MiddleTip },

            { VitureHandJointID.RingProximal, XRHandJointID.RingProximal },
            { VitureHandJointID.RingIntermediate, XRHandJointID.RingIntermediate },
            { VitureHandJointID.RingDistal, XRHandJointID.RingDistal },
            { VitureHandJointID.RingTip, XRHandJointID.RingTip },

            { VitureHandJointID.LittleProximal, XRHandJointID.LittleProximal },
            { VitureHandJointID.LittleIntermediate, XRHandJointID.LittleIntermediate },
            { VitureHandJointID.LittleDistal, XRHandJointID.LittleDistal },
            { VitureHandJointID.LittleTip, XRHandJointID.LittleTip }
        };
#endif
    }
}
