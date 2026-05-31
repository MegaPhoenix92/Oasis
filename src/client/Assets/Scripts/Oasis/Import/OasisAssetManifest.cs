using System;

namespace Oasis.Import
{
    [Serializable]
    public sealed class OasisDimensions
    {
        public float width;
        public float height;
        public float depth;
    }

    [Serializable]
    public sealed class OasisSpec
    {
        public string schema_version;
        public string source_prompt;
        public string normalized_prompt;
        public string object_type;
        public string name;
        public string[] materials;
        public string style;
        public OasisDimensions dimensions;
        public string[] details;
        public string meshy_prompt;
    }

    [Serializable]
    public sealed class OasisAssetManifest
    {
        public string asset_id;
        public string source_prompt;
        public string normalized_prompt;
        public OasisSpec spec;
        public string provider;
        public string job_id;
        public string source_url;
        public string fetch_path;
        public string local_path;
        public string checksum_sha256;
        public string format;
        public long file_size_bytes;
        public int triangle_count;
        public int texture_count;
        public string created_at;
    }
}
