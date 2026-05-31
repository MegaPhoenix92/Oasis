using System;
using System.Collections;
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

        public void StartGenerationFlow(string prompt, Action<OasisAssetManifest> onSuccess, Action<string> onFailure)
        {
            StartCoroutine(CoGenerateFlow(prompt, onSuccess, onFailure));
        }

        private IEnumerator CoGenerateFlow(string prompt, Action<OasisAssetManifest> onSuccess, Action<string> onFailure)
        {
            // 1. POST /spec to refine the prompt into structured spec
            string specUrl = backendBaseUrl + "/spec";
            PromptRequest specReq = new PromptRequest { prompt = prompt };
            string specJson = JsonUtility.ToJson(specReq);
            string specResponseJson = null;

            using (UnityWebRequest request = new UnityWebRequest(specUrl, "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(specJson);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    string errorCode = ExtractErrorCode(request);
                    onFailure?.Invoke(errorCode);
                    yield break;
                }

                specResponseJson = request.downloadHandler.text;
            }

            // 2. POST /generate to submit the generation job
            string generateUrl = backendBaseUrl + "/generate";
            string jobId = null;

            using (UnityWebRequest request = new UnityWebRequest(generateUrl, "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(specResponseJson);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    string errorCode = ExtractErrorCode(request);
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
                    onFailure?.Invoke("timeout");
                    yield break;
                }

                string jobUrl = backendBaseUrl + "/jobs/" + jobId;

                using (UnityWebRequest request = UnityWebRequest.Get(jobUrl))
                {
                    yield return request.SendWebRequest();

                    if (request.result != UnityWebRequest.Result.Success)
                    {
                        string errorCode = ExtractErrorCode(request);
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
                        onFailure?.Invoke("provider_error");
                        yield break;
                    }

                    if (jobRes.status == "ready")
                    {
                        if (jobRes.manifest == null || string.IsNullOrEmpty(jobRes.manifest.asset_id))
                        {
                            onFailure?.Invoke("asset_invalid");
                        }
                        else
                        {
                            onSuccess?.Invoke(jobRes.manifest);
                        }
                        yield break;
                    }
                    else if (jobRes.status == "failed")
                    {
                        string err = string.IsNullOrEmpty(jobRes.error_code) ? "provider_error" : jobRes.error_code;
                        onFailure?.Invoke(err);
                        yield break;
                    }
                }

                yield return new WaitForSeconds(pollInterval);
            }
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
