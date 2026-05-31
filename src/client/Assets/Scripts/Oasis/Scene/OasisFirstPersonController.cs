using UnityEngine;
using UnityEngine.EventSystems;

namespace Oasis.Scene
{
    public sealed class OasisFirstPersonController : MonoBehaviour
    {
        [SerializeField] private Transform cameraPivot;
        [SerializeField] private float walkSpeed = 4.5f;
        [SerializeField] private float sprintMultiplier = 1.75f;
        [SerializeField] private float lookSensitivity = 2.2f;
        [SerializeField] private float gravity = -22f;
        [SerializeField] private float jumpVelocity = 5.2f;
        [SerializeField] private float minPitch = -82f;
        [SerializeField] private float maxPitch = 82f;

        private CharacterController characterController;
        private float pitch;
        private float verticalVelocity;
        private bool lookHeld;

        public void Initialize(Transform cameraTransform)
        {
            cameraPivot = cameraTransform;
            characterController = GetComponent<CharacterController>();
        }

        private void Awake()
        {
            characterController = GetComponent<CharacterController>();
            if (characterController == null)
                characterController = gameObject.AddComponent<CharacterController>();

            characterController.height = 1.8f;
            characterController.radius = 0.32f;
            characterController.center = new Vector3(0f, 0.9f, 0f);
            characterController.stepOffset = 0.35f;
            characterController.slopeLimit = 50f;
        }

        private void Update()
        {
            if (cameraPivot == null || characterController == null)
                return;

            bool uiCapturingKeyboard = EventSystem.current != null && EventSystem.current.currentSelectedGameObject != null;
            UpdateLook();
            UpdateMovement(uiCapturingKeyboard);
        }

        private void UpdateLook()
        {
            if (Input.GetMouseButtonDown(1))
            {
                lookHeld = true;
                Cursor.lockState = CursorLockMode.Locked;
                Cursor.visible = false;
            }
            else if (Input.GetMouseButtonUp(1) || Input.GetKeyDown(KeyCode.Escape))
            {
                lookHeld = false;
                Cursor.lockState = CursorLockMode.None;
                Cursor.visible = true;
            }

            if (!lookHeld)
                return;

            float yawDelta = Input.GetAxis("Mouse X") * lookSensitivity;
            float pitchDelta = Input.GetAxis("Mouse Y") * lookSensitivity;
            transform.Rotate(Vector3.up, yawDelta, Space.World);
            pitch = Mathf.Clamp(pitch - pitchDelta, minPitch, maxPitch);
            cameraPivot.localRotation = Quaternion.Euler(pitch, 0f, 0f);
        }

        private void UpdateMovement(bool uiCapturingKeyboard)
        {
            if (characterController.isGrounded && verticalVelocity < 0f)
                verticalVelocity = -2f;

            Vector3 planar = Vector3.zero;
            if (!uiCapturingKeyboard)
            {
                float horizontal = Input.GetAxisRaw("Horizontal");
                float vertical = Input.GetAxisRaw("Vertical");
                planar = (transform.right * horizontal + transform.forward * vertical);
                if (planar.sqrMagnitude > 1f)
                    planar.Normalize();

                float speed = Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift)
                    ? walkSpeed * sprintMultiplier
                    : walkSpeed;
                planar *= speed;

                if (characterController.isGrounded && Input.GetKeyDown(KeyCode.Space))
                    verticalVelocity = jumpVelocity;
            }

            verticalVelocity += gravity * Time.deltaTime;
            Vector3 velocity = planar + Vector3.up * verticalVelocity;
            characterController.Move(velocity * Time.deltaTime);
        }

        private void OnDisable()
        {
            if (lookHeld)
            {
                Cursor.lockState = CursorLockMode.None;
                Cursor.visible = true;
                lookHeld = false;
            }
        }
    }
}
