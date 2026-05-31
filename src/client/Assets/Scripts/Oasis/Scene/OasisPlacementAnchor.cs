using UnityEngine;

namespace Oasis.Scene
{
    public sealed class OasisPlacementAnchor : MonoBehaviour
    {
        [SerializeField] private LayerMask groundMask = 1;
        [SerializeField] private Transform marker;

        public Vector3 LastGroundPoint { get; private set; }

        public void Initialize(Transform markerTransform)
        {
            marker = markerTransform;
            UpdateMarker();
        }

        private void Awake()
        {
            LastGroundPoint = Vector3.zero;
            UpdateMarker();
        }

        private void Update()
        {
            if (!Input.GetMouseButtonDown(0) || Camera.main == null)
                return;

            Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
            if (Physics.Raycast(ray, out RaycastHit hit, 500f, groundMask, QueryTriggerInteraction.Ignore))
            {
                LastGroundPoint = hit.point;
                UpdateMarker();
                Debug.Log($"Oasis placement point selected: {LastGroundPoint}");
            }
        }

        private void UpdateMarker()
        {
            if (marker == null)
                return;

            marker.position = LastGroundPoint + Vector3.up * 0.03f;
        }
    }
}
