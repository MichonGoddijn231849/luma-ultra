using System;
using System.Collections;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Rendering;

namespace Viture.XR
{
    /// <summary>
    /// VITURE RGB Camera Manager. Add to a GameObject in the scene. Use <see cref="VitureXR.Camera.RGB"/> for Start/Stop;
    /// access via <see cref="Instance"/> for <see cref="CameraRenderTexture"/>, <see cref="CaptureFrameAsync"/>, <see cref="ReadPixelsAsync"/>.
    /// </summary>
    [DisallowMultipleComponent]
    public class VitureRGBCameraManager : MonoBehaviour
    {
        #region Public API

        /// <summary>Singleton instance. Null if no Manager in scene. Add VitureRGBCameraManager to a GameObject first.</summary>
        public static VitureRGBCameraManager Instance => s_Instance;

        /// <summary>RenderTexture with the camera image. Null when inactive. Assign to RawImage, Renderer, etc.</summary>
        public RenderTexture CameraRenderTexture => m_CameraRenderTexture;

        /// <summary>When true, starts the RGB camera automatically on enable so the feed displays without a button. Default false.</summary>
        public bool StartCameraOnEnable { get => m_StartCameraOnEnable; set => m_StartCameraOnEnable = value; }

        /// <summary>Captures the current frame as Texture2D. Returns null if inactive.</summary>
        public Task<Texture2D> CaptureFrameAsync(CancellationToken cancellationToken = default)
        {
            if (!VitureXR.Camera.RGB.isActive || m_CameraRenderTexture == null || m_IsDisposed)
                return Task.FromResult<Texture2D>(null);

            var tcs = new TaskCompletionSource<Texture2D>();
            StartCoroutine(CaptureFrameCoroutine(tcs, cancellationToken));
            return tcs.Task;
        }

        /// <summary>Reads the current frame pixels as Color32 array. Returns null if inactive.</summary>
        public Task<Color32[]> ReadPixelsAsync(CancellationToken cancellationToken = default)
        {
            if (!VitureXR.Camera.RGB.isActive || m_CameraRenderTexture == null || m_IsDisposed)
                return Task.FromResult<Color32[]>(null);

            var tcs = new TaskCompletionSource<Color32[]>();
            StartCoroutine(ReadPixelsCoroutine(tcs, cancellationToken));
            return tcs.Task;
        }

        #endregion

        #region Constants

        private const int k_CameraInitWaitFrames = 5;
        private const string k_OESBlitShader = "Hidden/VitureXR/OESBlit";

        #endregion

        #region Private Fields

        internal static VitureRGBCameraManager s_Instance;
        private Texture2D m_CameraTexture;
        private RenderTexture m_CameraRenderTexture;
        private Material m_BlitMaterial;
        private int m_NativeTextureId;
        private bool m_IsInitialized;
        private bool m_CameraAcquired;
        private int m_RemainingWaitFrames;
        private bool m_IsDisposed;
        private bool m_HasNewFrame;

        [SerializeField]
        [Tooltip("When true, starts the RGB camera automatically on enable so the feed displays without a button.")]
        private bool m_StartCameraOnEnable;

        #endregion

        #region Unity Lifecycle

        private void OnEnable()
        {
            if (s_Instance != null && s_Instance != this)
            {
                Debug.LogWarning("[VitureXR] Multiple VitureRGBCameraManager instances. Only the first will be used.");
                return;
            }
            VitureXR.Camera.RGB.frameAvailable += OnCameraFrameAvailable;
            s_Instance = this;

            if (m_StartCameraOnEnable && VitureXR.Camera.RGB.isSupported && !VitureXR.Camera.RGB.isActive)
                VitureXR.Camera.RGB.Start();
        }

        private void OnDisable()
        {
            if (s_Instance == this)
                s_Instance = null;
            VitureXR.Camera.RGB.frameAvailable -= OnCameraFrameAvailable;
            ReleaseResources();
        }

        private void OnDestroy() => ReleaseResources();

        private void Update()
        {
            if (m_IsDisposed || !VitureXR.Camera.RGB.isSupported) return;
            if (!VitureXR.Camera.RGB.isActive)
            {
                if (m_CameraAcquired) { CleanupTextures(); m_CameraAcquired = false; m_NativeTextureId = 0; m_RemainingWaitFrames = k_CameraInitWaitFrames; }
                return;
            }
            UpdateCameraState();
        }

        private void OnApplicationPause(bool pauseStatus)
        {
            if (pauseStatus && VitureXR.Camera.RGB.isActive)
                VitureXR.Camera.RGB.Stop();
        }

        private void OnApplicationQuit() => ReleaseResources();

        #endregion

        #region Private Methods

        private void OnCameraFrameAvailable(long value) => m_HasNewFrame = true;

        /// <summary>Releases camera resources and stops the camera. Called automatically on disable/destroy.</summary>
        private void ReleaseResources()
        {
            if (m_IsDisposed) return;
            CleanupTextures();
            if (VitureXR.Camera.RGB.isActive)
                VitureXR.Camera.RGB.Stop();
            m_IsDisposed = true;
            if (s_Instance == this)
                s_Instance = null;
        }

        private bool InitializeTextures()
        {
            if (m_IsInitialized || m_NativeTextureId <= 0) return m_IsInitialized;

            var res = VitureXR.Camera.RGB.currentResolution;
            int w = res.x;
            int h = res.y;

            try
            {
                m_CameraTexture = Texture2D.CreateExternalTexture(
                    w, h, TextureFormat.RGBA32,
                    false, false, new IntPtr(m_NativeTextureId));
                m_CameraTexture.filterMode = FilterMode.Bilinear;
                m_CameraTexture.wrapMode = TextureWrapMode.Clamp;

                m_CameraRenderTexture = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32)
                {
                    filterMode = FilterMode.Bilinear,
                    wrapMode = TextureWrapMode.Clamp,
                    antiAliasing = 1
                };
                m_CameraRenderTexture.Create();

                Shader shader = Shader.Find(k_OESBlitShader) ?? Shader.Find("Unlit/Texture");
                m_BlitMaterial = shader != null ? new Material(shader) { hideFlags = HideFlags.DontSaveInBuild | HideFlags.DontSaveInEditor } : null;

                m_IsInitialized = true;
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogError($"[VitureXR] RGBCamera texture init failed: {ex.Message}");
                CleanupTextures();
                return false;
            }
        }

        private void CleanupTextures()
        {
            if (m_CameraRenderTexture != null) { m_CameraRenderTexture.Release(); DestroyImmediate(m_CameraRenderTexture); }
            if (m_CameraTexture != null) DestroyImmediate(m_CameraTexture);
            if (m_BlitMaterial != null) DestroyImmediate(m_BlitMaterial);

            m_CameraRenderTexture = null;
            m_CameraTexture = null;
            m_BlitMaterial = null;
            m_IsInitialized = false;
        }

        private void CleanupAndStop()
        {
            CleanupTextures();
            m_CameraAcquired = false;
            m_NativeTextureId = 0;
            if (VitureXR.Camera.RGB.isActive)
                VitureXR.Camera.RGB.Stop();
        }

        private void UpdateCameraState()
        {
            if (!m_CameraAcquired)
            {
                if (m_RemainingWaitFrames > 0) { m_RemainingWaitFrames--; return; }

                m_NativeTextureId = VitureXR.Camera.RGB.GetNativeTextureId();
                if (m_NativeTextureId <= 0) { CleanupAndStop(); return; }

                if (!InitializeTextures()) { CleanupAndStop(); return; }
                m_CameraAcquired = true;
            }
            else
            {
                var currentRes = VitureXR.Camera.RGB.currentResolution;
                if (m_CameraRenderTexture != null &&
                    (currentRes.x != m_CameraRenderTexture.width || currentRes.y != m_CameraRenderTexture.height))
                {
                    CleanupTextures();
                    m_CameraAcquired = false;
                    m_NativeTextureId = 0;
                    m_RemainingWaitFrames = 1;
                    return;
                }
                if (m_HasNewFrame)
                {
                    m_HasNewFrame = false;

                    if (m_CameraTexture != null && m_CameraRenderTexture != null && m_BlitMaterial != null)
                    {
                        Graphics.Blit(m_CameraTexture, m_CameraRenderTexture, m_BlitMaterial);
                    }
                }
            }
        }

        private IEnumerator CaptureFrameCoroutine(TaskCompletionSource<Texture2D> tcs, CancellationToken cancellationToken)
        {
            using var registration = cancellationToken.Register(() => tcs.TrySetCanceled());

            yield return new WaitForEndOfFrame();
            if (m_CameraRenderTexture == null || m_IsDisposed) { tcs.TrySetResult(null); yield break; }

            var request = AsyncGPUReadback.Request(m_CameraRenderTexture);
            while (!request.done && !m_IsDisposed) yield return null;

            if (m_IsDisposed || request.hasError) { tcs.TrySetResult(null); yield break; }

            var texture = new Texture2D(m_CameraRenderTexture.width, m_CameraRenderTexture.height, TextureFormat.RGBA32, false);
            texture.SetPixelData(request.GetData<Color32>(), 0);
            texture.Apply();
            tcs.TrySetResult(texture);
        }

        private IEnumerator ReadPixelsCoroutine(TaskCompletionSource<Color32[]> tcs, CancellationToken cancellationToken)
        {
            using var registration = cancellationToken.Register(() => tcs.TrySetCanceled());

            yield return new WaitForEndOfFrame();
            if (m_CameraRenderTexture == null || m_IsDisposed) { tcs.TrySetResult(null); yield break; }

            var request = AsyncGPUReadback.Request(m_CameraRenderTexture);
            while (!request.done && !m_IsDisposed) yield return null;

            if (m_IsDisposed || request.hasError) { tcs.TrySetResult(null); yield break; }
            tcs.TrySetResult(request.GetData<Color32>().ToArray());
        }

        #endregion
    }
}