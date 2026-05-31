using UnityEngine;

namespace Oasis.Import
{
    public readonly struct OasisPlacementResult
    {
        public OasisPlacementResult(float uniformScale, Vector3 rootPosition)
        {
            UniformScale = uniformScale;
            RootPosition = rootPosition;
        }

        public float UniformScale { get; }
        public Vector3 RootPosition { get; }
    }

    public static class OasisPlacementMath
    {
        public static bool TryCalculate(Bounds sourceBounds, OasisDimensions targetDimensions, Vector3 groundAnchor, out OasisPlacementResult result)
        {
            result = default;

            if (targetDimensions == null ||
                sourceBounds.size.x <= 0f || sourceBounds.size.y <= 0f || sourceBounds.size.z <= 0f ||
                targetDimensions.width <= 0f || targetDimensions.height <= 0f || targetDimensions.depth <= 0f)
            {
                return false;
            }

            float scale = Mathf.Min(
                targetDimensions.width / sourceBounds.size.x,
                targetDimensions.height / sourceBounds.size.y,
                targetDimensions.depth / sourceBounds.size.z);

            if (scale <= 0f || float.IsNaN(scale) || float.IsInfinity(scale))
                return false;

            Vector3 scaledCenter = sourceBounds.center * scale;
            Vector3 scaledExtents = sourceBounds.extents * scale;
            Vector3 bottomCenter = new Vector3(scaledCenter.x, scaledCenter.y - scaledExtents.y, scaledCenter.z);
            result = new OasisPlacementResult(scale, groundAnchor - bottomCenter);
            return true;
        }

        public static bool TryApply(GameObject importedRoot, OasisDimensions targetDimensions, Vector3 groundAnchor, out OasisImportFailure failure)
        {
            failure = OasisImportFailure.None;

            if (importedRoot == null || !TryGetRendererBounds(importedRoot, out Bounds sourceBounds))
            {
                failure = new OasisImportFailure(OasisImportErrorCode.AssetInvalid, "Imported asset does not contain renderable geometry.");
                return false;
            }

            if (!TryCalculate(sourceBounds, targetDimensions, groundAnchor, out OasisPlacementResult placement))
            {
                failure = new OasisImportFailure(OasisImportErrorCode.AssetInvalid, "Imported asset bounds or target dimensions are invalid.");
                return false;
            }

            importedRoot.transform.localScale = Vector3.one * placement.UniformScale;
            importedRoot.transform.position = placement.RootPosition;
            return true;
        }

        private static bool TryGetRendererBounds(GameObject root, out Bounds bounds)
        {
            Renderer[] renderers = root.GetComponentsInChildren<Renderer>();
            bounds = default;

            if (renderers.Length == 0)
                return false;

            bounds = renderers[0].bounds;
            for (int index = 1; index < renderers.Length; index++)
                bounds.Encapsulate(renderers[index].bounds);

            return true;
        }
    }
}
