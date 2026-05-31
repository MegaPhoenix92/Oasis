using Oasis.Import;
using Oasis.UI;
using UnityEngine;

namespace Oasis.Scene
{
    public sealed class OasisSceneBootstrap : MonoBehaviour
    {
        [SerializeField] private Material groundMaterial;
        private OasisPlacementAnchor placementAnchor;
        private OasisGlbImporter glbImporter;
        private OasisCreatorUI creatorUI;
        private GameObject activeImportedObject;
        private OasisGenerationFacade.GeneratedOasisAsset activeAsset;

        private void Awake()
        {
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.62f, 0.68f, 0.74f);
            RenderSettings.ambientEquatorColor = new Color(0.42f, 0.47f, 0.5f);
            RenderSettings.ambientGroundColor = new Color(0.28f, 0.28f, 0.26f);
            RenderSettings.ambientIntensity = 1.15f;

            CreateGround();
            GameObject marker = CreatePlacementMarker();
            GameObject target = new GameObject("Camera Target");
            target.transform.position = new Vector3(0f, 1f, 0f);

            placementAnchor = gameObject.AddComponent<OasisPlacementAnchor>();
            placementAnchor.Initialize(marker.transform);

            gameObject.AddComponent<OasisGridOverlay>();
            glbImporter = gameObject.AddComponent<OasisGlbImporter>();
            creatorUI = gameObject.AddComponent<OasisCreatorUI>();
            creatorUI.OnGenerationReady += HandleGenerationReady;
            creatorUI.OnPlaceRequested += HandlePlaceRequested;
            CreateLighting();
            CreateCamera(target.transform);

            Debug.Log("Oasis scene foundation ready: ground, grid, lighting, camera, and GLB importer initialized.");
        }

        private async void HandleGenerationReady(OasisGenerationFacade.GeneratedOasisAsset asset)
        {
            if (asset == null || glbImporter == null || placementAnchor == null)
                return;

            if (activeImportedObject != null)
                Destroy(activeImportedObject);

            activeAsset = asset;
            activeImportedObject = await glbImporter.ImportFromBytesAsync(asset.GlbBytes, asset.ManifestJson, placementAnchor.LastGroundPoint);
            if (activeImportedObject != null && creatorUI != null)
                creatorUI.RecordAssetImported(asset.Manifest.asset_id);
        }

        private void HandlePlaceRequested()
        {
            if (activeImportedObject == null || activeAsset == null || placementAnchor == null)
                return;

            MoveObjectToAnchor(activeImportedObject, placementAnchor.LastGroundPoint);
            if (creatorUI != null)
                creatorUI.RecordObjectPlaced(activeAsset.Manifest.asset_id);
            Debug.Log($"Oasis asset placed in scene: asset_id={activeAsset.Manifest.asset_id}, point={placementAnchor.LastGroundPoint}");
        }

        private static void MoveObjectToAnchor(GameObject importedRoot, Vector3 groundAnchor)
        {
            Renderer[] renderers = importedRoot.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0)
                return;

            Bounds bounds = renderers[0].bounds;
            for (int index = 1; index < renderers.Length; index++)
                bounds.Encapsulate(renderers[index].bounds);

            Vector3 bottomCenter = new Vector3(bounds.center.x, bounds.min.y, bounds.center.z);
            importedRoot.transform.position += groundAnchor - bottomCenter;
        }

        private void CreateGround()
        {
            GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Oasis Ground Plane";
            ground.transform.localScale = new Vector3(10f, 1f, 10f);
            ground.layer = 0;

            Renderer renderer = ground.GetComponent<Renderer>();
            if (renderer != null)
                renderer.sharedMaterial = groundMaterial != null ? groundMaterial : CreateGroundMaterial();
        }

        private static Material CreateGroundMaterial()
        {
            Material material = new Material(Shader.Find("Standard"));
            material.name = "Oasis Runtime Ground";
            material.color = new Color(0.38f, 0.43f, 0.37f);
            return material;
        }

        private static GameObject CreatePlacementMarker()
        {
            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            marker.name = "Placement Anchor Marker";
            marker.transform.localScale = new Vector3(0.35f, 0.02f, 0.35f);
            Collider collider = marker.GetComponent<Collider>();
            if (collider != null)
                Destroy(collider);

            Renderer renderer = marker.GetComponent<Renderer>();
            if (renderer != null)
            {
                Material material = new Material(Shader.Find("Standard"));
                material.name = "Oasis Placement Marker";
                material.color = new Color(0.1f, 0.45f, 0.9f, 0.8f);
                renderer.sharedMaterial = material;
            }

            return marker;
        }

        private static void CreateLighting()
        {
            GameObject lightObject = new GameObject("Directional Key Light");
            Light light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.15f;
            light.shadows = LightShadows.Soft;
            lightObject.transform.rotation = Quaternion.Euler(50f, -35f, 0f);
        }

        private static void CreateCamera(Transform target)
        {
            GameObject cameraObject = new GameObject("Oasis Camera");
            Camera camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.fieldOfView = 55f;
            camera.nearClipPlane = 0.03f;
            camera.farClipPlane = 500f;
            cameraObject.tag = "MainCamera";

            OasisCameraRig rig = cameraObject.AddComponent<OasisCameraRig>();
            rig.Initialize(target);
            cameraObject.transform.position = new Vector3(5f, 4f, -6f);
            cameraObject.transform.LookAt(target);
        }
    }
}
