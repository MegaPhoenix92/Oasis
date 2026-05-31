using UnityEngine;

namespace Oasis.Scene
{
    public sealed class OasisGridOverlay : MonoBehaviour
    {
        [SerializeField] private int halfExtent = 10;
        [SerializeField] private float spacing = 1f;
        [SerializeField] private Color majorLine = new Color(0.32f, 0.36f, 0.4f, 0.7f);
        [SerializeField] private Color minorLine = new Color(0.24f, 0.27f, 0.3f, 0.45f);

        private GameObject gridRoot;

        private void Awake()
        {
            BuildGrid();
        }

        private void Update()
        {
            if (Input.GetKeyDown(KeyCode.G) && gridRoot != null)
                gridRoot.SetActive(!gridRoot.activeSelf);
        }

        private void BuildGrid()
        {
            gridRoot = new GameObject("Grid Overlay Lines");
            gridRoot.transform.SetParent(transform, false);
            gridRoot.transform.localPosition = Vector3.up * 0.01f;

            for (int index = -halfExtent; index <= halfExtent; index++)
            {
                Color color = index == 0 || index % 5 == 0 ? majorLine : minorLine;
                AddLine(new Vector3(index * spacing, 0f, -halfExtent * spacing), new Vector3(index * spacing, 0f, halfExtent * spacing), color);
                AddLine(new Vector3(-halfExtent * spacing, 0f, index * spacing), new Vector3(halfExtent * spacing, 0f, index * spacing), color);
            }
        }

        private void AddLine(Vector3 start, Vector3 end, Color color)
        {
            GameObject lineObject = new GameObject("Grid Line");
            lineObject.transform.SetParent(gridRoot.transform, false);
            LineRenderer line = lineObject.AddComponent<LineRenderer>();
            line.positionCount = 2;
            line.SetPosition(0, start);
            line.SetPosition(1, end);
            line.startWidth = 0.015f;
            line.endWidth = 0.015f;
            line.material = new Material(Shader.Find("Sprites/Default"));
            line.startColor = color;
            line.endColor = color;
            line.useWorldSpace = false;
        }
    }
}
