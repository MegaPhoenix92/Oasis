using System;

namespace Oasis.Persistence
{
    [Serializable]
    public sealed class OasisWorldDocument
    {
        public string schema_version = "1.0";
        public string world_id;
        public string name;
        public string created_at;
        public string updated_at;
        public OasisWorldObject[] objects = Array.Empty<OasisWorldObject>();

        [NonSerialized] public string scene_settings_json = "{}";
    }

    [Serializable]
    public sealed class OasisWorldObject
    {
        public string instance_id;
        public string asset_id;
        public OasisWorldTransform transform = new OasisWorldTransform();
        public string created_at;
    }

    [Serializable]
    public sealed class OasisWorldTransform
    {
        public OasisWorldVector3 position = OasisWorldVector3.Zero;
        public OasisWorldQuaternion rotation = OasisWorldQuaternion.Identity;
        public OasisWorldVector3 scale = OasisWorldVector3.One;
    }

    [Serializable]
    public sealed class OasisWorldVector3
    {
        public float x;
        public float y;
        public float z;

        public static OasisWorldVector3 Zero => new OasisWorldVector3 { x = 0f, y = 0f, z = 0f };
        public static OasisWorldVector3 One => new OasisWorldVector3 { x = 1f, y = 1f, z = 1f };
    }

    [Serializable]
    public sealed class OasisWorldQuaternion
    {
        public float x;
        public float y;
        public float z;
        public float w;

        public static OasisWorldQuaternion Identity => new OasisWorldQuaternion { x = 0f, y = 0f, z = 0f, w = 1f };
    }
}
