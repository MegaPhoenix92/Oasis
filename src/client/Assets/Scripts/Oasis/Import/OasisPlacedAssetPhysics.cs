using UnityEngine;

namespace Oasis.Import
{
    public static class OasisPlacedAssetPhysics
    {
        public static void ConfigurePostImport(GameObject importedRoot)
        {
            if (importedRoot == null || !TryGetPostImportRendererBounds(importedRoot, out Bounds bounds))
                return;

            BoxCollider collider = EnsureBoundsCollider(importedRoot);
            collider.center = importedRoot.transform.InverseTransformPoint(bounds.center);
            collider.size = ToLocalSize(importedRoot.transform, bounds.size);
            collider.isTrigger = false;

            Rigidbody body = importedRoot.GetComponent<Rigidbody>();
            if (body == null)
                body = importedRoot.AddComponent<Rigidbody>();

            body.useGravity = true;
            body.isKinematic = true;
            body.mass = Mathf.Max(1f, bounds.size.x * bounds.size.y * bounds.size.z * 12f);
            body.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;
            body.interpolation = RigidbodyInterpolation.Interpolate;
            body.constraints = RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;
        }

        public static void EnablePlacedPhysics(GameObject placedRoot)
        {
            if (placedRoot == null)
                return;

            ConfigurePostImport(placedRoot);
            Rigidbody body = placedRoot.GetComponent<Rigidbody>();
            if (body == null)
                return;

            body.isKinematic = false;
            body.useGravity = true;
            body.WakeUp();
        }

        private static BoxCollider EnsureBoundsCollider(GameObject importedRoot)
        {
            BoxCollider existing = importedRoot.GetComponent<BoxCollider>();
            return existing != null ? existing : importedRoot.AddComponent<BoxCollider>();
        }

        private static bool TryGetPostImportRendererBounds(GameObject root, out Bounds bounds)
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

        private static Vector3 ToLocalSize(Transform root, Vector3 worldSize)
        {
            Vector3 scale = root.lossyScale;
            return new Vector3(
                SafeDivide(worldSize.x, Mathf.Abs(scale.x)),
                SafeDivide(worldSize.y, Mathf.Abs(scale.y)),
                SafeDivide(worldSize.z, Mathf.Abs(scale.z)));
        }

        private static float SafeDivide(float value, float divisor)
        {
            return divisor > 0.0001f ? value / divisor : value;
        }
    }
}
