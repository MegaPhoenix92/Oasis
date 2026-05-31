using UnityEngine;

namespace Oasis.Scene
{
    public sealed class OasisCameraRig : MonoBehaviour
    {
        [SerializeField] private Transform target;
        [SerializeField] private float orbitSpeed = 120f;
        [SerializeField] private float moveSpeed = 5f;
        [SerializeField] private float zoomSpeed = 8f;
        [SerializeField] private float minDistance = 1.5f;
        [SerializeField] private float maxDistance = 40f;

        private float yaw = 45f;
        private float pitch = 30f;
        private float distance = 8f;

        public void Initialize(Transform cameraTarget)
        {
            target = cameraTarget;
        }

        private void LateUpdate()
        {
            if (target == null)
                return;

            if (Input.GetMouseButton(1))
            {
                yaw += Input.GetAxis("Mouse X") * orbitSpeed * Time.deltaTime;
                pitch -= Input.GetAxis("Mouse Y") * orbitSpeed * Time.deltaTime;
                pitch = Mathf.Clamp(pitch, 8f, 80f);
            }

            float horizontal = Input.GetAxisRaw("Horizontal");
            float vertical = Input.GetAxisRaw("Vertical");
            Vector3 forward = Vector3.ProjectOnPlane(transform.forward, Vector3.up).normalized;
            Vector3 right = Vector3.ProjectOnPlane(transform.right, Vector3.up).normalized;
            target.position += (right * horizontal + forward * vertical) * moveSpeed * Time.deltaTime;

            distance = Mathf.Clamp(distance - Input.mouseScrollDelta.y * zoomSpeed * Time.deltaTime, minDistance, maxDistance);

            Quaternion rotation = Quaternion.Euler(pitch, yaw, 0f);
            transform.position = target.position - rotation * Vector3.forward * distance;
            transform.rotation = rotation;
        }
    }
}
