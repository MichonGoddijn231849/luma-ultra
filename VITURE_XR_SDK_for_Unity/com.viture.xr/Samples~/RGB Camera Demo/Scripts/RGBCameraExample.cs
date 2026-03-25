using System;
using System.IO;
using System.Security.Cryptography;
using System.Threading;
using UnityEngine;
using UnityEngine.UI;
using Viture.XR;
using Object = UnityEngine.Object;

/// <summary>
/// RGB camera usage example.
/// Add VitureRGBCameraManager to the scene. Use VitureXR.Camera.RGB for Start/Stop; use VitureRGBCameraManager.Instance for texture and capture.
/// </summary>
public class RGBCameraExample : MonoBehaviour
{
    private const string k_LogTag = "[RGBCameraExample]";

    [Header("Control")]
    [SerializeField]
    [Tooltip("Button to toggle RGB camera on/off. If null, camera auto-starts.")]
    private Button m_ToggleButton;

    [SerializeField]
    [Tooltip("Optional Text on the toggle button to show state (e.g. \"Open Camera\" / \"Close Camera\").")]
    private Text m_ToggleButtonText;

    [Header("Resolution")]
    [SerializeField]
    [Tooltip("Dropdown to select camera resolution. Only enabled when camera is active.")]
    private Dropdown m_ResolutionDropdown;

    [Header("Display")]
    [SerializeField]
    [Tooltip("RawImage to display camera feed (UI).")]
    private RawImage m_DisplayRawImage;

    [SerializeField]
    [Tooltip("Renderer to display camera feed (3D object).")]
    private Renderer m_DisplayRenderer;

    [SerializeField]
    [Tooltip("When enabled, RawImage and Renderer size/scale update with camera resolution.")]
    public bool m_FixedDisplaySize = true;

    private bool m_UseButtonControl;
    private bool m_LastIsActive;
    private Vector2Int[] m_SupportedResolutions;
    private Vector2Int? m_SelectedResolution;
    private RenderTexture m_LastAssignedTexture;

    private void Start()
    {
        if (!VitureXR.Camera.RGB.isSupported)
        {
            LogWarning("RGB Camera is not supported on this device.");
            return;
        }

        if (VitureRGBCameraManager.Instance == null)
        {
            LogError("VitureRGBCameraManager required in scene. Add it to a GameObject.");
            return;
        }

        m_UseButtonControl = m_ToggleButton != null;
        if (m_UseButtonControl)
        {
            m_ToggleButton.onClick.AddListener(OnToggleButtonClicked);
            m_LastIsActive = VitureXR.Camera.RGB.isActive;
            UpdateToggleButtonState();
        }
        else
        {
            StartCameraWithSelectedResolution();
        }

        SetupResolutionDropdown();
    }

    private void SetupResolutionDropdown()
    {
        if (m_ResolutionDropdown == null) return;

        m_SupportedResolutions = VitureXR.Camera.RGB.GetSupportedResolutions();
        m_ResolutionDropdown.ClearOptions();
        var options = new System.Collections.Generic.List<string>();
        foreach (var r in m_SupportedResolutions)
            options.Add($"{r.x} x {r.y}");
        m_ResolutionDropdown.AddOptions(options);
        m_ResolutionDropdown.onValueChanged.AddListener(OnResolutionDropdownChanged);
        SyncDropdownToCurrentResolution();
        UpdateResolutionDropdownState();
    }

    private void OnResolutionDropdownChanged(int index)
    {
        if (m_SupportedResolutions == null || index < 0 || index >= m_SupportedResolutions.Length)
            return;

        var res = m_SupportedResolutions[index];
        m_SelectedResolution = res;
        Log($"Resolution selected: {res.x}x{res.y}");

        if (VitureXR.Camera.RGB.isActive)
        {
            VitureXR.Camera.RGB.Stop();
            VitureXR.Camera.RGB.Start(res.x, res.y);
            m_LastAssignedTexture = null;
        }
    }

    private void SyncDropdownToCurrentResolution()
    {
        if (m_ResolutionDropdown == null || m_SupportedResolutions == null) return;

        var current = VitureXR.Camera.RGB.currentResolution;
        for (int i = 0; i < m_SupportedResolutions.Length; i++)
        {
            if (m_SupportedResolutions[i].x == current.x && m_SupportedResolutions[i].y == current.y)
            {
                if (m_ResolutionDropdown.value != i)
                {
                    m_ResolutionDropdown.SetValueWithoutNotify(i);
                }
                return;
            }
        }
    }

    private void UpdateResolutionDropdownState()
    {
        if (m_ResolutionDropdown == null) return;

        m_ResolutionDropdown.interactable = VitureXR.Camera.RGB.isSupported;
    }

    private void OnToggleButtonClicked()
    {
        if (VitureXR.Camera.RGB.isActive)
        {
            VitureXR.Camera.RGB.Stop();
            ClearDisplay();
        }
        else
        {
            StartCameraWithSelectedResolution();
        }
        m_LastIsActive = VitureXR.Camera.RGB.isActive;
        UpdateToggleButtonState();
    }

    private void StartCameraWithSelectedResolution()
    {
        if (m_SelectedResolution.HasValue)
            VitureXR.Camera.RGB.Start(m_SelectedResolution.Value.x, m_SelectedResolution.Value.y);
        else
            VitureXR.Camera.RGB.Start();
        Log("RGB Camera started.");
    }

    private void UpdateToggleButtonState()
    {
        if (m_ToggleButton == null) return;

        m_ToggleButton.interactable = VitureXR.Camera.RGB.isSupported;
        if (m_ToggleButtonText != null)
            m_ToggleButtonText.text = VitureXR.Camera.RGB.isActive ? "Stop Camera" : "Start Camera";
    }

    public void OnFixedDisplaySizeToggleChanged(bool isOn)
    {
        m_FixedDisplaySize = isOn;
        if (m_DisplayRawImage != null && VitureXR.Camera.RGB.isActive)
        {
            var current = VitureXR.Camera.RGB.currentResolution;
            var res = new Vector2Int(current.x, current.y);

            if (m_FixedDisplaySize)
            {
                res = VitureXR.Camera.RGB.GetDefaultResolution();
            }
            SetRawImageSizeToResolution(m_DisplayRawImage, res.x, res.y);
        }
    }

    private void ClearDisplay()
    {
        m_LastAssignedTexture = null;
        if (m_DisplayRawImage != null)
            m_DisplayRawImage.texture = null;
        if (m_DisplayRenderer != null && m_DisplayRenderer.material != null)
            m_DisplayRenderer.material.mainTexture = null;
    }

    private void Update()
    {
        if (m_UseButtonControl && m_LastIsActive != VitureXR.Camera.RGB.isActive)
        {
            m_LastIsActive = VitureXR.Camera.RGB.isActive;
            UpdateToggleButtonState();
            UpdateResolutionDropdownState();
            if (VitureXR.Camera.RGB.isActive)
                SyncDropdownToCurrentResolution();
            else
                m_LastAssignedTexture = null;
        }

        var manager = VitureRGBCameraManager.Instance;
        if (!VitureXR.Camera.RGB.isActive || manager == null)
            return;

        if (manager.CameraRenderTexture != null)
        {
            if (m_LastAssignedTexture != manager.CameraRenderTexture)
            {
                m_LastAssignedTexture = manager.CameraRenderTexture;
                if (m_DisplayRawImage != null)
                {
                    m_DisplayRawImage.texture = manager.CameraRenderTexture;

                    if (!m_FixedDisplaySize)
                    {
                        SetRawImageSizeToResolution(m_DisplayRawImage, manager.CameraRenderTexture.width, manager.CameraRenderTexture.height);
                    }
                }
                if (m_DisplayRenderer != null)
                {
                    m_DisplayRenderer.material.mainTexture = manager.CameraRenderTexture;
                }
            }
        }

        UpdateResolutionDropdownState();
        SyncDropdownToCurrentResolution();
    }

    private void OnDestroy()
    {
        if (m_ToggleButton != null)
            m_ToggleButton.onClick.RemoveListener(OnToggleButtonClicked);
        if (m_ResolutionDropdown != null)
            m_ResolutionDropdown.onValueChanged.RemoveListener(OnResolutionDropdownChanged);
        VitureXR.Camera.RGB.Stop();
    }

    private static void SetRawImageSizeToResolution(RawImage rawImage, int width, int height)
    {
        if (rawImage == null || width <= 0 || height <= 0) return;
        var rect = rawImage.rectTransform;
        rect.sizeDelta = new Vector2(width, height);
    }

    private void Log(string msg) => Debug.Log($"{k_LogTag} {msg}");
    private void LogWarning(string msg) => Debug.LogWarning($"{k_LogTag} {msg}");
    private void LogError(string msg) => Debug.LogError($"{k_LogTag} {msg}");
}
