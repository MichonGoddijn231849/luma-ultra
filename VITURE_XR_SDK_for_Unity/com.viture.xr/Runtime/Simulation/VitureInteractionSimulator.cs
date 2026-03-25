#if UNITY_EDITOR && INCLUDE_UNITY_XR_HANDS
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;
using UnityEngine.XR;
using UnityEngine.XR.Hands;
using Viture.XR.InputDevices;

namespace Viture.XR.Simulation
{
    /// <summary>
    /// Editor-only MonoBehaviour that simulates HMD and hand input using mouse and keyboard.
    ///
    /// Controls:
    ///   Right-click + drag  — Rotate HMD (yaw / pitch)
    ///   WASD                — Move HMD (forward / left / back / right)
    ///   R / F               — Move HMD (up / down)
    ///   Mouse position      — Hand aim direction
    ///   Left-click          — Select / Pinch
    ///   Q                   — Toggle left hand tracking on/off
    ///   E                   — Toggle right hand tracking on/off
    /// </summary>
    internal class VitureInteractionSimulator : MonoBehaviour
    {
        [SerializeField]
        private Camera m_MainCamera;
        
        [Header("HMD")]
        [SerializeField]
        private Vector2 m_MouseSensitivity = new(0.2f, 0.2f);

        [SerializeField]
        private float m_MoveSpeed = 1f;
        
        [Header("Hand")]
        [SerializeField]
        private Vector3 m_LeftHandPositionOffset = new(-0.2f, -0.1f, 0.4f);

        [SerializeField]
        private Quaternion m_LeftHandRotationOffset = Quaternion.Euler(-60f, 0f, 0f);
        
        [SerializeField]
        private Vector3 m_RightHandPositionOffset = new(0.2f, -0.1f, 0.4f);
        
        [SerializeField]
        private Quaternion m_RightHandRotationOffset = Quaternion.Euler(-60f, 0f, 0f);

        [SerializeField]
        private VitureSimHandExpression m_RestExpression;

        [SerializeField]
        private VitureSimHandExpression m_PinchExpression;
        
        // HMD state
        private XRHMD m_HMD;
        private float m_Yaw;
        private float m_Pitch;
        private Vector3 m_Position;
        
        // Hand state
        private VitureSimHandSubsystem m_HandSubsystem;
        private bool m_LeftHandTracked;
        private bool m_RightHandTracked;

        private void Awake()
        {
            SetupHMD();
            SetupHands();
        }

        private void SetupHMD()
        {
            m_HMD = InputSystem.AddDevice<XRHMD>("Viture Sim HMD");
        }

        private void SetupHands()
        {
            VitureHandDevice.InitializeDevices();

            var descriptors = new List<XRHandSubsystemDescriptor>();
            SubsystemManager.GetSubsystemDescriptors(descriptors);

            foreach (var desc in descriptors)
            {
                if (desc.id == VitureSimHandSubsystem.k_Id)
                {
                    m_HandSubsystem = desc.Create() as VitureSimHandSubsystem;
                    break;
                }
            }
            
            if (m_HandSubsystem != null)
                m_HandSubsystem.Start();
            else
                Debug.LogError("[VitureInteractionSimulator] Failed to create VitureSimHandSubsystem");
        }

        private void Update()
        {
            UpdateHMD();
            UpdateHands();
        }

        private void UpdateHMD()
        {
            if (m_HMD == null)
                return;

            if (Mouse.current != null && Mouse.current.rightButton.isPressed)
            {
                var delta = Mouse.current.delta.ReadValue();
                m_Yaw += delta.x * m_MouseSensitivity.x;
                m_Pitch -= delta.y * m_MouseSensitivity.y;
                m_Pitch = Mathf.Clamp(m_Pitch, -89f, 89f);
            }

            var rotation = Quaternion.Euler(m_Pitch, m_Yaw, 0f);

            if (Keyboard.current != null)
            {
                var move = Vector3.zero;

                if (Keyboard.current.wKey.isPressed) move += Vector3.forward;
                if (Keyboard.current.sKey.isPressed) move += Vector3.back;
                if (Keyboard.current.aKey.isPressed) move += Vector3.left;
                if (Keyboard.current.dKey.isPressed) move += Vector3.right;
                if (Keyboard.current.rKey.isPressed) move += Vector3.up;
                if (Keyboard.current.fKey.isPressed) move += Vector3.down;

                m_Position += rotation * move * m_MoveSpeed * Time.deltaTime;
            }
            
            var trackingState = (int)(InputTrackingState.Position | InputTrackingState.Rotation);

            InputSystem.QueueDeltaStateEvent(m_HMD.isTracked, true);
            InputSystem.QueueDeltaStateEvent(m_HMD.trackingState, trackingState);
            InputSystem.QueueDeltaStateEvent(m_HMD.devicePosition, m_Position);
            InputSystem.QueueDeltaStateEvent(m_HMD.deviceRotation, rotation);
            InputSystem.QueueDeltaStateEvent(m_HMD.centerEyePosition, m_Position);
            InputSystem.QueueDeltaStateEvent(m_HMD.centerEyeRotation, rotation);
        }

        private void UpdateHands()
        {
            if (m_HandSubsystem == null)
                return;

            if (Keyboard.current != null)
            {
                if (Keyboard.current.qKey.wasPressedThisFrame)
                {
                    m_LeftHandTracked = !m_LeftHandTracked;
                    Debug.Log($"[VitureInteractionSimulator] Left hand: {(m_LeftHandTracked ? "ON" : "OFF")}");
                }

                if (Keyboard.current.eKey.wasPressedThisFrame)
                {
                    m_RightHandTracked = !m_RightHandTracked;
                    Debug.Log($"[VitureInteractionSimulator] Right hand: {(m_RightHandTracked ? "ON" : "OFF")}");
                }
            }

            var hmdRotation = Quaternion.Euler(m_Pitch, m_Yaw, 0f);

            UpdateSingleHand(Handedness.Left, m_LeftHandTracked, hmdRotation);
            UpdateSingleHand(Handedness.Right, m_RightHandTracked, hmdRotation);
        }

        private void UpdateSingleHand(Handedness handedness, bool tracked, Quaternion hmdRotation)
        {
            m_HandSubsystem.SetIsTracked(handedness, tracked);

            if (!tracked)
                return;

            var posOffset = handedness == Handedness.Left ? m_LeftHandPositionOffset : m_RightHandPositionOffset;
            var rotOffset = handedness == Handedness.Left ? m_LeftHandRotationOffset : m_RightHandRotationOffset;

            var handPos = m_Position + hmdRotation * posOffset;
            var handRot = hmdRotation * rotOffset;
            
            m_HandSubsystem.SetRootPose(handedness, new Pose(handPos, handRot));

            if (m_MainCamera == null)
                m_MainCamera = Camera.main;

            if (m_MainCamera != null && Mouse.current != null)
            {
                var mousePos = Mouse.current.position.ReadValue();
                var ray = m_MainCamera.ScreenPointToRay(new Vector3(mousePos.x, mousePos.y, 0f));
                var aimRot = Quaternion.LookRotation(ray.direction);
                m_HandSubsystem.SetAimPose(handedness, new Pose(handPos, aimRot));
            }
            else
            {
                m_HandSubsystem.SetAimPose(handedness, new Pose(handPos, handRot));
            }

            bool select = Mouse.current != null && Mouse.current.leftButton.isPressed;
            m_HandSubsystem.SetSelect(handedness, select);
            m_HandSubsystem.SetExpression(handedness, select ? m_PinchExpression : m_RestExpression);
        }

        private void OnDestroy()
        {
            if (m_HandSubsystem != null)
            {
                m_HandSubsystem.Stop();
                m_HandSubsystem.Destroy();
                m_HandSubsystem = null;
            }

            if (m_HMD != null && m_HMD.added)
            {
                InputSystem.RemoveDevice(m_HMD);
                m_HMD = null;
            }
        }
    }
}
#endif
