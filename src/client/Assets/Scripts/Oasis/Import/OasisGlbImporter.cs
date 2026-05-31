using System;
using System.IO;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;
using GLTFast;
using UnityEngine;

namespace Oasis.Import
{
    public sealed class OasisGlbImporter : MonoBehaviour
    {
        [SerializeField] private Transform importParent;
        [SerializeField] private Vector3 defaultPlacementPoint = Vector3.zero;

        public async Task<GameObject> ImportFromFileAsync(string glbFilePath, string manifestJson, Vector3 groundAnchor, CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(glbFilePath) || !File.Exists(glbFilePath))
            {
                ReportFailure(new OasisImportFailure(OasisImportErrorCode.AssetInvalid, "Asset file was not found."));
                return null;
            }

            byte[] bytes;
            try
            {
                bytes = await Task.Run(() => File.ReadAllBytes(glbFilePath), cancellationToken);
            }
            catch (Exception)
            {
                ReportFailure(new OasisImportFailure(OasisImportErrorCode.AssetInvalid, "Asset file could not be read."));
                return null;
            }

            return await ImportFromBytesAsync(bytes, manifestJson, groundAnchor, new Uri(glbFilePath), cancellationToken);
        }

        public async Task<GameObject> ImportFromBytesAsync(byte[] glbBytes, string manifestJson, Vector3 groundAnchor, Uri sourceUri = null, CancellationToken cancellationToken = default)
        {
            if (!OasisAssetManifestValidator.TryParseAndValidate(manifestJson, out OasisAssetManifest manifest, out OasisImportFailure failure) ||
                !OasisAssetManifestValidator.ValidateAssetBytes(glbBytes, manifest, out failure) ||
                !ValidateChecksum(glbBytes, manifest, out failure))
            {
                ReportFailure(failure);
                return null;
            }

            Transform parent = importParent != null ? importParent : transform;
            GameObject importedRoot = new GameObject("Imported Asset " + manifest.asset_id);
            importedRoot.transform.SetParent(parent, false);

            try
            {
                using GltfImport gltf = new GltfImport();
                Uri uri = sourceUri ?? new Uri("oasis://asset/" + manifest.asset_id + ".glb");
                bool loaded = await gltf.LoadGltfBinary(glbBytes, uri, cancellationToken: cancellationToken);
                if (!loaded || !await gltf.InstantiateMainSceneAsync(importedRoot.transform, cancellationToken))
                {
                    Destroy(importedRoot);
                    ReportFailure(new OasisImportFailure(OasisImportErrorCode.ImportFailed, "Asset import failed."));
                    return null;
                }
            }
            catch (Exception)
            {
                Destroy(importedRoot);
                ReportFailure(new OasisImportFailure(OasisImportErrorCode.ImportFailed, "Asset import failed."));
                return null;
            }

            if (!OasisPlacementMath.TryApply(importedRoot, manifest.spec.dimensions, groundAnchor, out failure))
            {
                Destroy(importedRoot);
                ReportFailure(failure);
                return null;
            }

            Debug.Log($"Oasis asset imported: asset_id={manifest.asset_id}, triangles={manifest.triangle_count}, textures={manifest.texture_count}");
            return importedRoot;
        }

        public Task<GameObject> ImportFromBytesAtDefaultPointAsync(byte[] glbBytes, string manifestJson, CancellationToken cancellationToken = default)
        {
            return ImportFromBytesAsync(glbBytes, manifestJson, defaultPlacementPoint, cancellationToken: cancellationToken);
        }

        private static bool ValidateChecksum(byte[] glbBytes, OasisAssetManifest manifest, out OasisImportFailure failure)
        {
            failure = OasisImportFailure.None;
            using SHA256 sha256 = SHA256.Create();
            string checksum = BitConverter.ToString(sha256.ComputeHash(glbBytes)).Replace("-", string.Empty).ToLowerInvariant();
            if (checksum == manifest.checksum_sha256.ToLowerInvariant())
                return true;

            failure = new OasisImportFailure(OasisImportErrorCode.AssetChecksumMismatch, "Asset checksum does not match its manifest.");
            return false;
        }

        private static void ReportFailure(OasisImportFailure failure)
        {
            Debug.LogWarning($"Oasis import rejected: {failure.Code} - {failure.Message}");
        }
    }
}
