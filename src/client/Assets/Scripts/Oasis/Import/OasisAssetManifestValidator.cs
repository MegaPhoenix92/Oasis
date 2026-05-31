using System;
using System.Globalization;
using System.Text.RegularExpressions;
using UnityEngine;

namespace Oasis.Import
{
    public static class OasisAssetManifestValidator
    {
        public const long MaxAssetBytes = 50L * 1024L * 1024L;
        private static readonly Regex Sha256Regex = new Regex("^[a-fA-F0-9]{64}$", RegexOptions.Compiled);

        public static bool TryParseAndValidate(string manifestJson, out OasisAssetManifest manifest, out OasisImportFailure failure)
        {
            manifest = null;
            failure = OasisImportFailure.None;

            if (string.IsNullOrWhiteSpace(manifestJson))
            {
                failure = new OasisImportFailure(OasisImportErrorCode.ManifestMalformed, "Asset manifest is empty or malformed.");
                return false;
            }

            try
            {
                manifest = JsonUtility.FromJson<OasisAssetManifest>(manifestJson);
            }
            catch (Exception)
            {
                failure = new OasisImportFailure(OasisImportErrorCode.ManifestMalformed, "Asset manifest is empty or malformed.");
                return false;
            }

            return Validate(manifest, out failure);
        }

        public static bool Validate(OasisAssetManifest manifest, out OasisImportFailure failure)
        {
            failure = OasisImportFailure.None;

            if (manifest == null || manifest.spec == null || manifest.spec.dimensions == null)
            {
                failure = new OasisImportFailure(OasisImportErrorCode.ManifestMissingRequiredField, "Asset manifest is missing required fields.");
                return false;
            }

            if (!HasText(manifest.asset_id) || !Guid.TryParse(manifest.asset_id, out _))
                return Missing(out failure);
            if (!HasText(manifest.source_prompt) || !HasText(manifest.normalized_prompt))
                return Missing(out failure);
            if (!HasText(manifest.provider) || manifest.provider != "meshy.ai")
                return Missing(out failure);
            if (!HasText(manifest.job_id) || !HasText(manifest.source_url))
                return Missing(out failure);
            if (!HasText(manifest.fetch_path) || manifest.fetch_path != "/assets/" + manifest.asset_id)
                return Missing(out failure);
            if (!HasText(manifest.local_path) || !HasText(manifest.checksum_sha256))
                return Missing(out failure);
            if (!Sha256Regex.IsMatch(manifest.checksum_sha256))
                return Missing(out failure);
            if (!HasText(manifest.created_at) || !DateTimeOffset.TryParse(manifest.created_at, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out _))
                return Missing(out failure);

            if (manifest.format != "glb")
            {
                failure = new OasisImportFailure(OasisImportErrorCode.ManifestUnsupportedFormat, "Only GLB assets are supported.");
                return false;
            }

            if (manifest.file_size_bytes <= 0 || manifest.file_size_bytes > MaxAssetBytes)
            {
                failure = new OasisImportFailure(OasisImportErrorCode.AssetOversized, "Asset exceeds the supported size limit.");
                return false;
            }

            if (manifest.triangle_count < 0 || manifest.texture_count < 0)
                return Missing(out failure);

            return ValidateSpec(manifest, out failure);
        }

        public static bool ValidateAssetBytes(byte[] glbBytes, OasisAssetManifest manifest, out OasisImportFailure failure)
        {
            failure = OasisImportFailure.None;

            if (glbBytes == null || glbBytes.Length == 0)
            {
                failure = new OasisImportFailure(OasisImportErrorCode.AssetInvalid, "Asset bytes are empty or invalid.");
                return false;
            }

            if (glbBytes.LongLength > MaxAssetBytes || (manifest != null && manifest.file_size_bytes > MaxAssetBytes))
            {
                failure = new OasisImportFailure(OasisImportErrorCode.AssetOversized, "Asset exceeds the supported size limit.");
                return false;
            }

            if (manifest != null && manifest.file_size_bytes != glbBytes.LongLength)
            {
                failure = new OasisImportFailure(OasisImportErrorCode.AssetInvalid, "Asset size does not match its manifest.");
                return false;
            }

            if (glbBytes.Length < 12 || glbBytes[0] != 0x67 || glbBytes[1] != 0x6c || glbBytes[2] != 0x54 || glbBytes[3] != 0x46)
            {
                failure = new OasisImportFailure(OasisImportErrorCode.AssetInvalid, "Asset is not a valid GLB payload.");
                return false;
            }

            return true;
        }

        private static bool ValidateSpec(OasisAssetManifest manifest, out OasisImportFailure failure)
        {
            OasisSpec spec = manifest.spec;
            if (spec.schema_version != "1.0" || !HasText(spec.source_prompt) || !HasText(spec.normalized_prompt))
                return Missing(out failure);
            if (!HasText(spec.object_type) || !HasText(spec.name) || !HasText(spec.style) || !HasText(spec.meshy_prompt))
                return Missing(out failure);
            if (spec.materials == null || spec.details == null)
                return Missing(out failure);
            if (spec.dimensions.width <= 0f || spec.dimensions.height <= 0f || spec.dimensions.depth <= 0f)
                return Missing(out failure);

            failure = OasisImportFailure.None;
            return true;
        }

        private static bool Missing(out OasisImportFailure failure)
        {
            failure = new OasisImportFailure(OasisImportErrorCode.ManifestMissingRequiredField, "Asset manifest is missing required fields.");
            return false;
        }

        private static bool HasText(string value)
        {
            return !string.IsNullOrWhiteSpace(value);
        }
    }
}
