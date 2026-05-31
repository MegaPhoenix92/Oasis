using System;
using System.Globalization;
using System.Text;
using UnityEngine;

namespace Oasis.Persistence
{
    public static class OasisSceneSettings
    {
        private const string TimeOfDayKey = "time_of_day";

        public static float GetTimeOfDay(OasisWorldDocument document, float fallback = 0.5f)
        {
            if (document == null || !TryGetTopLevelNumber(document.scene_settings_json, TimeOfDayKey, out float value))
                return Mathf.Clamp01(fallback);

            return Mathf.Clamp01(value);
        }

        public static void SetTimeOfDay(OasisWorldDocument document, float value)
        {
            if (document == null)
                return;

            string sceneSettings = IsJsonObject(document.scene_settings_json) ? document.scene_settings_json : "{}";
            string formatted = Mathf.Clamp01(value).ToString("R", CultureInfo.InvariantCulture);
            document.scene_settings_json = SetTopLevelNumber(sceneSettings, TimeOfDayKey, formatted);
        }

        private static bool TryGetTopLevelNumber(string json, string key, out float value)
        {
            value = 0f;
            if (!TryFindTopLevelPropertyValue(json, key, out int valueStart, out int valueEnd))
                return false;

            string raw = json.Substring(valueStart, valueEnd - valueStart).Trim();
            return float.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out value);
        }

        private static string SetTopLevelNumber(string json, string key, string formattedValue)
        {
            if (TryFindTopLevelPropertyValue(json, key, out int valueStart, out int valueEnd))
                return json.Substring(0, valueStart) + formattedValue + json.Substring(valueEnd);

            int closeIndex = json.LastIndexOf('}');
            if (closeIndex < 0)
                return "{ \"" + key + "\": " + formattedValue + " }";

            string beforeClose = json.Substring(0, closeIndex).TrimEnd();
            string afterClose = json.Substring(closeIndex);
            bool hasExistingProperties = beforeClose.Length > 1;
            return beforeClose + (hasExistingProperties ? "," : string.Empty) + " \"" + key + "\": " + formattedValue + " " + afterClose;
        }

        private static bool TryFindTopLevelPropertyValue(string json, string propertyName, out int valueStart, out int valueEnd)
        {
            valueStart = -1;
            valueEnd = -1;
            if (!IsJsonObject(json) || string.IsNullOrEmpty(propertyName))
                return false;

            int depth = 0;
            bool inString = false;
            bool escaped = false;
            for (int index = 0; index < json.Length; index++)
            {
                char current = json[index];
                if (inString)
                {
                    if (escaped)
                    {
                        escaped = false;
                    }
                    else if (current == '\\')
                    {
                        escaped = true;
                    }
                    else if (current == '"')
                    {
                        inString = false;
                    }
                    continue;
                }

                if (current == '{')
                {
                    depth++;
                    continue;
                }
                if (current == '}')
                {
                    depth--;
                    continue;
                }
                if (current != '"')
                    continue;

                if (depth != 1)
                {
                    inString = true;
                    continue;
                }

                int keyStart = index + 1;
                StringBuilder keyBuilder = new StringBuilder();
                bool keyEscaped = false;
                index = keyStart;
                for (; index < json.Length; index++)
                {
                    char keyChar = json[index];
                    if (keyEscaped)
                    {
                        keyBuilder.Append(keyChar);
                        keyEscaped = false;
                    }
                    else if (keyChar == '\\')
                    {
                        keyEscaped = true;
                    }
                    else if (keyChar == '"')
                    {
                        break;
                    }
                    else
                    {
                        keyBuilder.Append(keyChar);
                    }
                }

                if (index >= json.Length || !string.Equals(keyBuilder.ToString(), propertyName, StringComparison.Ordinal))
                    continue;

                int colonIndex = index + 1;
                while (colonIndex < json.Length && char.IsWhiteSpace(json[colonIndex]))
                    colonIndex++;
                if (colonIndex >= json.Length || json[colonIndex] != ':')
                    return false;

                valueStart = colonIndex + 1;
                while (valueStart < json.Length && char.IsWhiteSpace(json[valueStart]))
                    valueStart++;
                if (valueStart >= json.Length)
                    return false;

                valueEnd = FindValueEnd(json, valueStart);
                return valueEnd > valueStart;
            }

            return false;
        }

        private static int FindValueEnd(string json, int start)
        {
            int depth = 0;
            bool inString = false;
            bool escaped = false;
            for (int index = start; index < json.Length; index++)
            {
                char current = json[index];
                if (inString)
                {
                    if (escaped)
                        escaped = false;
                    else if (current == '\\')
                        escaped = true;
                    else if (current == '"')
                        inString = false;
                    continue;
                }

                if (current == '"')
                {
                    inString = true;
                }
                else if (current == '{' || current == '[')
                {
                    depth++;
                }
                else if (current == '}' || current == ']')
                {
                    if (depth == 0)
                        return index;
                    depth--;
                }
                else if (current == ',' && depth == 0)
                {
                    return index;
                }
            }

            return json.Length;
        }

        private static bool IsJsonObject(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return false;
            string trimmed = value.Trim();
            return trimmed.StartsWith("{", StringComparison.Ordinal) && trimmed.EndsWith("}", StringComparison.Ordinal);
        }
    }
}
