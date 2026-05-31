using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace Oasis.Capture
{
    public sealed class OasisCaptureService : MonoBehaviour
    {
        [SerializeField] private string captureDirectoryName = "OasisCaptures";
        [SerializeField] private int shortClipFps = 8;
        [SerializeField] private float maxShortClipDurationSeconds = 10f;

        private const string ShortClipDirectoryName = "short_clips";
        private const string ShortClipFramesDirectoryName = "frames";
        private const string ShortClipManifestName = "manifest.json";
        private static readonly char[] PortableInvalidFileNameChars = { '<', '>', ':', '"', '/', '\\', '|', '?', '*', '\0' };

        public string CaptureDirectory
        {
            get
            {
                string basePath = string.IsNullOrWhiteSpace(Application.persistentDataPath) ? "." : Application.persistentDataPath;
                return Path.GetFullPath(Path.Combine(basePath, captureDirectoryName));
            }
        }

        public string SanitizeFilename(string filename)
        {
            if (string.IsNullOrEmpty(filename))
            {
                return "capture_" + DateTime.Now.ToString("yyyyMMdd_HHmmss");
            }

            // Remove path navigation / directory separators
            string clean = Path.GetFileName(filename);
            
            // Strip out invalid characters
            foreach (char c in Path.GetInvalidFileNameChars())
            {
                clean = clean.Replace(c, '_');
            }
            foreach (char c in PortableInvalidFileNameChars)
            {
                clean = clean.Replace(c, '_');
            }
            
            // Extra safety to prevent relative path sequences or path traversal
            clean = clean.Replace("/", "_")
                         .Replace("\\", "_")
                         .Replace("..", "_")
                         .Replace(":", "_");

            if (string.IsNullOrWhiteSpace(clean))
            {
                clean = "capture_" + DateTime.Now.ToString("yyyyMMdd_HHmmss");
            }

            return clean;
        }

        public bool IsPathContained(string parentDir, string childPath)
        {
            try
            {
                string fullParent = Path.GetFullPath(parentDir).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                string fullChild = Path.GetFullPath(childPath);
                StringComparison comparison = Path.DirectorySeparatorChar == '\\'
                    ? StringComparison.OrdinalIgnoreCase
                    : StringComparison.Ordinal;
                
                // Child path must start with the parent directory path followed by a directory separator
                return fullChild.StartsWith(fullParent + Path.DirectorySeparatorChar, comparison) ||
                       fullChild.StartsWith(fullParent + Path.AltDirectorySeparatorChar, comparison);
            }
            catch
            {
                return false;
            }
        }

        public bool CaptureScreenshot(string filename, out string savedPath)
        {
            savedPath = null;
            try
            {
                string sanitized = SanitizeFilename(filename);
                // Ensure extension is .png
                if (!sanitized.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
                {
                    sanitized += ".png";
                }

                string targetDir = CaptureDirectory;
                if (!Directory.Exists(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }

                string targetPath = Path.Combine(targetDir, sanitized);

                // Containment / path traversal verification
                if (!IsPathContained(targetDir, targetPath))
                {
                    Debug.LogError($"[OasisCaptureService] Path containment violation: Attempted write outside target directory: {targetPath}");
                    return false;
                }

                // Write screenshot file
                if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null)
                {
                    // Headless / mock mode: write a dummy file
                    File.WriteAllBytes(targetPath, new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }); // Dummy PNG header
                    Debug.Log($"[OasisCaptureService] Headless mode: saved mock screenshot to {targetPath}");
                }
                else
                {
                    ScreenCapture.CaptureScreenshot(targetPath);
                    Debug.Log($"[OasisCaptureService] Saved screenshot to {targetPath}");
                }

                savedPath = targetPath;
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogError($"[OasisCaptureService] Failed to capture screenshot: {ex.Message}");
                return false;
            }
        }

        public bool CaptureShortClip(string filename, float durationSeconds, out string savedPath)
        {
            savedPath = null;
            try
            {
                string targetDir = CaptureDirectory;
                if (!Directory.Exists(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }

                string clipName = SanitizeClipDirectoryName(filename);
                string clipsDir = Path.Combine(targetDir, ShortClipDirectoryName);

                if (!IsPathContained(targetDir, clipsDir))
                {
                    Debug.LogError($"[OasisCaptureService] Path containment violation: Attempted write outside target directory: {clipsDir}");
                    return false;
                }

                Directory.CreateDirectory(clipsDir);

                string clipDir = CreateUniqueClipDirectory(clipsDir, clipName);
                string framesDir = Path.Combine(clipDir, ShortClipFramesDirectoryName);
                string manifestPath = Path.Combine(clipDir, ShortClipManifestName);

                if (!IsPathContained(clipsDir, clipDir) ||
                    !IsPathContained(clipDir, framesDir) ||
                    !IsPathContained(clipDir, manifestPath))
                {
                    Debug.LogError($"[OasisCaptureService] Path containment violation: Attempted write outside clip directory: {clipDir}");
                    return false;
                }

                Directory.CreateDirectory(framesDir);

                float clampedDuration = Mathf.Clamp(durationSeconds <= 0f ? 1f : durationSeconds, 0.1f, maxShortClipDurationSeconds);
                int clampedFps = Mathf.Clamp(shortClipFps, 1, 30);

                WriteClipManifest(
                    manifestPath,
                    clipName,
                    clampedDuration,
                    clampedFps,
                    Array.Empty<string>(),
                    SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null ? "headless_pending" : "capturing");

                if (SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null || !isActiveAndEnabled)
                {
                    CaptureFrameSequenceNow(clipName, framesDir, manifestPath, clampedDuration, clampedFps, "headless_frame_sequence");
                }
                else
                {
                    StartCoroutine(CaptureFrameSequenceCoroutine(clipName, framesDir, manifestPath, clampedDuration, clampedFps));
                }

                Debug.Log($"[OasisCaptureService] Started short clip frame capture ({clampedDuration}s at {clampedFps} FPS) in {clipDir}");
                savedPath = manifestPath;
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogError($"[OasisCaptureService] Failed to capture short clip: {ex.Message}");
                return false;
            }
        }

        public string SanitizeClipDirectoryName(string filename)
        {
            string sanitized = SanitizeFilename(filename);
            string withoutExtension = Path.GetFileNameWithoutExtension(sanitized);
            if (string.IsNullOrWhiteSpace(withoutExtension))
            {
                withoutExtension = "clip_" + DateTime.Now.ToString("yyyyMMdd_HHmmss");
            }

            return SanitizePathSegment(withoutExtension);
        }

        private string CreateUniqueClipDirectory(string parentDir, string clipName)
        {
            string uniqueName = clipName;
            string clipDir = Path.Combine(parentDir, uniqueName);
            int suffix = 1;

            while (Directory.Exists(clipDir))
            {
                uniqueName = clipName + "_" + suffix.ToString("D2");
                clipDir = Path.Combine(parentDir, uniqueName);
                suffix++;
            }

            if (!IsPathContained(parentDir, clipDir))
            {
                throw new InvalidOperationException("Short clip directory is outside the capture root.");
            }

            Directory.CreateDirectory(clipDir);
            return clipDir;
        }

        private IEnumerator CaptureFrameSequenceCoroutine(string clipName, string framesDir, string manifestPath, float durationSeconds, int fps)
        {
            int frameCount = Mathf.Max(1, Mathf.CeilToInt(durationSeconds * fps));
            float frameIntervalSeconds = 1f / fps;
            List<string> frameFiles = new List<string>(frameCount);

            for (int frameIndex = 0; frameIndex < frameCount; frameIndex++)
            {
                yield return new WaitForEndOfFrame();
                string relativeFramePath = CaptureSingleFrame(framesDir, frameIndex, false);
                frameFiles.Add(relativeFramePath);

                if (frameIndex < frameCount - 1)
                {
                    yield return new WaitForSeconds(frameIntervalSeconds);
                }
            }

            WriteClipManifest(manifestPath, clipName, durationSeconds, fps, frameFiles.ToArray(), "complete");
            Debug.Log($"[OasisCaptureService] Saved short clip frame sequence to {manifestPath}");
        }

        private void CaptureFrameSequenceNow(string clipName, string framesDir, string manifestPath, float durationSeconds, int fps, string mode)
        {
            int frameCount = Mathf.Max(1, Mathf.CeilToInt(durationSeconds * fps));
            List<string> frameFiles = new List<string>(frameCount);

            for (int frameIndex = 0; frameIndex < frameCount; frameIndex++)
            {
                frameFiles.Add(CaptureSingleFrame(framesDir, frameIndex, true));
            }

            WriteClipManifest(manifestPath, clipName, durationSeconds, fps, frameFiles.ToArray(), mode);
        }

        private string CaptureSingleFrame(string framesDir, int frameIndex, bool allowGeneratedFrame)
        {
            string frameName = "frame_" + frameIndex.ToString("D4") + ".png";
            string framePath = Path.Combine(framesDir, frameName);

            if (!IsPathContained(framesDir, framePath))
            {
                throw new InvalidOperationException("Short clip frame path is outside the frames directory.");
            }

            Texture2D texture = null;
            try
            {
                if (SystemInfo.graphicsDeviceType != GraphicsDeviceType.Null)
                {
                    texture = ScreenCapture.CaptureScreenshotAsTexture();
                }

                if (texture == null && allowGeneratedFrame)
                {
                    texture = CreateGeneratedFrame(frameIndex);
                }

                if (texture == null)
                {
                    throw new InvalidOperationException("Unable to capture a scene frame.");
                }

                File.WriteAllBytes(framePath, texture.EncodeToPNG());
            }
            finally
            {
                if (texture != null)
                {
                    if (Application.isPlaying)
                    {
                        Destroy(texture);
                    }
                    else
                    {
                        DestroyImmediate(texture);
                    }
                }
            }

            return Path.Combine(ShortClipFramesDirectoryName, frameName).Replace("\\", "/");
        }

        private static Texture2D CreateGeneratedFrame(int frameIndex)
        {
            Texture2D texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            byte shade = (byte)(32 + ((frameIndex * 37) % 180));
            Color32 color = new Color32(shade, (byte)(255 - shade), (byte)(80 + (frameIndex % 120)), 255);
            texture.SetPixels32(new[] { color, color, color, color });
            texture.Apply(false);
            return texture;
        }

        private void WriteClipManifest(string manifestPath, string clipName, float durationSeconds, int fps, string[] frameFiles, string status)
        {
            if (!IsPathContained(Path.GetDirectoryName(manifestPath), manifestPath))
            {
                throw new InvalidOperationException("Short clip manifest path is outside the clip directory.");
            }

            string manifestJson = JsonUtility.ToJson(
                new ShortClipManifest
                {
                    clip_name = clipName,
                    duration_seconds = durationSeconds,
                    fps = fps,
                    frame_count = frameFiles.Length,
                    frames = frameFiles,
                    status = status
                },
                true);

            File.WriteAllText(manifestPath, manifestJson);
        }

        private string SanitizePathSegment(string segment)
        {
            string clean = segment.Trim();
            foreach (char c in Path.GetInvalidFileNameChars())
            {
                clean = clean.Replace(c, '_');
            }
            foreach (char c in PortableInvalidFileNameChars)
            {
                clean = clean.Replace(c, '_');
            }

            clean = clean.Replace("/", "_")
                         .Replace("\\", "_")
                         .Replace("..", "_")
                         .Replace(":", "_");

            if (string.IsNullOrWhiteSpace(clean) || clean == "." || clean == "..")
            {
                clean = "clip_" + DateTime.Now.ToString("yyyyMMdd_HHmmss");
            }

            return clean;
        }

        [Serializable]
        private sealed class ShortClipManifest
        {
            public string clip_name;
            public float duration_seconds;
            public int fps;
            public int frame_count;
            public string[] frames;
            public string status;
        }
    }
}
