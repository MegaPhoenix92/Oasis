using Oasis.Persistence;
using UnityEngine;

namespace Oasis.Scene
{
    public sealed class OasisTimeOfDayController : MonoBehaviour
    {
        [SerializeField] private Light sun;
        [SerializeField] private bool animateTime = true;
        [SerializeField] private float secondsPerDay = 180f;
        [SerializeField] private float keyboardStep = 0.04f;

        private OasisWorldDocument worldDocument;
        private float currentTimeOfDay = 0.5f;

        public float CurrentTimeOfDay => currentTimeOfDay;
        public bool IsAnimating => animateTime;

        public void Initialize(OasisWorldDocument document, Light directionalSun)
        {
            worldDocument = document;
            currentTimeOfDay = OasisSceneSettings.GetTimeOfDay(worldDocument);
            if (directionalSun != null)
                sun = directionalSun;
            ApplyLighting(currentTimeOfDay);
        }

        private void Update()
        {
            if (worldDocument == null)
                return;

            if (Input.GetKeyDown(KeyCode.T))
                animateTime = !animateTime;
            if (Input.GetKeyDown(KeyCode.LeftBracket))
                SetTimeOfDay(CurrentTimeOfDay - keyboardStep);
            if (Input.GetKeyDown(KeyCode.RightBracket))
                SetTimeOfDay(CurrentTimeOfDay + keyboardStep);

            if (!animateTime || secondsPerDay <= 0f)
                return;

            float next = Mathf.Repeat(CurrentTimeOfDay + Time.deltaTime / secondsPerDay, 1f);
            SetTimeOfDay(next);
        }

        public void SetTimeOfDay(float normalizedTime)
        {
            if (worldDocument == null)
                return;

            float clamped = Mathf.Clamp01(normalizedTime);
            currentTimeOfDay = clamped;
            ApplyLighting(clamped);
        }

        public void SetAnimationEnabled(bool enabled)
        {
            animateTime = enabled;
        }

        public void FlushToWorldDocument()
        {
            OasisSceneSettings.SetTimeOfDay(worldDocument, currentTimeOfDay);
        }

        private void ApplyLighting(float timeOfDay)
        {
            float sunAngle = Mathf.Lerp(-20f, 340f, timeOfDay);
            float daylight = Mathf.Clamp01(Mathf.Sin(timeOfDay * Mathf.PI));
            float twilight = Mathf.Clamp01(1f - Mathf.Abs(timeOfDay - 0.5f) * 2f);

            if (sun != null)
            {
                sun.transform.rotation = Quaternion.Euler(sunAngle, -35f, 0f);
                sun.intensity = Mathf.Lerp(0.08f, 1.25f, daylight);
                sun.color = Color.Lerp(new Color(0.45f, 0.56f, 1f), new Color(1f, 0.92f, 0.74f), twilight);
            }

            RenderSettings.ambientSkyColor = Color.Lerp(new Color(0.03f, 0.04f, 0.08f), new Color(0.62f, 0.68f, 0.74f), daylight);
            RenderSettings.ambientEquatorColor = Color.Lerp(new Color(0.025f, 0.03f, 0.055f), new Color(0.42f, 0.47f, 0.5f), daylight);
            RenderSettings.ambientGroundColor = Color.Lerp(new Color(0.015f, 0.018f, 0.028f), new Color(0.28f, 0.28f, 0.26f), daylight);
            RenderSettings.ambientIntensity = Mathf.Lerp(0.28f, 1.15f, daylight);
        }
    }
}
