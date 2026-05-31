namespace Oasis.Import
{
    public enum OasisImportErrorCode
    {
        None,
        ManifestMalformed,
        ManifestMissingRequiredField,
        ManifestUnsupportedFormat,
        AssetOversized,
        AssetChecksumMismatch,
        AssetInvalid,
        ImportFailed
    }

    public readonly struct OasisImportFailure
    {
        public OasisImportFailure(OasisImportErrorCode code, string message)
        {
            Code = code;
            Message = message;
        }

        public OasisImportErrorCode Code { get; }
        public string Message { get; }

        public static OasisImportFailure None => new OasisImportFailure(OasisImportErrorCode.None, string.Empty);
    }
}
