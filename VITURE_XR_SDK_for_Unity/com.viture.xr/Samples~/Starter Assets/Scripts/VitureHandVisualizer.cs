using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Serialization;
using UnityEngine.XR.Hands;

namespace Viture.XR.Samples.StarterAssets
{
    public class VitureHandVisualizer : MonoBehaviour
    {
        [SerializeField] private GameObject m_LeftHandTracking;

        [SerializeField] private GameObject m_RightHandTracking;

        [SerializeField] private bool m_DrawMeshes = true;

        [SerializeField] private bool m_DrawJoints = true;

        [SerializeField] private GameObject m_JointPrefab;

        [SerializeField] private bool m_DrawLines = true;

        [SerializeField] private Material m_LineMaterial;

        private XRHandSubsystem m_HandSubsystem;

        private readonly Dictionary<Handedness, Dictionary<XRHandJointID, GameObject>> m_SpawnedJoints = new();
        private readonly Dictionary<Handedness, Dictionary<XRHandJointID, LineRenderer>> m_JointLines = new();

        private static readonly Vector3[] s_LinePointsReuse = new Vector3[2];

        private const float k_LineWidth = 0.0036f;
        
        // Hand fade settings
        [Serializable]
        private class HandFadeTarget
        {
            public Transform Wrist;
            public Renderer HandRenderer;
            public int[] TargetMaterialIndices;
            [HideInInspector] public float CurrentAlpha = 1.0f;
            [HideInInspector] public float TargetAlpha = 1.0f;
        }

        [SerializeField] private Transform m_CameraHead;
        [SerializeField] private float m_FadeOutThreshold = 0.25f;
        [SerializeField] private float m_FadeInThreshold = 0.3f;
        [SerializeField] private float m_FadeSpeed = 5.0f;
        [SerializeField] private HandFadeTarget[] m_HandTargets;

        private static readonly int s_AlphaPropertyID = Shader.PropertyToID("_Alpha");
        private MaterialPropertyBlock m_SharedPropBlock;

        private void Awake()
        {
            m_SharedPropBlock = new MaterialPropertyBlock();

            if (m_HandTargets != null)
            {
                foreach (var hand in m_HandTargets)
                {
                    hand.CurrentAlpha = 1.0f;
                    hand.TargetAlpha = 1.0f;
                }
            }
        }
        private void Start()
        {
            if (!m_DrawMeshes)
            {
                for (int i = 0; i < 2; i++)
                {
                    var meshController = i == 0
                        ? m_LeftHandTracking.GetComponent<XRHandMeshController>()
                        : m_RightHandTracking.GetComponent<XRHandMeshController>();

                    if (meshController != null)
                    {
                        meshController.enabled = false;
                        meshController.handMeshRenderer.enabled = false;
                    }
                }
            }
            
            if (m_DrawJoints)
            {
                SpawnJointPrefabs(Handedness.Left);
                SpawnJointPrefabs(Handedness.Right);
                
                if (m_HandSubsystem != null)
                {
                    UpdateRenderingVisibility(Handedness.Left, m_HandSubsystem.leftHand.isTracked);
                    UpdateRenderingVisibility(Handedness.Right, m_HandSubsystem.rightHand.isTracked);
                }
            }
        }
        
        private void ProcessHandFade(HandFadeTarget hand)
        {
            if (!hand.Wrist || !hand.HandRenderer) return;

            float distance = Vector3.Distance(hand.Wrist.position, m_CameraHead.position);

            if (distance < m_FadeOutThreshold)
            {
                hand.TargetAlpha = 0.0f;
            }
            else if (distance > m_FadeInThreshold)
            {
                hand.TargetAlpha = 1.0f;
            }

            if (!Mathf.Approximately(hand.CurrentAlpha, hand.TargetAlpha))
            {
                hand.CurrentAlpha = Mathf.MoveTowards(hand.CurrentAlpha, hand.TargetAlpha, m_FadeSpeed * Time.deltaTime);
                ApplyAlphaToMaterials(hand);
            }
        }

        private void ApplyAlphaToMaterials(HandFadeTarget hand)
        {
            if (hand.TargetMaterialIndices == null) return;

            foreach (int index in hand.TargetMaterialIndices)
            {
                if (index < 0 || index >= hand.HandRenderer.sharedMaterials.Length) continue;

                hand.HandRenderer.GetPropertyBlock(m_SharedPropBlock, index);
                m_SharedPropBlock.SetFloat(s_AlphaPropertyID, hand.CurrentAlpha);
                hand.HandRenderer.SetPropertyBlock(m_SharedPropBlock, index);
            }
        }

        private void OnDestroy()
        {
            foreach (var joints in m_SpawnedJoints.Values)
            {
                foreach (var joint in joints.Values)
                {
                    if (joint != null)
                        Destroy(joint);
                }
            }

            m_SpawnedJoints.Clear();
            m_JointLines.Clear();
        }

        private void OnEnable()
        {
            TrySubscribe();
        }

        private void Update()
        {
            if (m_HandSubsystem == null)
                TrySubscribe();
            
            if (!m_CameraHead || m_HandTargets == null) return;
            foreach (var hand in m_HandTargets)
            {
                ProcessHandFade(hand);
            }
        }

        private void OnDisable()
        {
            if (m_HandSubsystem != null)
            {
                m_HandSubsystem.trackingAcquired -= OnTrackingAcquired;
                m_HandSubsystem.trackingLost -= OnTrackingLost;
                m_HandSubsystem.updatedHands -= OnUpdatedHands;
            }
        }
        
        private void TrySubscribe()
        {
            if (m_HandSubsystem != null)
                return;

            var subsystems = new List<XRHandSubsystem>();
            SubsystemManager.GetSubsystems(subsystems);
            if (subsystems.Count == 0)
                return;

            m_HandSubsystem = subsystems[0];
            m_HandSubsystem.trackingAcquired += OnTrackingAcquired;
            m_HandSubsystem.trackingLost += OnTrackingLost;
            m_HandSubsystem.updatedHands += OnUpdatedHands;
        }

        private void SpawnJointPrefabs(Handedness handedness)
        {
            m_SpawnedJoints.Add(handedness, new Dictionary<XRHandJointID, GameObject>());
            m_JointLines.Add(handedness, new Dictionary<XRHandJointID, LineRenderer>());

            XRHandSkeletonDriver skeletonDriver = handedness == Handedness.Left
                ? m_LeftHandTracking.GetComponent<XRHandSkeletonDriver>()
                : m_RightHandTracking.GetComponent<XRHandSkeletonDriver>();

            if (skeletonDriver != null)
            {
                foreach (var jointTransformReference in skeletonDriver.jointTransformReferences)
                {
                    var jointId = jointTransformReference.xrHandJointID;
                    var spawnedJoint = Instantiate(m_JointPrefab, jointTransformReference.jointTransform);
                    m_SpawnedJoints[handedness][jointId] = spawnedJoint;

                    if (m_DrawLines && jointId != XRHandJointID.Wrist)
                    {
                        var lineRenderer = spawnedJoint.AddComponent<LineRenderer>();
                        ConfigureLineRenderer(lineRenderer);
                        m_JointLines[handedness][jointId] = lineRenderer;
                    }
                }
            }
        }

        private void ConfigureLineRenderer(LineRenderer lineRenderer)
        {
            lineRenderer.startWidth = lineRenderer.endWidth = k_LineWidth;
            lineRenderer.positionCount = 2;
            lineRenderer.useWorldSpace = true;
            lineRenderer.material = m_LineMaterial;
        }

        private void OnTrackingAcquired(XRHand hand)
        {
            UpdateRenderingVisibility(hand.handedness, true);
        }

        private void OnTrackingLost(XRHand hand)
        {
            UpdateRenderingVisibility(hand.handedness, false);
        }

        private void OnUpdatedHands(XRHandSubsystem subsystem, XRHandSubsystem.UpdateSuccessFlags updateSuccessFlags,
            XRHandSubsystem.UpdateType updateType)
        {
            if (m_DrawLines)
            {
                if ((updateSuccessFlags & XRHandSubsystem.UpdateSuccessFlags.LeftHandJoints) != 0)
                    UpdateJointLines(subsystem.leftHand);

                if ((updateSuccessFlags & XRHandSubsystem.UpdateSuccessFlags.RightHandJoints) != 0)
                    UpdateJointLines(subsystem.rightHand);
            }
        }

        private void UpdateJointLines(XRHand hand)
        {
            if (!m_JointLines.ContainsKey(hand.handedness))
                return;

            var handedness = hand.handedness;
            var lines = m_JointLines[handedness];

            foreach (var kvp in lines)
            {
                var jointId = kvp.Key;
                var lineRenderer = kvp.Value;
                var parentJointId = GetParentJointId(jointId);

                if (parentJointId == XRHandJointID.Invalid)
                    continue;

                if (hand.GetJoint(jointId).TryGetPose(out var jointPose) &&
                    hand.GetJoint(parentJointId).TryGetPose(out var parentPose))
                {
                    s_LinePointsReuse[0] = parentPose.position;
                    s_LinePointsReuse[1] = jointPose.position;
                    lineRenderer.SetPositions(s_LinePointsReuse);
                }
            }
        }

        private void UpdateRenderingVisibility(Handedness handedness, bool isTracked)
        {
            if (m_SpawnedJoints.TryGetValue(handedness, out var joints))
            {
                foreach (var joint in joints.Values)
                    joint.SetActive(isTracked);
            }
        }

        private XRHandJointID GetParentJointId(XRHandJointID jointId)
        {
            return jointId switch
            {
                // Thumb chain
                XRHandJointID.ThumbProximal => XRHandJointID.Wrist,
                XRHandJointID.ThumbDistal => XRHandJointID.ThumbProximal,
                XRHandJointID.ThumbTip => XRHandJointID.ThumbDistal,

                // Index chain
                XRHandJointID.IndexProximal => XRHandJointID.Wrist,
                XRHandJointID.IndexIntermediate => XRHandJointID.IndexProximal,
                XRHandJointID.IndexDistal => XRHandJointID.IndexIntermediate,
                XRHandJointID.IndexTip => XRHandJointID.IndexDistal,

                // Middle chain
                XRHandJointID.MiddleProximal => XRHandJointID.Wrist,
                XRHandJointID.MiddleIntermediate => XRHandJointID.MiddleProximal,
                XRHandJointID.MiddleDistal => XRHandJointID.MiddleIntermediate,
                XRHandJointID.MiddleTip => XRHandJointID.MiddleDistal,

                // Ring chain
                XRHandJointID.RingProximal => XRHandJointID.Wrist,
                XRHandJointID.RingIntermediate => XRHandJointID.RingProximal,
                XRHandJointID.RingDistal => XRHandJointID.RingIntermediate,
                XRHandJointID.RingTip => XRHandJointID.RingDistal,

                // Little chain
                XRHandJointID.LittleProximal => XRHandJointID.Wrist,
                XRHandJointID.LittleIntermediate => XRHandJointID.LittleProximal,
                XRHandJointID.LittleDistal => XRHandJointID.LittleIntermediate,
                XRHandJointID.LittleTip => XRHandJointID.LittleDistal,

                // Palm connects to wrist
                XRHandJointID.Palm => XRHandJointID.Wrist,

                _ => XRHandJointID.Invalid
            };
        }
    }
}