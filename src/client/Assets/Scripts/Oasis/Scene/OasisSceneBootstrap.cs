using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Oasis.Import;
using Oasis.Persistence;
using Oasis.UI;
using UnityEngine;

namespace Oasis.Scene
{
    public sealed class OasisSceneBootstrap : MonoBehaviour
    {
        [SerializeField] private Material groundMaterial;
        private OasisPlacementAnchor placementAnchor;
        private OasisGlbImporter glbImporter;
        private OasisWorldPersistence worldPersistence;
        private OasisTimeOfDayController timeOfDayController;
        private Light directionalSun;
        private OasisCreatorUI creatorUI;
        private GameObject activeImportedObject;
        private OasisGenerationFacade.GeneratedOasisAsset activeAsset;
        private OasisWorldDocument activeWorld;
        private readonly Dictionary<string, string> manifestJsonByAssetId = new Dictionary<string, string>();
        private readonly Dictionary<string, byte[]> glbBytesByAssetId = new Dictionary<string, byte[]>();
        private readonly Dictionary<string, GameObject> gameObjectByInstanceId = new Dictionary<string, GameObject>();
        private readonly OasisCreatorHistory creatorHistory = new OasisCreatorHistory();
        private readonly List<GameObject> placedWorldObjects = new List<GameObject>();

        private void Awake()
        {
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.62f, 0.68f, 0.74f);
            RenderSettings.ambientEquatorColor = new Color(0.42f, 0.47f, 0.5f);
            RenderSettings.ambientGroundColor = new Color(0.28f, 0.28f, 0.26f);
            RenderSettings.ambientIntensity = 1.15f;

            CreateGround();
            GameObject marker = CreatePlacementMarker();

            placementAnchor = gameObject.AddComponent<OasisPlacementAnchor>();
            placementAnchor.Initialize(marker.transform);

            gameObject.AddComponent<OasisGridOverlay>();
            glbImporter = gameObject.AddComponent<OasisGlbImporter>();
            worldPersistence = gameObject.AddComponent<OasisWorldPersistence>();
            creatorUI = gameObject.AddComponent<OasisCreatorUI>();
            creatorUI.OnGenerationReady += HandleGenerationReady;
            creatorUI.OnPlaceRequested += HandlePlaceRequested;
            creatorUI.OnUndoRequested += HandleUndoRequested;
            creatorUI.OnRedoRequested += HandleRedoRequested;
            activeWorld = CreateNewWorldDocument("Untitled World");
            UpdateUndoRedoUI();
            directionalSun = CreateLighting();
            timeOfDayController = gameObject.AddComponent<OasisTimeOfDayController>();
            timeOfDayController.Initialize(activeWorld, directionalSun);
            CreateCamera();

            Debug.Log("Oasis scene foundation ready: ground, grid, lighting, camera, and GLB importer initialized.");
        }

        private async void HandleGenerationReady(OasisGenerationFacade.GeneratedOasisAsset asset)
        {
            if (asset == null || glbImporter == null || placementAnchor == null)
                return;

            if (activeImportedObject != null)
                Destroy(activeImportedObject);

            activeAsset = asset;
            manifestJsonByAssetId[asset.Manifest.asset_id] = asset.ManifestJson;
            glbBytesByAssetId[asset.Manifest.asset_id] = asset.GlbBytes;
            activeImportedObject = await glbImporter.ImportFromBytesAsync(asset.GlbBytes, asset.ManifestJson, placementAnchor.LastGroundPoint);
            if (activeImportedObject != null && creatorUI != null)
                creatorUI.RecordAssetImported(asset.Manifest.asset_id);
        }

        private void UpdateUndoRedoUI()
        {
            if (creatorUI != null)
            {
                creatorUI.SetUndoRedoStates(creatorHistory.UndoCount > 0, creatorHistory.RedoCount > 0);
            }
        }

        private async void HandleUndoRequested()
        {
            await UndoAsync();
        }

        private async void HandleRedoRequested()
        {
            await RedoAsync();
        }

        public async Task UndoAsync()
        {
            OasisCreatorOperation op = creatorHistory.PopUndo();
            if (op == null) return;

            if (op.type == "place")
            {
                DeleteObjectInMemory(op.snapshot.instance_id);
            }
            else if (op.type == "delete")
            {
                await RestoreObjectInMemoryAsync(op.snapshot);
            }
            else if (op.type == "move")
            {
                RestoreMoveInMemory(op.instance_id, op.from);
            }

            UpdateUndoRedoUI();
        }

        public async Task RedoAsync()
        {
            OasisCreatorOperation op = creatorHistory.PopRedo();
            if (op == null) return;

            if (op.type == "place")
            {
                await RestoreObjectInMemoryAsync(op.snapshot);
            }
            else if (op.type == "delete")
            {
                DeleteObjectInMemory(op.snapshot.instance_id);
            }
            else if (op.type == "move")
            {
                RestoreMoveInMemory(op.instance_id, op.to);
            }

            UpdateUndoRedoUI();
        }

        private void DeleteObjectInMemory(string instanceId)
        {
            if (gameObjectByInstanceId.TryGetValue(instanceId, out GameObject obj))
            {
                if (obj != null)
                {
                    placedWorldObjects.Remove(obj);
                    Destroy(obj);
                }
                gameObjectByInstanceId.Remove(instanceId);
            }

            if (activeWorld != null && activeWorld.objects != null)
            {
                List<OasisWorldObject> objects = new List<OasisWorldObject>(activeWorld.objects);
                objects.RemoveAll(o => o.instance_id == instanceId);
                activeWorld.objects = objects.ToArray();
            }
        }

        private async Task RestoreObjectInMemoryAsync(OasisWorldObject snapshot)
        {
            if (snapshot == null) return;

            if (glbBytesByAssetId.TryGetValue(snapshot.asset_id, out byte[] glbBytes) &&
                manifestJsonByAssetId.TryGetValue(snapshot.asset_id, out string manifestJson))
            {
                GameObject obj = await glbImporter.ImportFromBytesAsync(glbBytes, manifestJson, Vector3.zero);
                if (obj != null)
                {
                    ApplyTransform(obj.transform, snapshot.transform);
                    obj.name = "OasisObject_" + snapshot.instance_id;
                    OasisPlacedAssetPhysics.EnablePlacedPhysics(obj);
                    
                    OasisWorldObjectBehaviour behaviour = obj.AddComponent<OasisWorldObjectBehaviour>();
                    behaviour.instanceId = snapshot.instance_id;
                    behaviour.assetId = snapshot.asset_id;

                    placedWorldObjects.Add(obj);
                    gameObjectByInstanceId[snapshot.instance_id] = obj;
                }
            }

            if (activeWorld != null)
            {
                List<OasisWorldObject> objects = new List<OasisWorldObject>(activeWorld.objects ?? Array.Empty<OasisWorldObject>());
                bool exists = false;
                foreach (OasisWorldObject o in objects)
                {
                    if (o.instance_id == snapshot.instance_id)
                    {
                        exists = true;
                        break;
                    }
                }
                if (!exists)
                {
                    objects.Add(CloneWorldObject(snapshot));
                    activeWorld.objects = objects.ToArray();
                }
            }
        }

        private void RestoreMoveInMemory(string instanceId, OasisWorldTransform targetTransform)
        {
            if (gameObjectByInstanceId.TryGetValue(instanceId, out GameObject obj))
            {
                if (obj != null)
                {
                    ApplyTransform(obj.transform, targetTransform);
                }
            }
            UpdateTransformInWorld(instanceId, targetTransform);
        }

        private void UpdateTransformInWorld(string instanceId, OasisWorldTransform newTransform)
        {
            if (activeWorld != null && activeWorld.objects != null)
            {
                foreach (OasisWorldObject obj in activeWorld.objects)
                {
                    if (obj.instance_id == instanceId)
                    {
                        obj.transform.position.x = newTransform.position.x;
                        obj.transform.position.y = newTransform.position.y;
                        obj.transform.position.z = newTransform.position.z;

                        obj.transform.rotation.x = newTransform.rotation.x;
                        obj.transform.rotation.y = newTransform.rotation.y;
                        obj.transform.rotation.z = newTransform.rotation.z;
                        obj.transform.rotation.w = newTransform.rotation.w;

                        obj.transform.scale.x = newTransform.scale.x;
                        obj.transform.scale.y = newTransform.scale.y;
                        obj.transform.scale.z = newTransform.scale.z;
                        break;
                    }
                }
            }
        }

        public void PerformMove(string instanceId, OasisWorldTransform toTransform)
        {
            if (gameObjectByInstanceId.TryGetValue(instanceId, out GameObject obj))
            {
                OasisWorldObject wObj = null;
                foreach (OasisWorldObject o in activeWorld.objects)
                {
                    if (o.instance_id == instanceId)
                    {
                        wObj = o;
                        break;
                    }
                }

                if (wObj != null)
                {
                    OasisCreatorOperation op = new OasisCreatorOperation
                    {
                        type = "move",
                        instance_id = instanceId,
                        from = CloneWorldTransform(wObj.transform),
                        to = CloneWorldTransform(toTransform)
                    };

                    if (obj != null)
                    {
                        ApplyTransform(obj.transform, toTransform);
                    }
                    UpdateTransformInWorld(instanceId, toTransform);

                    creatorHistory.PushOperation(op);
                    UpdateUndoRedoUI();
                }
            }
        }

        public void PerformDelete(string instanceId)
        {
            OasisWorldObject wObj = null;
            foreach (OasisWorldObject o in activeWorld.objects)
            {
                if (o.instance_id == instanceId)
                {
                    wObj = o;
                    break;
                }
            }

            if (wObj != null)
            {
                OasisCreatorOperation op = new OasisCreatorOperation
                {
                    type = "delete",
                    snapshot = CloneWorldObject(wObj)
                };

                DeleteObjectInMemory(instanceId);

                creatorHistory.PushOperation(op);
                UpdateUndoRedoUI();
            }
        }

        private static void ApplyTransform(Transform unityTransform, OasisWorldTransform docTransform)
        {
            unityTransform.position = new Vector3(docTransform.position.x, docTransform.position.y, docTransform.position.z);
            unityTransform.rotation = new Quaternion(docTransform.rotation.x, docTransform.rotation.y, docTransform.rotation.z, docTransform.rotation.w);
            unityTransform.localScale = new Vector3(docTransform.scale.x, docTransform.scale.y, docTransform.scale.z);
        }

        private static OasisWorldTransform CloneWorldTransform(OasisWorldTransform src)
        {
            if (src == null) return null;
            return new OasisWorldTransform
            {
                position = new OasisWorldVector3 { x = src.position.x, y = src.position.y, z = src.position.z },
                rotation = new OasisWorldQuaternion { x = src.rotation.x, y = src.rotation.y, z = src.rotation.z, w = src.rotation.w },
                scale = new OasisWorldVector3 { x = src.scale.x, y = src.scale.y, z = src.scale.z }
            };
        }

        private static OasisWorldObject CloneWorldObject(OasisWorldObject src)
        {
            if (src == null) return null;
            return new OasisWorldObject
            {
                instance_id = src.instance_id,
                asset_id = src.asset_id,
                created_at = src.created_at,
                transform = CloneWorldTransform(src.transform)
            };
        }

        private OasisWorldObject CreateWorldObject(string instanceId, string assetId, Transform placedTransform)
        {
            return new OasisWorldObject
            {
                instance_id = instanceId,
                asset_id = assetId,
                created_at = NowIso(),
                transform = CreateWorldTransform(placedTransform)
            };
        }

        private void HandlePlaceRequested()
        {
            if (activeImportedObject == null || activeAsset == null || placementAnchor == null)
                return;

            MoveObjectToAnchor(activeImportedObject, placementAnchor.LastGroundPoint);
            
            string instanceId = Guid.NewGuid().ToString();
            OasisWorldObject worldObject = CreateWorldObject(instanceId, activeAsset.Manifest.asset_id, activeImportedObject.transform);

            List<OasisWorldObject> objects = new List<OasisWorldObject>(activeWorld.objects ?? Array.Empty<OasisWorldObject>());
            objects.Add(worldObject);
            activeWorld.objects = objects.ToArray();

            activeImportedObject.name = "OasisObject_" + instanceId;
            OasisWorldObjectBehaviour behaviour = activeImportedObject.AddComponent<OasisWorldObjectBehaviour>();
            behaviour.instanceId = instanceId;
            behaviour.assetId = activeAsset.Manifest.asset_id;

            placedWorldObjects.Add(activeImportedObject);
            gameObjectByInstanceId[instanceId] = activeImportedObject;
            OasisPlacedAssetPhysics.EnablePlacedPhysics(activeImportedObject);

            OasisCreatorOperation op = new OasisCreatorOperation
            {
                type = "place",
                snapshot = CloneWorldObject(worldObject)
            };
            creatorHistory.PushOperation(op);
            UpdateUndoRedoUI();

            if (creatorUI != null)
                creatorUI.RecordObjectPlaced(activeAsset.Manifest.asset_id);
            Debug.Log($"Oasis asset placed in scene: asset_id={activeAsset.Manifest.asset_id}, point={placementAnchor.LastGroundPoint}, instance_id={instanceId}");
            activeImportedObject = null;
            activeAsset = null;
        }

        public Task<OasisWorldPersistenceFailure> SaveActiveWorldAsync(CancellationToken cancellationToken = default)
        {
            SyncWorldTransformsFromScene();
            activeWorld.updated_at = NowIso();
            return worldPersistence.SaveAsync(
                activeWorld,
                manifestJsonByAssetId,
                new OasisHttpAssetFetcher(creatorUI != null ? creatorUI.backendBaseUrl : "http://localhost:8000"),
                cancellationToken);
        }

        public async Task<OasisWorldLoadResult> LoadWorldAsync(string worldId, CancellationToken cancellationToken = default)
        {
            OasisWorldLoadResult result = await worldPersistence.LoadAsync(worldId, glbImporter, cancellationToken);
            if (result.Success && result.Document != null)
            {
                DestroyActiveSceneObjects();
                activeWorld = result.Document;
                manifestJsonByAssetId.Clear();
                glbBytesByAssetId.Clear();
                gameObjectByInstanceId.Clear();
                creatorHistory.Clear();

                foreach (KeyValuePair<string, string> entry in result.ManifestJsonByAssetId)
                    manifestJsonByAssetId[entry.Key] = entry.Value;

                foreach (KeyValuePair<string, byte[]> entry in result.GlbBytesByAssetId)
                    glbBytesByAssetId[entry.Key] = entry.Value;

                foreach (GameObject obj in result.ImportedObjects)
                {
                    if (obj != null && obj.name.StartsWith("OasisObject_"))
                    {
                        string instanceId = obj.name.Substring("OasisObject_".Length);
                        
                        string assetId = "";
                        foreach (OasisWorldObject wObj in activeWorld.objects)
                        {
                            if (wObj.instance_id == instanceId)
                            {
                                assetId = wObj.asset_id;
                                break;
                            }
                        }

                        OasisWorldObjectBehaviour behaviour = obj.AddComponent<OasisWorldObjectBehaviour>();
                        behaviour.instanceId = instanceId;
                        behaviour.assetId = assetId;
                        OasisPlacedAssetPhysics.EnablePlacedPhysics(obj);

                        placedWorldObjects.Add(obj);
                        gameObjectByInstanceId[instanceId] = obj;
                    }
                }
                if (timeOfDayController != null)
                    timeOfDayController.Initialize(activeWorld, directionalSun);
                UpdateUndoRedoUI();
            }
            return result;
        }

        private void SyncWorldTransformsFromScene()
        {
            if (timeOfDayController != null)
                timeOfDayController.FlushToWorldDocument();

            if (activeWorld == null || activeWorld.objects == null)
                return;

            foreach (OasisWorldObject worldObject in activeWorld.objects)
            {
                if (worldObject == null || string.IsNullOrWhiteSpace(worldObject.instance_id))
                    continue;

                if (!gameObjectByInstanceId.TryGetValue(worldObject.instance_id, out GameObject obj) || obj == null)
                    continue;

                worldObject.transform = CreateWorldTransform(obj.transform);
            }
        }

        private void DestroyActiveSceneObjects()
        {
            if (activeImportedObject != null)
            {
                Destroy(activeImportedObject);
                activeImportedObject = null;
                activeAsset = null;
            }

            foreach (GameObject placedObject in placedWorldObjects)
            {
                if (placedObject != null)
                    Destroy(placedObject);
            }
            placedWorldObjects.Clear();
            gameObjectByInstanceId.Clear();
        }

        private static OasisWorldDocument CreateNewWorldDocument(string worldName)
        {
            string now = NowIso();
            return new OasisWorldDocument
            {
                schema_version = "1.0",
                world_id = Guid.NewGuid().ToString(),
                name = string.IsNullOrWhiteSpace(worldName) ? "Untitled World" : worldName,
                created_at = now,
                updated_at = now,
                scene_settings_json = "{ \"time_of_day\": 0.5 }",
                objects = Array.Empty<OasisWorldObject>()
            };
        }

        private static string NowIso()
        {
            return DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
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

        private static Light CreateLighting()
        {
            GameObject lightObject = new GameObject("Directional Key Light");
            Light light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.15f;
            light.shadows = LightShadows.Soft;
            lightObject.transform.rotation = Quaternion.Euler(50f, -35f, 0f);
            return light;
        }

        private static void CreateCamera()
        {
            GameObject explorer = new GameObject("Oasis First Person Explorer");
            explorer.transform.position = new Vector3(0f, 0.08f, -5f);
            CharacterController controller = explorer.AddComponent<CharacterController>();
            controller.height = 1.8f;
            controller.radius = 0.32f;
            controller.center = new Vector3(0f, 0.9f, 0f);

            GameObject cameraObject = new GameObject("Oasis Camera");
            cameraObject.transform.SetParent(explorer.transform, false);
            cameraObject.transform.localPosition = new Vector3(0f, 1.62f, 0f);
            Camera camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.fieldOfView = 55f;
            camera.nearClipPlane = 0.03f;
            camera.farClipPlane = 500f;
            cameraObject.tag = "MainCamera";

            OasisFirstPersonController firstPerson = explorer.AddComponent<OasisFirstPersonController>();
            firstPerson.Initialize(cameraObject.transform);
        }

        private static OasisWorldTransform CreateWorldTransform(Transform placedTransform)
        {
            return new OasisWorldTransform
            {
                position = new OasisWorldVector3 { x = placedTransform.position.x, y = placedTransform.position.y, z = placedTransform.position.z },
                rotation = new OasisWorldQuaternion { x = placedTransform.rotation.x, y = placedTransform.rotation.y, z = placedTransform.rotation.z, w = placedTransform.rotation.w },
                scale = new OasisWorldVector3 { x = placedTransform.localScale.x, y = placedTransform.localScale.y, z = placedTransform.localScale.z }
            };
        }
    }
}
