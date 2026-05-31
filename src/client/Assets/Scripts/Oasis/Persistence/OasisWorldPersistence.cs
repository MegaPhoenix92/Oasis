using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Oasis.Import;
using UnityEngine;
using UnityEngine.Networking;

namespace Oasis.Persistence
{
    public enum OasisWorldPersistenceErrorCode
    {
        None,
        InvalidWorldId,
        InvalidAssetId,
        InvalidWorldDocument,
        DuplicateInstanceId,
        AssetFetchFailed,
        AssetMissing,
        AssetChecksumMismatch,
        AssetInvalid,
        FilesystemError,
        ImportFailed
    }

    public readonly struct OasisWorldPersistenceFailure
    {
        public static readonly OasisWorldPersistenceFailure None = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.None, string.Empty);

        public OasisWorldPersistenceErrorCode Code { get; }
        public string Message { get; }
        public string InstanceId { get; }
        public string AssetId { get; }

        public OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode code, string message, string instanceId = "", string assetId = "")
        {
            Code = code;
            Message = message;
            InstanceId = instanceId ?? string.Empty;
            AssetId = assetId ?? string.Empty;
        }

        public bool IsFailure => Code != OasisWorldPersistenceErrorCode.None;
    }

    public sealed class OasisWorldSkippedObject
    {
        public string instance_id;
        public string asset_id;
        public OasisWorldPersistenceErrorCode reason;
        public string message;
    }

    public sealed class OasisWorldLoadResult
    {
        public OasisWorldDocument Document { get; internal set; }
        public List<GameObject> ImportedObjects { get; } = new List<GameObject>();
        public List<OasisWorldSkippedObject> SkippedObjects { get; } = new List<OasisWorldSkippedObject>();
        public Dictionary<string, string> ManifestJsonByAssetId { get; } = new Dictionary<string, string>();
        public OasisWorldPersistenceFailure Failure { get; internal set; } = OasisWorldPersistenceFailure.None;
        public bool Success => !Failure.IsFailure;
    }

    public interface IOasisAssetFetcher
    {
        Task<byte[]> FetchAssetAsync(OasisAssetManifest manifest, CancellationToken cancellationToken);
    }

    public sealed class OasisHttpAssetFetcher : IOasisAssetFetcher
    {
        private readonly string backendBaseUrl;

        public OasisHttpAssetFetcher(string backendBaseUrl)
        {
            this.backendBaseUrl = string.IsNullOrWhiteSpace(backendBaseUrl) ? "http://localhost:8000" : backendBaseUrl.TrimEnd('/');
        }

        public async Task<byte[]> FetchAssetAsync(OasisAssetManifest manifest, CancellationToken cancellationToken)
        {
            if (manifest == null || string.IsNullOrWhiteSpace(manifest.fetch_path) || manifest.fetch_path != "/assets/" + manifest.asset_id)
                return null;

            using UnityWebRequest request = UnityWebRequest.Get(backendBaseUrl + manifest.fetch_path);
            UnityWebRequestAsyncOperation operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    request.Abort();
                    cancellationToken.ThrowIfCancellationRequested();
                }

                await Task.Yield();
            }

            return request.result == UnityWebRequest.Result.Success ? request.downloadHandler.data : null;
        }
    }

    public sealed class OasisWorldPersistence : MonoBehaviour
    {
        private const string WorldFileName = "world.json";
        private const string ManifestsDirectoryName = "manifests";
        private const string AssetsDirectoryName = "assets";

        [SerializeField] private string worldsDirectoryName = "OasisWorlds";

        public string WorldsRootPath
        {
            get
            {
                string basePath = string.IsNullOrWhiteSpace(Application.persistentDataPath) ? "." : Application.persistentDataPath;
                return Path.GetFullPath(Path.Combine(basePath, worldsDirectoryName));
            }
        }

        public async Task<OasisWorldPersistenceFailure> SaveAsync(
            OasisWorldDocument document,
            IReadOnlyDictionary<string, string> manifestJsonByAssetId,
            IOasisAssetFetcher assetFetcher,
            CancellationToken cancellationToken = default)
        {
            if (!TryValidateWorldDocument(document, out OasisWorldPersistenceFailure failure))
                return failure;
            if (manifestJsonByAssetId == null || assetFetcher == null)
                return new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.AssetMissing, "Save requires manifests and a client asset fetcher.");
            if (!TryResolveWorldDirectory(document.world_id, out string worldDirectory, out failure))
                return failure;

            string root = WorldsRootPath;
            string tempDirectory = Path.Combine(root, document.world_id + ".tmp-" + Guid.NewGuid().ToString("N"));
            string backupDirectory = Path.Combine(root, document.world_id + ".bak-" + Guid.NewGuid().ToString("N"));
            bool finalMovedToBackup = false;

            try
            {
                Directory.CreateDirectory(Path.Combine(tempDirectory, ManifestsDirectoryName));
                Directory.CreateDirectory(Path.Combine(tempDirectory, AssetsDirectoryName));
                await WriteAllTextAsync(Path.Combine(tempDirectory, WorldFileName), SerializeWorldDocument(document), cancellationToken);

                foreach (string assetId in GetReferencedAssetIds(document))
                {
                    if (!manifestJsonByAssetId.TryGetValue(assetId, out string manifestJson) ||
                        !OasisAssetManifestValidator.TryParseAndValidate(manifestJson, out OasisAssetManifest manifest, out OasisImportFailure importFailure) ||
                        manifest.asset_id != assetId ||
                        manifest.fetch_path != "/assets/" + assetId)
                    {
                        return CleanupTempAndFail(tempDirectory, new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.AssetInvalid, "Referenced asset manifest is invalid.", assetId: assetId));
                    }

                    byte[] glbBytes = await assetFetcher.FetchAssetAsync(manifest, cancellationToken);
                    if (glbBytes == null)
                    {
                        return CleanupTempAndFail(tempDirectory, new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.AssetFetchFailed, "Referenced GLB could not be fetched.", assetId: assetId));
                    }
                    if (!OasisAssetManifestValidator.ValidateAssetBytes(glbBytes, manifest, out importFailure))
                    {
                        return CleanupTempAndFail(tempDirectory, new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.AssetInvalid, importFailure.Message, assetId: assetId));
                    }
                    if (!ValidateChecksum(glbBytes, manifest, out failure))
                    {
                        return CleanupTempAndFail(tempDirectory, failure);
                    }

                    await WriteAllTextAsync(Path.Combine(tempDirectory, ManifestsDirectoryName, assetId + ".json"), manifestJson, cancellationToken);
                    await WriteAllBytesAsync(Path.Combine(tempDirectory, AssetsDirectoryName, assetId + ".glb"), glbBytes, cancellationToken);
                }

                if (Directory.Exists(worldDirectory))
                {
                    Directory.Move(worldDirectory, backupDirectory);
                    finalMovedToBackup = true;
                }

                Directory.Move(tempDirectory, worldDirectory);
                if (finalMovedToBackup)
                    Directory.Delete(backupDirectory, true);

                return OasisWorldPersistenceFailure.None;
            }
            catch (Exception)
            {
                TryDeleteDirectory(tempDirectory);
                if (finalMovedToBackup && !Directory.Exists(worldDirectory) && Directory.Exists(backupDirectory))
                {
                    try
                    {
                        Directory.Move(backupDirectory, worldDirectory);
                    }
                    catch (Exception)
                    {
                        // Preserve the typed failure if rollback itself cannot complete.
                    }
                }
                return new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.FilesystemError, "World save failed without committing a partial directory.");
            }
        }

        public async Task<OasisWorldLoadResult> LoadAsync(string worldId, OasisGlbImporter importer, CancellationToken cancellationToken = default)
        {
            OasisWorldLoadResult result = new OasisWorldLoadResult();
            if (!TryResolveWorldDirectory(worldId, out string worldDirectory, out OasisWorldPersistenceFailure failure))
            {
                result.Failure = failure;
                return result;
            }

            string worldJsonPath = Path.Combine(worldDirectory, WorldFileName);
            try
            {
                if (!File.Exists(worldJsonPath))
                {
                    result.Failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldDocument, "Saved world.json was not found.");
                    return result;
                }

                string worldJson = await ReadAllTextAsync(worldJsonPath, cancellationToken);
                if (!TryParseWorldDocument(worldJson, out OasisWorldDocument document, out failure) || document.world_id != worldId)
                {
                    result.Failure = failure.IsFailure ? failure : new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldDocument, "Saved world.json is invalid.");
                    return result;
                }

                result.Document = document;

                foreach (OasisWorldObject worldObject in document.objects)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (!TryLoadAssetForObject(worldDirectory, worldObject, out string manifestJson, out byte[] glbBytes, out OasisWorldPersistenceFailure skipped))
                    {
                        AddSkipped(result, worldObject, skipped);
                        continue;
                    }

                    result.ManifestJsonByAssetId[worldObject.asset_id] = manifestJson;

                    if (importer == null)
                        continue;

                    GameObject imported = await importer.ImportFromBytesAsync(glbBytes, manifestJson, Vector3.zero, cancellationToken: cancellationToken);
                    if (imported == null)
                    {
                        AddSkipped(result, worldObject, new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.ImportFailed, "Saved asset import failed.", worldObject.instance_id, worldObject.asset_id));
                        continue;
                    }

                    ApplyTransform(imported.transform, worldObject.transform);
                    result.ImportedObjects.Add(imported);
                }
            }
            catch (Exception)
            {
                result.Failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.FilesystemError, "Saved world could not be loaded.");
            }

            return result;
        }

        public static string SerializeWorldDocument(OasisWorldDocument document)
        {
            string sceneSettings = IsJsonObject(document.scene_settings_json) ? document.scene_settings_json : "{}";
            StringBuilder builder = new StringBuilder();
            builder.Append("{\n");
            AppendJsonProperty(builder, "schema_version", document.schema_version, true);
            AppendJsonProperty(builder, "world_id", document.world_id, true);
            AppendJsonProperty(builder, "name", document.name, true);
            AppendJsonProperty(builder, "created_at", document.created_at, true);
            AppendJsonProperty(builder, "updated_at", document.updated_at, true);
            builder.Append("  \"scene_settings\": ").Append(sceneSettings).Append(",\n");
            builder.Append("  \"objects\": [");
            OasisWorldObject[] objects = document.objects ?? Array.Empty<OasisWorldObject>();
            for (int index = 0; index < objects.Length; index++)
            {
                OasisWorldObject worldObject = objects[index];
                if (index > 0)
                    builder.Append(",");
                builder.Append("\n    {\n");
                AppendJsonProperty(builder, "instance_id", worldObject.instance_id, true, 6);
                AppendJsonProperty(builder, "asset_id", worldObject.asset_id, true, 6);
                builder.Append("      \"transform\": {\n");
                AppendVector(builder, "position", worldObject.transform.position, true, 8);
                AppendQuaternion(builder, "rotation", worldObject.transform.rotation, true, 8);
                AppendVector(builder, "scale", worldObject.transform.scale, false, 8);
                builder.Append("      },\n");
                AppendJsonProperty(builder, "created_at", worldObject.created_at, false, 6);
                builder.Append("\n    }");
            }
            builder.Append("\n  ]\n}");
            return builder.ToString();
        }

        public static bool TryParseWorldDocument(string worldJson, out OasisWorldDocument document, out OasisWorldPersistenceFailure failure)
        {
            document = null;
            failure = OasisWorldPersistenceFailure.None;

            if (string.IsNullOrWhiteSpace(worldJson) || !TryExtractTopLevelObject(worldJson, "scene_settings", out string sceneSettings))
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldDocument, "world.json is malformed or missing scene_settings.");
                return false;
            }

            try
            {
                document = JsonUtility.FromJson<OasisWorldDocument>(worldJson);
                if (document != null)
                    document.scene_settings_json = sceneSettings;
            }
            catch (Exception)
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldDocument, "world.json is malformed.");
                return false;
            }

            return TryValidateWorldDocument(document, out failure);
        }

        public static bool TryValidateWorldDocument(OasisWorldDocument document, out OasisWorldPersistenceFailure failure)
        {
            failure = OasisWorldPersistenceFailure.None;
            if (document == null || document.schema_version != "1.0" || !IsUuid(document.world_id) || string.IsNullOrWhiteSpace(document.name) ||
                !IsTimestamp(document.created_at) || !IsTimestamp(document.updated_at) || !IsJsonObject(document.scene_settings_json))
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldDocument, "World document failed schema validation.");
                return false;
            }
            if (document.objects == null)
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldDocument, "World document must include objects.");
                return false;
            }

            HashSet<string> instances = new HashSet<string>();
            foreach (OasisWorldObject worldObject in document.objects)
            {
                if (worldObject == null || !IsUuid(worldObject.instance_id) || !IsUuid(worldObject.asset_id) || !IsTimestamp(worldObject.created_at) || worldObject.transform == null ||
                    worldObject.transform.position == null || worldObject.transform.rotation == null || worldObject.transform.scale == null)
                {
                    failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldDocument, "World object failed schema validation.");
                    return false;
                }

                if (!instances.Add(worldObject.instance_id))
                {
                    failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.DuplicateInstanceId, "World document contains duplicate instance_id values.", worldObject.instance_id, worldObject.asset_id);
                    return false;
                }
            }

            return true;
        }

        private bool TryLoadAssetForObject(string worldDirectory, OasisWorldObject worldObject, out string manifestJson, out byte[] glbBytes, out OasisWorldPersistenceFailure failure)
        {
            manifestJson = null;
            glbBytes = null;
            failure = OasisWorldPersistenceFailure.None;

            if (!IsUuid(worldObject.asset_id))
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidAssetId, "Saved object asset_id is not a UUID.", worldObject.instance_id, worldObject.asset_id);
                return false;
            }

            string manifestPath = Path.Combine(worldDirectory, ManifestsDirectoryName, worldObject.asset_id + ".json");
            string assetPath = Path.Combine(worldDirectory, AssetsDirectoryName, worldObject.asset_id + ".glb");
            if (!IsWithinDirectory(worldDirectory, manifestPath) || !IsWithinDirectory(worldDirectory, assetPath))
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidAssetId, "Saved asset path was rejected.", worldObject.instance_id, worldObject.asset_id);
                return false;
            }

            if (!File.Exists(manifestPath) || !File.Exists(assetPath))
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.AssetMissing, "Saved asset manifest or GLB is missing.", worldObject.instance_id, worldObject.asset_id);
                return false;
            }

            manifestJson = File.ReadAllText(manifestPath, Encoding.UTF8);
            if (!OasisAssetManifestValidator.TryParseAndValidate(manifestJson, out OasisAssetManifest manifest, out _) || manifest.asset_id != worldObject.asset_id)
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.AssetInvalid, "Saved asset manifest is invalid.", worldObject.instance_id, worldObject.asset_id);
                return false;
            }

            glbBytes = File.ReadAllBytes(assetPath);
            if (!OasisAssetManifestValidator.ValidateAssetBytes(glbBytes, manifest, out _) || !ValidateChecksum(glbBytes, manifest, out failure))
            {
                if (!failure.IsFailure)
                    failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.AssetInvalid, "Saved GLB is invalid.", worldObject.instance_id, worldObject.asset_id);
                return false;
            }

            return true;
        }

        private bool TryResolveWorldDirectory(string worldId, out string worldDirectory, out OasisWorldPersistenceFailure failure)
        {
            worldDirectory = null;
            failure = OasisWorldPersistenceFailure.None;
            if (!IsUuid(worldId))
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldId, "world_id must be a UUID.");
                return false;
            }

            string root = WorldsRootPath;
            Directory.CreateDirectory(root);
            worldDirectory = Path.GetFullPath(Path.Combine(root, worldId));
            if (!IsWithinDirectory(root, worldDirectory))
            {
                failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.InvalidWorldId, "world_id path was rejected.");
                return false;
            }

            return true;
        }

        private static IEnumerable<string> GetReferencedAssetIds(OasisWorldDocument document)
        {
            HashSet<string> seen = new HashSet<string>();
            foreach (OasisWorldObject worldObject in document.objects ?? Array.Empty<OasisWorldObject>())
            {
                if (seen.Add(worldObject.asset_id))
                    yield return worldObject.asset_id;
            }
        }

        private static OasisWorldPersistenceFailure CleanupTempAndFail(string tempDirectory, OasisWorldPersistenceFailure failure)
        {
            TryDeleteDirectory(tempDirectory);
            return failure;
        }

        private static bool ValidateChecksum(byte[] glbBytes, OasisAssetManifest manifest, out OasisWorldPersistenceFailure failure)
        {
            failure = OasisWorldPersistenceFailure.None;
            using SHA256 sha256 = SHA256.Create();
            string checksum = BitConverter.ToString(sha256.ComputeHash(glbBytes)).Replace("-", string.Empty).ToLowerInvariant();
            if (checksum == manifest.checksum_sha256.ToLowerInvariant())
                return true;

            failure = new OasisWorldPersistenceFailure(OasisWorldPersistenceErrorCode.AssetChecksumMismatch, "Asset checksum does not match its manifest.", assetId: manifest.asset_id);
            return false;
        }

        private static void AddSkipped(OasisWorldLoadResult result, OasisWorldObject worldObject, OasisWorldPersistenceFailure failure)
        {
            result.SkippedObjects.Add(new OasisWorldSkippedObject
            {
                instance_id = worldObject.instance_id,
                asset_id = worldObject.asset_id,
                reason = failure.Code,
                message = failure.Message
            });
            Debug.LogWarning($"Oasis saved object skipped: instance_id={worldObject.instance_id}, asset_id={worldObject.asset_id}, reason={failure.Code}");
        }

        private static void ApplyTransform(Transform target, OasisWorldTransform source)
        {
            target.position = new Vector3(source.position.x, source.position.y, source.position.z);
            target.rotation = new Quaternion(source.rotation.x, source.rotation.y, source.rotation.z, source.rotation.w);
            target.localScale = new Vector3(source.scale.x, source.scale.y, source.scale.z);
        }

        private static bool IsUuid(string value)
        {
            return Guid.TryParse(value, out _);
        }

        private static bool IsTimestamp(string value)
        {
            return !string.IsNullOrWhiteSpace(value) &&
                DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out _);
        }

        private static bool IsJsonObject(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return false;
            string trimmed = value.Trim();
            return trimmed.StartsWith("{", StringComparison.Ordinal) && trimmed.EndsWith("}", StringComparison.Ordinal);
        }

        private static bool IsWithinDirectory(string rootDirectory, string candidatePath)
        {
            string root = Path.GetFullPath(rootDirectory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string candidate = Path.GetFullPath(candidatePath);
            return candidate.StartsWith(root, StringComparison.Ordinal);
        }

        private static void TryDeleteDirectory(string directory)
        {
            try
            {
                if (Directory.Exists(directory))
                    Directory.Delete(directory, true);
            }
            catch (Exception)
            {
                // Best-effort cleanup; caller still receives the typed save/load failure.
            }
        }

        private static Task<string> ReadAllTextAsync(string path, CancellationToken cancellationToken)
        {
            return Task.Run(() => File.ReadAllText(path, Encoding.UTF8), cancellationToken);
        }

        private static Task WriteAllTextAsync(string path, string contents, CancellationToken cancellationToken)
        {
            return Task.Run(() => File.WriteAllText(path, contents, Encoding.UTF8), cancellationToken);
        }

        private static Task WriteAllBytesAsync(string path, byte[] bytes, CancellationToken cancellationToken)
        {
            return Task.Run(() => File.WriteAllBytes(path, bytes), cancellationToken);
        }

        private static bool TryExtractTopLevelObject(string json, string propertyName, out string rawObject)
        {
            rawObject = null;
            string quotedName = "\"" + propertyName + "\"";
            int propertyIndex = json.IndexOf(quotedName, StringComparison.Ordinal);
            if (propertyIndex < 0)
                return false;

            int colonIndex = json.IndexOf(':', propertyIndex + quotedName.Length);
            if (colonIndex < 0)
                return false;

            int objectStart = colonIndex + 1;
            while (objectStart < json.Length && char.IsWhiteSpace(json[objectStart]))
                objectStart++;
            if (objectStart >= json.Length || json[objectStart] != '{')
                return false;

            bool inString = false;
            bool escaped = false;
            int depth = 0;
            for (int index = objectStart; index < json.Length; index++)
            {
                char current = json[index];
                if (inString)
                {
                    if (escaped)
                    {
                        escaped = false;
                    }
                    else if (current == '\\')
                    {
                        escaped = true;
                    }
                    else if (current == '"')
                    {
                        inString = false;
                    }
                    continue;
                }

                if (current == '"')
                {
                    inString = true;
                }
                else if (current == '{')
                {
                    depth++;
                }
                else if (current == '}')
                {
                    depth--;
                    if (depth == 0)
                    {
                        rawObject = json.Substring(objectStart, index - objectStart + 1);
                        return true;
                    }
                }
            }

            return false;
        }

        private static void AppendJsonProperty(StringBuilder builder, string name, string value, bool comma, int indent = 2)
        {
            builder.Append(' ', indent).Append('"').Append(name).Append("\": \"").Append(EscapeJson(value)).Append('"');
            if (comma)
                builder.Append(',');
            builder.Append('\n');
        }

        private static void AppendVector(StringBuilder builder, string name, OasisWorldVector3 vector, bool comma, int indent)
        {
            builder.Append(' ', indent).Append('"').Append(name).Append("\": { \"x\": ").Append(Float(vector.x)).Append(", \"y\": ").Append(Float(vector.y)).Append(", \"z\": ").Append(Float(vector.z)).Append(" }");
            if (comma)
                builder.Append(',');
            builder.Append('\n');
        }

        private static void AppendQuaternion(StringBuilder builder, string name, OasisWorldQuaternion rotation, bool comma, int indent)
        {
            builder.Append(' ', indent).Append('"').Append(name).Append("\": { \"x\": ").Append(Float(rotation.x)).Append(", \"y\": ").Append(Float(rotation.y)).Append(", \"z\": ").Append(Float(rotation.z)).Append(", \"w\": ").Append(Float(rotation.w)).Append(" }");
            if (comma)
                builder.Append(',');
            builder.Append('\n');
        }

        private static string Float(float value)
        {
            return value.ToString("R", CultureInfo.InvariantCulture);
        }

        private static string EscapeJson(string value)
        {
            return (value ?? string.Empty).Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }
}
