using System;
using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using Oasis.Import;

namespace Oasis.UI
{
    [Serializable]
    public class PromptRequest
    {
        public string prompt;
    }

    [Serializable]
    public class GenerateResponse
    {
        public string job_id;
        public string status;
    }

    [Serializable]
    public class JobResponse
    {
        public string status;
        public OasisAssetManifest manifest;
        public string error_code;
    }

    [Serializable]
    public class ErrorResponse
    {
        public string error_code;
        public string message;
    }

    public class OasisGenerationFacade : MonoBehaviour
    {
        public string backendBaseUrl = "http://localhost:8000";
        private readonly string sessionId = Guid.NewGuid().ToString();
        private string activePromptId;
        private float activeFlowStartedAt;

        public sealed class GeneratedOasisAsset
        {
            public OasisAssetManifest Manifest { get; }
            public string ManifestJson { get; }
            public byte[] GlbBytes { get; }

            public GeneratedOasisAsset(OasisAssetManifest manifest, string manifestJson, byte[] glbBytes)
            {
                Manifest = manifest;
                ManifestJson = manifestJson;
                GlbBytes = glbBytes;
            }
        }

        public void StartGenerationFlow(string prompt, Action<GeneratedOasisAsset> onSuccess, Action<string> onFailure)
        {
            StartCoroutine(CoGenerateFlow(prompt, onSuccess, onFailure));
        }

        public void RecordAssetImported(string assetId)
        {
            EmitTelemetry("asset_imported", assetId: assetId);
        }

        public void RecordObjectPlaced(string assetId)
        {
            EmitTelemetry("object_placed", assetId: assetId);
        }

        private IEnumerator CoGenerateFlow(string prompt, Action<GeneratedOasisAsset> onSuccess, Action<string> onFailure)
        {
            activePromptId = Guid.NewGuid().ToString();
            activeFlowStartedAt = Time.realtimeSinceStartup;
            EmitTelemetry("prompt_submitted");

            // 1. POST /create to submit the locked prompt -> spec -> generation chain.
            string createUrl = NormalizeBaseUrl() + "/create";
            PromptRequest createReq = new PromptRequest { prompt = prompt };
            string createJson = JsonUtility.ToJson(createReq);
            string jobId = null;

            using (UnityWebRequest request = new UnityWebRequest(createUrl, "POST"))
            {
                byte[] bodyRaw = Encoding.UTF8.GetBytes(createJson);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    string errorCode = ExtractErrorCode(request);
                    EmitTelemetry("flow_failed", errorCode: errorCode);
                    onFailure?.Invoke(errorCode);
                    yield break;
                }

                GenerateResponse genRes = null;
                try
                {
                    genRes = JsonUtility.FromJson<GenerateResponse>(request.downloadHandler.text);
                }
                catch (Exception)
                {
                    // Fail to parse
                }

                if (genRes == null || string.IsNullOrEmpty(genRes.job_id))
                {
                    EmitTelemetry("flow_failed", errorCode: "provider_error");
                    onFailure?.Invoke("provider_error");
                    yield break;
                }

                jobId = genRes.job_id;
            }

            // 3. Poll GET /jobs/{job_id} until ready or failed (timeout at 90s)
            float startTime = Time.time;
            float pollInterval = 2.0f;

            while (true)
            {
                if (Time.time - startTime > 90f)
                {
                    EmitTelemetry("flow_failed", errorCode: "timeout");
                    onFailure?.Invoke("timeout");
                    yield break;
                }

                string jobUrl = NormalizeBaseUrl() + "/jobs/" + jobId;

                using (UnityWebRequest request = UnityWebRequest.Get(jobUrl))
                {
                    yield return request.SendWebRequest();

                    if (request.result != UnityWebRequest.Result.Success)
                    {
                        string errorCode = ExtractErrorCode(request);
                        EmitTelemetry("flow_failed", errorCode: errorCode);
                        onFailure?.Invoke(errorCode);
                        yield break;
                    }

                    JobResponse jobRes = null;
                    try
                    {
                        jobRes = JsonUtility.FromJson<JobResponse>(request.downloadHandler.text);
                    }
                    catch (Exception)
                    {
                        // Fail to parse
                    }

                    if (jobRes == null)
                    {
                        EmitTelemetry("flow_failed", errorCode: "provider_error");
                        onFailure?.Invoke("provider_error");
                        yield break;
                    }

                    if (jobRes.status == "ready")
                    {
                        string manifestJson = JsonUtility.ToJson(jobRes.manifest);
                        if (jobRes.manifest == null || string.IsNullOrEmpty(jobRes.manifest.asset_id) || !IsValidFetchPath(jobRes.manifest))
                        {
                            EmitTelemetry("flow_failed", errorCode: "asset_invalid");
                            onFailure?.Invoke("asset_invalid");
                        }
                        else
                        {
                            EmitTelemetry("generation_ready", provider: jobRes.manifest.provider, assetId: jobRes.manifest.asset_id);
                            yield return CoDownloadAsset(jobRes.manifest, manifestJson, onSuccess, onFailure);
                        }
                        yield break;
                    }
                    else if (jobRes.status == "failed")
                    {
                        string err = string.IsNullOrEmpty(jobRes.error_code) ? "provider_error" : jobRes.error_code;
                        EmitTelemetry("flow_failed", errorCode: err);
                        onFailure?.Invoke(err);
                        yield break;
                    }
                }

                yield return new WaitForSeconds(pollInterval);
            }
        }

        private IEnumerator CoDownloadAsset(OasisAssetManifest manifest, string manifestJson, Action<GeneratedOasisAsset> onSuccess, Action<string> onFailure)
        {
            string assetUrl = NormalizeBaseUrl() + manifest.fetch_path;
            using (UnityWebRequest request = UnityWebRequest.Get(assetUrl))
            {
                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    string errorCode = ExtractErrorCode(request);
                    EmitTelemetry("flow_failed", provider: manifest.provider, errorCode: errorCode, assetId: manifest.asset_id);
                    onFailure?.Invoke(errorCode);
                    yield break;
                }

                byte[] glbBytes = request.downloadHandler.data;
                if (glbBytes == null || glbBytes.Length == 0)
                {
                    EmitTelemetry("flow_failed", provider: manifest.provider, errorCode: "asset_invalid", assetId: manifest.asset_id);
                    onFailure?.Invoke("asset_invalid");
                    yield break;
                }

                EmitTelemetry("asset_downloaded", provider: manifest.provider, assetId: manifest.asset_id);
                onSuccess?.Invoke(new GeneratedOasisAsset(manifest, manifestJson, glbBytes));
            }
        }

        private bool IsValidFetchPath(OasisAssetManifest manifest)
        {
            return manifest != null && manifest.fetch_path == "/assets/" + manifest.asset_id;
        }

        private string NormalizeBaseUrl()
        {
            return string.IsNullOrWhiteSpace(backendBaseUrl) ? "http://localhost:8000" : backendBaseUrl.TrimEnd('/');
        }

        private void EmitTelemetry(string eventName, string provider = "", string errorCode = "", string assetId = "")
        {
            if (string.IsNullOrEmpty(activePromptId))
                activePromptId = Guid.NewGuid().ToString();

            int elapsedMs = Mathf.Max(0, Mathf.RoundToInt((Time.realtimeSinceStartup - activeFlowStartedAt) * 1000f));
            string line = "{"
                + "\"event\":\"" + EscapeJson(eventName) + "\","
                + "\"session_id\":\"" + EscapeJson(sessionId) + "\","
                + "\"prompt_id\":\"" + EscapeJson(activePromptId) + "\","
                + "\"provider\":\"" + EscapeJson(provider) + "\","
                + "\"elapsed_ms\":" + elapsedMs + ","
                + "\"error_code\":\"" + EscapeJson(errorCode) + "\","
                + "\"asset_id\":\"" + EscapeJson(assetId) + "\","
                + "\"created_at\":\"" + DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ") + "\""
                + "}\n";

            try
            {
                string path = Path.Combine(Application.persistentDataPath, "oasis_m1_telemetry.jsonl");
                File.AppendAllText(path, line, Encoding.UTF8);
            }
            catch (Exception)
            {
                // Local telemetry must never break the demo flow.
            }
        }

        private string EscapeJson(string value)
        {
            return (value ?? string.Empty).Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        private string ExtractErrorCode(UnityWebRequest request)
        {
            if (request.downloadHandler != null && !string.IsNullOrEmpty(request.downloadHandler.text))
            {
                try
                {
                    ErrorResponse errRes = JsonUtility.FromJson<ErrorResponse>(request.downloadHandler.text);
                    if (errRes != null && !string.IsNullOrEmpty(errRes.error_code))
                    {
                        return errRes.error_code;
                    }
                }
                catch
                {
                    // Ignore and fallback
                }
            }

            if (request.responseCode == 400) return "invalid_prompt";
            if (request.responseCode == 404) return "asset_not_found";
            if (request.responseCode == 422) return "asset_invalid";
            if (request.responseCode == 504) return "timeout";

            return "network_error";
        }
    }
}
