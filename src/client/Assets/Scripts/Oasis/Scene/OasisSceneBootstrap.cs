using Oasis.Import;
using UnityEngine;

namespace Oasis.Scene
{
    public sealed class OasisSceneBootstrap : MonoBehaviour
    {
        [SerializeField] private Material groundMaterial;

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

            OasisPlacementAnchor anchor = gameObject.AddComponent<OasisPlacementAnchor>();
            anchor.Initialize(marker.transform);

            gameObject.AddComponent<OasisGridOverlay>();
            gameObject.AddComponent<OasisGlbImporter>();
            CreateLighting();
            CreateCamera(target.transform);

            Debug.Log("Oasis scene foundation ready: ground, grid, lighting, camera, and GLB importer initialized.");
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
