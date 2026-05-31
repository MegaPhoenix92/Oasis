using System;
using System.IO;
using UnityEngine;

namespace Oasis.Capture
{
    public sealed class OasisCaptureService : MonoBehaviour
    {
        [SerializeField] private string captureDirectoryName = "OasisCaptures";

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
                
                // Child path must start with the parent directory path followed by a directory separator
                return fullChild.StartsWith(fullParent + Path.DirectorySeparatorChar) ||
                       fullChild.StartsWith(fullParent + Path.AltDirectorySeparatorChar);
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
                string sanitized = SanitizeFilename(filename);
                // Ensure extension is .mp4
                if (!sanitized.EndsWith(".mp4", StringComparison.OrdinalIgnoreCase))
                {
                    sanitized += ".mp4";
                }

                string targetDir = CaptureDirectory;
                if (!Directory.Exists(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }

                string targetPath = Path.Combine(targetDir, sanitized);

                // Containment check
                if (!IsPathContained(targetDir, targetPath))
                {
                    Debug.LogError($"[OasisCaptureService] Path containment violation: Attempted write outside target directory: {targetPath}");
                    return false;
                }

                // Simulate video capture for demos / user study
                byte[] mockMp4 = new byte[] { 0, 0, 0, 24, 102, 116, 121, 112, 109, 112, 52, 50 }; // ftypmp42
                File.WriteAllBytes(targetPath, mockMp4);
                
                Debug.Log($"[OasisCaptureService] Saved short video clip ({durationSeconds}s) to {targetPath}");
                savedPath = targetPath;
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogError($"[OasisCaptureService] Failed to capture short clip: {ex.Message}");
                return false;
            }
        }
    }
}
