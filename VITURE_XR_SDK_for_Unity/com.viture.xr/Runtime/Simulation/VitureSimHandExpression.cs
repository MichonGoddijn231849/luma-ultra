#if UNITY_EDITOR && INCLUDE_UNITY_XR_HANDS
using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.Hands;

namespace Viture.XR.Simulation
{
    [CreateAssetMenu(fileName = "New Hand Expression", menuName = "VITURE/Sim Hand Expression")]
    public class VitureSimHandExpression : ScriptableObject
    {
        [Serializable]
        public struct JointPose
        {
            public XRHandJointID jointId;
            public Pose pose;
        }

        [SerializeField]
        private List<JointPose> m_LeftJointPoses;

        [SerializeField]
        private List<JointPose> m_RightJointPoses;
        

        // Runtime flat lookup
        private Pose[] m_LeftPoses, m_RightPoses;
        private bool[] m_LeftHas, m_RightHas;

        public bool TryGetJointPose(Handedness handedness, XRHandJointID jointId, out Pose pose)
        {
            if (m_LeftPoses == null)
                BuildLookup();
            
            var poses = handedness == Handedness.Left ? m_LeftPoses : m_RightPoses;
            var has = handedness == Handedness.Left ? m_LeftHas : m_RightHas;

            var i = jointId.ToIndex();
            if (has[i])
            {
                pose = poses[i];
                return true;
            }

            pose = Pose.identity;
            return false;
        }

        private void BuildLookup()
        {
            var size = XRHandJointID.EndMarker.ToIndex();
            m_LeftPoses = new Pose[size];
            m_LeftHas = new bool[size];
            m_RightPoses = new Pose[size];
            m_RightHas = new bool[size];

            BuildSide(m_LeftJointPoses, m_LeftPoses, m_LeftHas);
            BuildSide(m_RightJointPoses, m_RightPoses, m_RightHas);
        }

        private static void BuildSide(List<JointPose> source, Pose[] poses, bool[] has)
        {
            if (source == null)
                return;

            foreach (var jp in source)
            {
                var i = jp.jointId.ToIndex();
                poses[i] = jp.pose;
                has[i] = true;
            }
        }

        private void OnValidate()
        {
            m_LeftPoses = m_RightPoses = null;
            m_LeftHas = m_RightHas = null;
        }
    }
}
#endif
