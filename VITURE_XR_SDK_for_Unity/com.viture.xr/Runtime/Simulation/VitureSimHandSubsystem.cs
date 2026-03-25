#if UNITY_EDITOR && INCLUDE_UNITY_XR_HANDS
using System.Collections.Generic;
using Unity.Collections;
using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.Hands;
using UnityEngine.XR.Hands.ProviderImplementation;
using Viture.XR.InputDevices;

namespace Viture.XR.Simulation
{
    /// <summary>
    /// Simulated hand tracking subsystem for Editor use.
    /// Provides the full XRHandSubsystem contract (tracking events, joint data)
    /// and feeds VitureHandDevice for Input System integration.
    /// </summary>
    internal class VitureSimHandSubsystem : XRHandSubsystem
    {
        internal const string k_Id = "Viture-Sim-Hands";

        private XRHandProviderUtility.SubsystemUpdater m_Updater;
        private VitureSimHandProvider m_SimProvider => provider as VitureSimHandProvider;

        internal void SetIsTracked(Handedness h, bool tracked) => m_SimProvider.SetIsTracked(h, tracked);
        internal void SetRootPose(Handedness h, Pose pose) => m_SimProvider.SetRootPose(h, pose);
        internal void SetAimPose(Handedness h, Pose pose) => m_SimProvider.SetAimPose(h, pose);
        internal void SetSelect(Handedness h, bool select) => m_SimProvider.SetSelect(h, select);
        internal void SetExpression(Handedness h, VitureSimHandExpression expr) => m_SimProvider.SetExpression(h, expr);

        protected override void OnCreate()
        {
            base.OnCreate();
            m_Updater = new XRHandProviderUtility.SubsystemUpdater(this);
        }

        protected override void OnStart()
        {
            m_Updater.Start();
            base.OnStart();
        }

        protected override void OnStop()
        {
            m_Updater.Stop();
            base.OnStop();
        }

        protected override void OnDestroy()
        {
            m_Updater.Destroy();
            m_Updater = null;
            base.OnDestroy();
        }
        
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        private static void Register()
        {
            XRHandSubsystemDescriptor.Register(new XRHandSubsystemDescriptor.Cinfo
            {
                id = k_Id,
                providerType = typeof(VitureSimHandProvider),
                subsystemTypeOverride = typeof(VitureSimHandSubsystem)
            });
        }

        private class VitureSimHandProvider : XRHandSubsystemProvider
        {
            class HandState
            {
                public bool isTracked;
                public Pose rootPose = Pose.identity;
                public Pose aimPose = Pose.identity;
                public bool select;
                public VitureSimHandExpression expression;
            }

            private readonly HandState m_LeftHand = new();
            private readonly HandState m_RightHand = new();
            
            // Reusable buffer for computed world poses
            private readonly Pose[] m_WorldPoses = new Pose[XRHandJointID.EndMarker.ToIndex()];

            private HandState GetHandState(Handedness h) => h == Handedness.Left ? m_LeftHand : m_RightHand;

            internal void SetIsTracked(Handedness h, bool tracked) => GetHandState(h).isTracked = tracked;

            internal void SetRootPose(Handedness h, Pose pose) => GetHandState(h).rootPose = pose;

            internal void SetAimPose(Handedness h, Pose pose) => GetHandState(h).aimPose = pose;

            internal void SetSelect(Handedness h, bool select) => GetHandState(h).select = select;

            internal void SetExpression(Handedness h, VitureSimHandExpression expr) =>
                GetHandState(h).expression = expr;
            
            public override void Start() {}
            public override void Stop() {}
            public override void Destroy() {}

            public override void GetHandLayout(NativeArray<bool> handJointsInLayout)
            {
                handJointsInLayout[XRHandJointID.Wrist.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.Palm.ToIndex()] = true;

                handJointsInLayout[XRHandJointID.ThumbMetacarpal.ToIndex()] = false;
                handJointsInLayout[XRHandJointID.ThumbProximal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.ThumbDistal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.ThumbTip.ToIndex()] = true;
                
                handJointsInLayout[XRHandJointID.IndexMetacarpal.ToIndex()] = false;
                handJointsInLayout[XRHandJointID.IndexProximal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.IndexIntermediate.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.IndexDistal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.IndexTip.ToIndex()] = true;
                
                handJointsInLayout[XRHandJointID.MiddleMetacarpal.ToIndex()] = false;
                handJointsInLayout[XRHandJointID.MiddleProximal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.MiddleIntermediate.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.MiddleDistal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.MiddleTip.ToIndex()] = true;
                
                handJointsInLayout[XRHandJointID.RingMetacarpal.ToIndex()] = false;
                handJointsInLayout[XRHandJointID.RingProximal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.RingIntermediate.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.RingDistal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.RingTip.ToIndex()] = true;
                
                handJointsInLayout[XRHandJointID.LittleMetacarpal.ToIndex()] = false;
                handJointsInLayout[XRHandJointID.LittleProximal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.LittleIntermediate.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.LittleDistal.ToIndex()] = true;
                handJointsInLayout[XRHandJointID.LittleTip.ToIndex()] = true;
            }

            public override UpdateSuccessFlags TryUpdateHands(
                UpdateType updateType,
                ref Pose leftHandRootPose, NativeArray<XRHandJoint> leftHandJoints,
                ref Pose rightHandRootPose, NativeArray<XRHandJoint> rightHandJoints)
            {
                var flags = UpdateSuccessFlags.None;

                // Always push device state (so VitureHandDevice reflects tracking loss)
                UpdateDevice(Handedness.Left, m_LeftHand);
                UpdateDevice(Handedness.Right, m_RightHand);
                
                // Only fill joints when tracked
                // (base XRHandSubsystem fires trackingAcquired/trackingLost based on these flags)
                if (m_LeftHand.isTracked)
                {
                    FillJoints(Handedness.Left, m_LeftHand, ref leftHandRootPose, leftHandJoints);
                    flags |= UpdateSuccessFlags.LeftHandRootPose | UpdateSuccessFlags.LeftHandJoints;
                }

                if (m_RightHand.isTracked)
                {
                    FillJoints(Handedness.Right, m_RightHand, ref rightHandRootPose, rightHandJoints);
                    flags |= UpdateSuccessFlags.RightHandRootPose | UpdateSuccessFlags.RightHandJoints;
                }

                return flags;
            }

            /// <summary>
            /// Generates a minimal flat open-hand skeleton relative to the wrist pose.
            /// </summary>
            private void FillJoints(Handedness handedness, HandState state, ref Pose rootPose,
                NativeArray<XRHandJoint> joints)
            {
                rootPose = state.rootPose;
                var expr = state.expression;

                if (expr == null)
                    return;

                // Initialize all to rootPose so any missing parent falls back to wrist
                for (int i = 0; i < m_WorldPoses.Length; i++)
                    m_WorldPoses[i] = state.rootPose;

                SetJoint(joints, handedness, XRHandJointID.Wrist, state.rootPose.position, state.rootPose.rotation);

                // Iterate in enum order — parents are always processed before children
                for (var jointId = XRHandJointID.Palm; jointId < XRHandJointID.EndMarker; jointId++)
                {
                    if (!expr.TryGetJointPose(handedness, jointId, out var localPose))
                        continue;

                    var parentId = s_ParentJoint.GetValueOrDefault(jointId, XRHandJointID.Wrist);
                    var parentPose = m_WorldPoses[parentId.ToIndex()];

                    var worldPos = parentPose.position + parentPose.rotation * localPose.position;
                    var worldRot = parentPose.rotation * localPose.rotation;

                    m_WorldPoses[jointId.ToIndex()] = new Pose(worldPos, worldRot);
                    SetJoint(joints, handedness, jointId, worldPos, worldRot);
                }
            }

            private static void SetJoint(NativeArray<XRHandJoint> joints, Handedness handedness, XRHandJointID jointId,
                Vector3 position, Quaternion rotation)
            {
                joints[jointId.ToIndex()] = XRHandProviderUtility.CreateJoint(handedness, XRHandJointTrackingState.Pose,
                    jointId, new Pose(position, rotation));
            }

            private void UpdateDevice(Handedness handedness, HandState state)
            {
                if (!state.isTracked)
                {
                    VitureHandDevice.UpdateDeviceState(
                        handedness, false, InputTrackingState.None, 
                        Vector3.zero, Quaternion.identity, 
                        new VitureHandState());
                    return;
                }

                var indexTipPos = state.rootPose.position + state.rootPose.rotation * new Vector3(0f, 0f, 0.1f);
                
                VitureHandDevice.UpdateDeviceState(
                    handedness, true, 
                    InputTrackingState.Position | InputTrackingState.Rotation,
                    state.rootPose.position, state.rootPose.rotation,
                    new VitureHandState
                    {
                        aimPosition = state.aimPose.position,
                        aimRotation = state.aimPose.rotation,
                        pinchPosition = state.rootPose.position,
                        pokePosition = indexTipPos,
                        pokeRotation = state.rootPose.rotation,
                        select = state.select,
                        gesture = state.select ? (int)VitureGesture.Pinch : (int)VitureGesture.None,
                        palmFacing = (int)ViturePalmFacing.Up
                    });
            }
            
            private static readonly Dictionary<XRHandJointID, XRHandJointID> s_ParentJoint = new()
            {
                { XRHandJointID.Palm, XRHandJointID.Wrist },
                { XRHandJointID.ThumbProximal, XRHandJointID.Wrist },
                { XRHandJointID.ThumbDistal, XRHandJointID.ThumbProximal },
                { XRHandJointID.ThumbTip, XRHandJointID.ThumbDistal },
                { XRHandJointID.IndexProximal, XRHandJointID.Wrist },
                { XRHandJointID.IndexIntermediate, XRHandJointID.IndexProximal },
                { XRHandJointID.IndexDistal, XRHandJointID.IndexIntermediate },
                { XRHandJointID.IndexTip, XRHandJointID.IndexDistal },
                { XRHandJointID.MiddleProximal, XRHandJointID.Wrist },
                { XRHandJointID.MiddleIntermediate, XRHandJointID.MiddleProximal },
                { XRHandJointID.MiddleDistal, XRHandJointID.MiddleIntermediate },
                { XRHandJointID.MiddleTip, XRHandJointID.MiddleDistal },
                { XRHandJointID.RingProximal, XRHandJointID.Wrist },
                { XRHandJointID.RingIntermediate, XRHandJointID.RingProximal },
                { XRHandJointID.RingDistal, XRHandJointID.RingIntermediate },
                { XRHandJointID.RingTip, XRHandJointID.RingDistal },
                { XRHandJointID.LittleProximal, XRHandJointID.Wrist },
                { XRHandJointID.LittleIntermediate, XRHandJointID.LittleProximal },
                { XRHandJointID.LittleDistal, XRHandJointID.LittleIntermediate },
                { XRHandJointID.LittleTip, XRHandJointID.LittleDistal },
            };
        }
    }
}
#endif
