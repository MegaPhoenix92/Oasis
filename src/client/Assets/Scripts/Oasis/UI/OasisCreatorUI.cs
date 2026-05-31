using System;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Oasis.Import;

namespace Oasis.UI
{
    public enum OasisCreatorState
    {
        Idle,
        Generating,
        Preview,
        Error
    }

    public class OasisCreatorUI : MonoBehaviour
    {
        [Header("UI References")]
        [SerializeField] private TMP_InputField promptInputField;
        [SerializeField] private Button generateButton;
        [SerializeField] private Button placeButton;
        [SerializeField] private Button retryButton;
        [SerializeField] private Button undoButton;
        [SerializeField] private Button redoButton;
        [SerializeField] private Button screenshotButton;
        [SerializeField] private Button videoButton;
        [SerializeField] private Button voiceButton;

        [Header("State Panels")]
        [SerializeField] private GameObject generatingPanel;
        [SerializeField] private GameObject errorPanel;
        [SerializeField] private GameObject previewPanel;
        [SerializeField] private TMP_Text errorText;

        [Header("Configuration")]
        public string backendBaseUrl = "http://localhost:8000";
        public int voiceSampleRate = 16000;
        public int voiceMaxSeconds = 8;

        // Integration Seams for #9 and #21
        public event Action<OasisGenerationFacade.GeneratedOasisAsset> OnGenerationReady;
        public event Action OnPlaceRequested;
        public event Action<string> OnFlowFailed;
        public event Action OnUndoRequested;
        public event Action OnRedoRequested;
        public event Action<string, RefineTransformDelta> OnRefineTransformRequested;
        public event Action<string, OasisGenerationFacade.GeneratedOasisAsset> OnRefineAssetReady;

        // Integration Seams for #18
        public event Action OnScreenshotRequested;
        public event Action OnVideoRequested;

        private OasisCreatorState currentState = OasisCreatorState.Idle;
        private OasisGenerationFacade facade;
        private string selectedInstanceId;
        private OasisSpec selectedPriorSpec;
        private AudioClip voiceClip;
        private bool isVoiceRecording;
        private Coroutine voiceTimeoutCoroutine;

        public OasisCreatorState CurrentState => currentState;
        public string SelectedInstanceId => selectedInstanceId;

        private void Awake()
        {
            if (promptInputField == null)
            {
                CreateUIProgrammatically();
            }
        }

        private void Start()
        {
            // Set up button event listeners
            if (generateButton != null)
            {
                generateButton.onClick.AddListener(SubmitPrompt);
            }
            if (retryButton != null)
            {
                retryButton.onClick.AddListener(SubmitPrompt);
            }
            if (placeButton != null)
            {
                placeButton.onClick.AddListener(HandlePlaceRequested);
            }
            if (undoButton != null)
            {
                undoButton.onClick.AddListener(HandleUndoRequested);
            }
            if (redoButton != null)
            {
                redoButton.onClick.AddListener(HandleRedoRequested);
            }
            if (screenshotButton != null)
            {
                screenshotButton.onClick.AddListener(HandleScreenshotRequested);
            }
            if (videoButton != null)
            {
                videoButton.onClick.AddListener(HandleVideoRequested);
            }
            if (voiceButton != null)
            {
                voiceButton.onClick.AddListener(HandleVoiceRequested);
            }

            // Ensure facade is present
            facade = GetComponent<OasisGenerationFacade>();
            if (facade == null)
            {
                facade = gameObject.AddComponent<OasisGenerationFacade>();
            }

            SetState(OasisCreatorState.Idle);
        }

        public void SetSelectedObject(string instanceId, OasisSpec priorSpec)
        {
            selectedInstanceId = instanceId;
            selectedPriorSpec = priorSpec;
        }

        public void ClearSelectedObject(string instanceId = null)
        {
            if (!string.IsNullOrEmpty(instanceId) && selectedInstanceId != instanceId)
                return;

            selectedInstanceId = null;
            selectedPriorSpec = null;
        }

        private void Update()
        {
            // Keyboard support: Enter key submits prompt when focused, idle/error state, and not empty
            if ((currentState == OasisCreatorState.Idle || currentState == OasisCreatorState.Error)
                && promptInputField != null
                && promptInputField.isFocused
                && !string.IsNullOrWhiteSpace(promptInputField.text))
            {
                if (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter))
                {
                    SubmitPrompt();
                }
            }

            // Undo/Redo keyboard shortcuts
            bool isControlOrCommand = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl) ||
                                     Input.GetKey(KeyCode.LeftCommand) || Input.GetKey(KeyCode.RightCommand);

            if (isControlOrCommand)
            {
                if (Input.GetKeyDown(KeyCode.Z))
                {
                    if (Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift))
                    {
                        HandleRedoRequested();
                    }
                    else
                    {
                        HandleUndoRequested();
                    }
                }
                else if (Input.GetKeyDown(KeyCode.Y))
                {
                    HandleRedoRequested();
                }
            }
        }

        private bool canUndo = false;
        private bool canRedo = false;

        public void SetUndoRedoStates(bool canUndo, bool canRedo)
        {
            this.canUndo = canUndo;
            this.canRedo = canRedo;
            UpdateUndoRedoButtonInteractivity();
        }

        private void UpdateUndoRedoButtonInteractivity()
        {
            bool interactable = (currentState != OasisCreatorState.Generating);
            bool isUiInteractable = interactable && !isVoiceRecording;

            if (generateButton != null)
            {
                generateButton.interactable = isUiInteractable;
            }

            if (promptInputField != null)
            {
                promptInputField.interactable = isUiInteractable;
            }

            if (undoButton != null)
            {
                undoButton.interactable = canUndo && interactable;
                Image img = undoButton.GetComponent<Image>();
                if (img != null)
                {
                    img.color = (canUndo && interactable) ? new Color(0.25f, 0.45f, 0.75f, 1f) : new Color(0.2f, 0.2f, 0.2f, 0.5f);
                }
            }

            if (redoButton != null)
            {
                redoButton.interactable = canRedo && interactable;
                Image img = redoButton.GetComponent<Image>();
                if (img != null)
                {
                    img.color = (canRedo && interactable) ? new Color(0.25f, 0.45f, 0.75f, 1f) : new Color(0.2f, 0.2f, 0.2f, 0.5f);
                }
            }

            if (screenshotButton != null)
            {
                screenshotButton.interactable = interactable;
                Image img = screenshotButton.GetComponent<Image>();
                if (img != null)
                {
                    img.color = interactable ? new Color(0.4f, 0.2f, 0.7f, 1f) : new Color(0.2f, 0.2f, 0.2f, 0.5f);
                }
            }

            if (videoButton != null)
            {
                videoButton.interactable = interactable;
                Image img = videoButton.GetComponent<Image>();
                if (img != null)
                {
                    img.color = interactable ? new Color(0.8f, 0.3f, 0.3f, 1f) : new Color(0.2f, 0.2f, 0.2f, 0.5f);
                }
            }

            if (voiceButton != null)
            {
                voiceButton.interactable = (currentState != OasisCreatorState.Generating) || isVoiceRecording;
                Image img = voiceButton.GetComponent<Image>();
                if (img != null)
                {
                    img.color = isVoiceRecording ? new Color(0.9f, 0.2f, 0.2f, 1f) : ((currentState != OasisCreatorState.Generating) ? new Color(0.15f, 0.5f, 0.55f, 1f) : new Color(0.2f, 0.2f, 0.2f, 0.5f));
                }
            }
        }

        private void HandleUndoRequested()
        {
            OnUndoRequested?.Invoke();
        }

        private void HandleRedoRequested()
        {
            OnRedoRequested?.Invoke();
        }

        private void HandleScreenshotRequested()
        {
            OnScreenshotRequested?.Invoke();
        }

        private void HandleVideoRequested()
        {
            OnVideoRequested?.Invoke();
        }

        private void HandleVoiceRequested()
        {
            if (isVoiceRecording)
            {
                FinishVoiceRecording();
                return;
            }

            if (currentState == OasisCreatorState.Generating)
                return;

            if (Microphone.devices == null || Microphone.devices.Length == 0)
            {
                SetState(OasisCreatorState.Error, "microphone_error");
                OnFlowFailed?.Invoke("microphone_error");
                return;
            }

            try
            {
                voiceClip = Microphone.Start(null, false, voiceMaxSeconds, voiceSampleRate);
            }
            catch (Exception)
            {
                voiceClip = null;
            }

            if (voiceClip == null)
            {
                SetState(OasisCreatorState.Error, "microphone_error");
                OnFlowFailed?.Invoke("microphone_error");
                return;
            }

            isVoiceRecording = true;
            UpdateUndoRedoButtonInteractivity();
            voiceTimeoutCoroutine = StartCoroutine(CoWatchVoiceRecordingTimeout());
        }

        private void FinishVoiceRecording()
        {
            if (voiceTimeoutCoroutine != null)
            {
                StopCoroutine(voiceTimeoutCoroutine);
                voiceTimeoutCoroutine = null;
            }

            bool wasRecording = Microphone.IsRecording(null);
            int samplePosition = wasRecording ? Microphone.GetPosition(null) : (voiceClip != null ? voiceClip.samples : 0);
            Microphone.End(null);
            isVoiceRecording = false;
            UpdateUndoRedoButtonInteractivity();

            if (voiceClip == null || samplePosition <= 0)
            {
                SetState(OasisCreatorState.Error, voiceClip == null ? "microphone_error" : "invalid_prompt");
                OnFlowFailed?.Invoke(voiceClip == null ? "microphone_error" : "invalid_prompt");
                return;
            }

            byte[] wavBytes = EncodeWav(voiceClip, samplePosition);
            SetState(OasisCreatorState.Generating);
            facade.backendBaseUrl = backendBaseUrl;
            facade.StartVoiceAudioFlow(
                wavBytes,
                "audio/wav",
                onSuccess: SubmitVoiceTranscript,
                onFailure: (errorCode) =>
                {
                    SetState(OasisCreatorState.Error, errorCode);
                    OnFlowFailed?.Invoke(errorCode);
                });
        }

        public void SetState(OasisCreatorState state, string errorCode = null)
        {
            currentState = state;

            // Toggle state panels based on active state
            if (generatingPanel != null) generatingPanel.SetActive(state == OasisCreatorState.Generating);
            if (errorPanel != null) errorPanel.SetActive(state == OasisCreatorState.Error);
            if (previewPanel != null) previewPanel.SetActive(state == OasisCreatorState.Preview);

            // Handle input field interactivity
            if (promptInputField != null)
            {
                promptInputField.interactable = (state != OasisCreatorState.Generating);
            }

            // Handle buttons interactiveness and visibility
            if (generateButton != null)
            {
                generateButton.interactable = (state != OasisCreatorState.Generating);
            }

            if (placeButton != null)
            {
                placeButton.gameObject.SetActive(state == OasisCreatorState.Preview);
                placeButton.interactable = (state == OasisCreatorState.Preview);
            }

            if (retryButton != null)
            {
                retryButton.gameObject.SetActive(state == OasisCreatorState.Error);
                retryButton.interactable = (state == OasisCreatorState.Error);
            }

            // Setup error text message
            if (state == OasisCreatorState.Error && errorText != null)
            {
                errorText.text = GetSafeErrorMessage(errorCode);
            }

            UpdateUndoRedoButtonInteractivity();
        }

        public void SubmitPrompt()
        {
            if (promptInputField == null) return;

            string prompt = promptInputField.text;
            if (string.IsNullOrWhiteSpace(prompt))
            {
                SetState(OasisCreatorState.Error, "invalid_prompt");
                OnFlowFailed?.Invoke("invalid_prompt");
                return;
            }

            SetState(OasisCreatorState.Generating);

            facade.backendBaseUrl = backendBaseUrl;
            if (!string.IsNullOrEmpty(selectedInstanceId) && selectedPriorSpec != null)
            {
                facade.StartRefineFlow(selectedPriorSpec, prompt,
                    onSuccess: (result) =>
                    {
                        if (result.kind == "transform")
                        {
                            PerformSelectedTransformRefine(result);
                        }
                        else if (result.kind == "respec")
                        {
                            StartSelectedRespecRefine(result);
                        }
                        else
                        {
                            SetState(OasisCreatorState.Error, "model_parse_error");
                            OnFlowFailed?.Invoke("model_parse_error");
                        }
                    },
                    onFailure: (errorCode) =>
                    {
                        SetState(OasisCreatorState.Error, errorCode);
                        OnFlowFailed?.Invoke(errorCode);
                    }
                );
                return;
            }

            facade.StartGenerationFlow(prompt,
                onSuccess: (manifest) =>
                {
                    SetState(OasisCreatorState.Preview);
                    OnGenerationReady?.Invoke(manifest);
                },
                onFailure: (errorCode) =>
                {
                    SetState(OasisCreatorState.Error, errorCode);
                    OnFlowFailed?.Invoke(errorCode);
                }
            );
        }

        public void SubmitVoiceTranscript(string transcript)
        {
            if (promptInputField == null)
                return;

            promptInputField.text = transcript;
            SubmitPrompt();
        }

        private void PerformSelectedTransformRefine(RefineResult result)
        {
            OnRefineTransformRequested?.Invoke(selectedInstanceId, result.transform_delta);
            SetState(OasisCreatorState.Idle);
        }

        private void StartSelectedRespecRefine(RefineResult result)
        {
            string refinedInstanceId = selectedInstanceId;
            facade.StartGenerationFromSpec(result.spec,
                onSuccess: (asset) =>
                {
                    SetState(OasisCreatorState.Idle);
                    OnRefineAssetReady?.Invoke(refinedInstanceId, asset);
                },
                onFailure: (errorCode) =>
                {
                    SetState(OasisCreatorState.Error, errorCode);
                    OnFlowFailed?.Invoke(errorCode);
                }
            );
        }

        private void HandlePlaceRequested()
        {
            OnPlaceRequested?.Invoke();
        }

        public void RecordAssetImported(string assetId)
        {
            if (facade != null)
                facade.RecordAssetImported(assetId);
        }

        public void RecordObjectPlaced(string assetId)
        {
            if (facade != null)
                facade.RecordObjectPlaced(assetId);
        }

        public string GetSafeErrorMessage(string errorCode)
        {
            switch (errorCode)
            {
                case "invalid_prompt":
                    return "The prompt provided is empty or invalid. Please check your description and try again.";
                case "model_parse_error":
                    return "Failed to parse the generation specification. Please try a different description.";
                case "provider_error":
                    return "The AI generation provider encountered an error. Please try again in a moment.";
                case "timeout":
                    return "The generation request timed out. The server took too long to respond. Please retry.";
                case "asset_not_found":
                    return "The requested asset could not be found on the server.";
                case "asset_invalid":
                    return "The generated asset is invalid or could not be loaded.";
                case "network_error":
                    return "Could not connect to the Oasis AI service. Please make sure the backend is running.";
                case "microphone_error":
                    return "Could not access the microphone. Please check microphone permissions and try again.";
                default:
                    return "An unexpected error occurred during generation. Please try again.";
            }
        }

        private void CreateUIProgrammatically()
        {
            // Create Canvas
            GameObject canvasObj = new GameObject("OasisCreatorCanvas");
            canvasObj.transform.SetParent(transform, false);
            Canvas canvas = canvasObj.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvasObj.AddComponent<CanvasScaler>();
            canvasObj.AddComponent<GraphicRaycaster>();

            // Create EventSystem if not exists
            if (UnityEngine.Object.FindObjectOfType<UnityEngine.EventSystems.EventSystem>() == null)
            {
                GameObject eventSystemObj = new GameObject("EventSystem");
                eventSystemObj.AddComponent<UnityEngine.EventSystems.EventSystem>();
                eventSystemObj.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
            }

            // UI Panel
            GameObject panelObj = new GameObject("UIPanel");
            panelObj.transform.SetParent(canvasObj.transform, false);
            Image panelImage = panelObj.AddComponent<Image>();
            panelImage.color = new Color(0.12f, 0.12f, 0.12f, 0.85f); // Semi-transparent dark background

            RectTransform panelRect = panelObj.GetComponent<RectTransform>();
            panelRect.anchorMin = new Vector2(0f, 1f); // Top-left anchor
            panelRect.anchorMax = new Vector2(0f, 1f);
            panelRect.pivot = new Vector2(0f, 1f);
            panelRect.anchoredPosition = new Vector2(20f, -20f);
            panelRect.sizeDelta = new Vector2(340f, 210f);

            // 1. Prompt Input Field
            GameObject inputObj = new GameObject("PromptInputField");
            inputObj.transform.SetParent(panelObj.transform, false);
            RectTransform inputRect = inputObj.AddComponent<RectTransform>();
            inputRect.anchorMin = new Vector2(0.5f, 1f);
            inputRect.anchorMax = new Vector2(0.5f, 1f);
            inputRect.pivot = new Vector2(0.5f, 1f);
            inputRect.anchoredPosition = new Vector2(0f, -15f);
            inputRect.sizeDelta = new Vector2(300f, 35f);

            Image inputImage = inputObj.AddComponent<Image>();
            inputImage.color = new Color(0.2f, 0.2f, 0.2f, 1f);

            promptInputField = inputObj.AddComponent<TMP_InputField>();

            GameObject textAreaObj = new GameObject("Text Area");
            textAreaObj.transform.SetParent(inputObj.transform, false);
            RectTransform textAreaRect = textAreaObj.AddComponent<RectTransform>();
            textAreaRect.anchorMin = Vector2.zero;
            textAreaRect.anchorMax = Vector2.one;
            textAreaRect.sizeDelta = new Vector2(-10f, -10f); // 5px padding on sides

            textAreaObj.AddComponent<RectMask2D>();

            // Text text
            GameObject textObj = new GameObject("Text");
            textObj.transform.SetParent(textAreaObj.transform, false);
            RectTransform textRect = textObj.AddComponent<RectTransform>();
            textRect.anchorMin = Vector2.zero;
            textRect.anchorMax = Vector2.one;
            textRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI textComponent = textObj.AddComponent<TextMeshProUGUI>();
            textComponent.color = Color.white;
            textComponent.fontSize = 13f;
            textComponent.alignment = TextAlignmentOptions.Left;

            // Placeholder text
            GameObject placeholderObj = new GameObject("Placeholder");
            placeholderObj.transform.SetParent(textAreaObj.transform, false);
            RectTransform placeholderRect = placeholderObj.AddComponent<RectTransform>();
            placeholderRect.anchorMin = Vector2.zero;
            placeholderRect.anchorMax = Vector2.one;
            placeholderRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI placeholderComponent = placeholderObj.AddComponent<TextMeshProUGUI>();
            placeholderComponent.text = "Enter generation prompt...";
            placeholderComponent.color = new Color(0.6f, 0.6f, 0.6f, 1.0f);
            placeholderComponent.fontSize = 13f;
            placeholderComponent.fontStyle = FontStyles.Italic;
            placeholderComponent.alignment = TextAlignmentOptions.Left;

            promptInputField.textViewport = textAreaRect;
            promptInputField.textComponent = textComponent;
            promptInputField.placeholder = placeholderComponent;

            // 2. Generate Button
            GameObject genBtnObj = new GameObject("GenerateButton");
            genBtnObj.transform.SetParent(panelObj.transform, false);
            RectTransform genBtnRect = genBtnObj.AddComponent<RectTransform>();
            genBtnRect.anchorMin = new Vector2(0.5f, 1f);
            genBtnRect.anchorMax = new Vector2(0.5f, 1f);
            genBtnRect.pivot = new Vector2(0.5f, 1f);
            genBtnRect.anchoredPosition = new Vector2(-110f, -60f);
            genBtnRect.sizeDelta = new Vector2(90f, 30f);

            Image genBtnImage = genBtnObj.AddComponent<Image>();
            genBtnImage.color = new Color(0.12f, 0.58f, 0.28f, 1f); // Sleek Green
            generateButton = genBtnObj.AddComponent<Button>();

            GameObject genBtnTextObj = new GameObject("Text");
            genBtnTextObj.transform.SetParent(genBtnObj.transform, false);
            RectTransform genBtnTextRect = genBtnTextObj.AddComponent<RectTransform>();
            genBtnTextRect.anchorMin = Vector2.zero;
            genBtnTextRect.anchorMax = Vector2.one;
            genBtnTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI genBtnText = genBtnTextObj.AddComponent<TextMeshProUGUI>();
            genBtnText.text = "Generate";
            genBtnText.color = Color.white;
            genBtnText.fontSize = 13f;
            genBtnText.alignment = TextAlignmentOptions.Center;

            // Undo Button
            GameObject undoBtnObj = new GameObject("UndoButton");
            undoBtnObj.transform.SetParent(panelObj.transform, false);
            RectTransform undoBtnRect = undoBtnObj.AddComponent<RectTransform>();
            undoBtnRect.anchorMin = new Vector2(0.5f, 1f);
            undoBtnRect.anchorMax = new Vector2(0.5f, 1f);
            undoBtnRect.pivot = new Vector2(0.5f, 1f);
            undoBtnRect.anchoredPosition = new Vector2(-10f, -60f);
            undoBtnRect.sizeDelta = new Vector2(90f, 30f);

            Image undoBtnImage = undoBtnObj.AddComponent<Image>();
            undoBtnImage.color = new Color(0.2f, 0.2f, 0.2f, 0.5f);
            undoButton = undoBtnObj.AddComponent<Button>();
            undoButton.interactable = false;

            GameObject undoBtnTextObj = new GameObject("Text");
            undoBtnTextObj.transform.SetParent(undoBtnObj.transform, false);
            RectTransform undoBtnTextRect = undoBtnTextObj.AddComponent<RectTransform>();
            undoBtnTextRect.anchorMin = Vector2.zero;
            undoBtnTextRect.anchorMax = Vector2.one;
            undoBtnTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI undoBtnText = undoBtnTextObj.AddComponent<TextMeshProUGUI>();
            undoBtnText.text = "Undo";
            undoBtnText.color = Color.white;
            undoBtnText.fontSize = 13f;
            undoBtnText.alignment = TextAlignmentOptions.Center;

            // Redo Button
            GameObject redoBtnObj = new GameObject("RedoButton");
            redoBtnObj.transform.SetParent(panelObj.transform, false);
            RectTransform redoBtnRect = redoBtnObj.AddComponent<RectTransform>();
            redoBtnRect.anchorMin = new Vector2(0.5f, 1f);
            redoBtnRect.anchorMax = new Vector2(0.5f, 1f);
            redoBtnRect.pivot = new Vector2(0.5f, 1f);
            redoBtnRect.anchoredPosition = new Vector2(90f, -60f);
            redoBtnRect.sizeDelta = new Vector2(90f, 30f);

            Image redoBtnImage = redoBtnObj.AddComponent<Image>();
            redoBtnImage.color = new Color(0.2f, 0.2f, 0.2f, 0.5f);
            redoButton = redoBtnObj.AddComponent<Button>();
            redoButton.interactable = false;

            GameObject redoBtnTextObj = new GameObject("Text");
            redoBtnTextObj.transform.SetParent(redoBtnObj.transform, false);
            RectTransform redoBtnTextRect = redoBtnTextObj.AddComponent<RectTransform>();
            redoBtnTextRect.anchorMin = Vector2.zero;
            redoBtnTextRect.anchorMax = Vector2.one;
            redoBtnTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI redoBtnText = redoBtnTextObj.AddComponent<TextMeshProUGUI>();
            redoBtnText.text = "Redo";
            redoBtnText.color = Color.white;
            redoBtnText.fontSize = 13f;
            redoBtnText.alignment = TextAlignmentOptions.Center;

            // 3. Generating Panel
            generatingPanel = new GameObject("GeneratingPanel");
            generatingPanel.transform.SetParent(panelObj.transform, false);
            RectTransform genPanelRect = generatingPanel.AddComponent<RectTransform>();
            genPanelRect.anchorMin = new Vector2(0.5f, 0f);
            genPanelRect.anchorMax = new Vector2(0.5f, 0f);
            genPanelRect.pivot = new Vector2(0.5f, 0f);
            genPanelRect.anchoredPosition = new Vector2(0f, 10f);
            genPanelRect.sizeDelta = new Vector2(300f, 40f);

            GameObject genTextObj = new GameObject("Text");
            genTextObj.transform.SetParent(generatingPanel.transform, false);
            RectTransform genTextRect = genTextObj.AddComponent<RectTransform>();
            genTextRect.anchorMin = Vector2.zero;
            genTextRect.anchorMax = Vector2.one;
            genTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI genText = genTextObj.AddComponent<TextMeshProUGUI>();
            genText.text = "Generating asset, please wait...";
            genText.color = new Color(0.95f, 0.65f, 0.1f, 1f);
            genText.fontSize = 12f;
            genText.alignment = TextAlignmentOptions.Center;

            // 4. Preview Panel (with Place Button)
            previewPanel = new GameObject("PreviewPanel");
            previewPanel.transform.SetParent(panelObj.transform, false);
            RectTransform prevPanelRect = previewPanel.AddComponent<RectTransform>();
            prevPanelRect.anchorMin = new Vector2(0.5f, 0f);
            prevPanelRect.anchorMax = new Vector2(0.5f, 0f);
            prevPanelRect.pivot = new Vector2(0.5f, 0f);
            prevPanelRect.anchoredPosition = new Vector2(0f, 10f);
            prevPanelRect.sizeDelta = new Vector2(300f, 40f);

            GameObject placeBtnObj = new GameObject("PlaceButton");
            placeBtnObj.transform.SetParent(previewPanel.transform, false);
            RectTransform placeBtnRect = placeBtnObj.AddComponent<RectTransform>();
            placeBtnRect.anchorMin = new Vector2(0.5f, 0.5f);
            placeBtnRect.anchorMax = new Vector2(0.5f, 0.5f);
            placeBtnRect.pivot = new Vector2(0.5f, 0.5f);
            placeBtnRect.anchoredPosition = Vector2.zero;
            placeBtnRect.sizeDelta = new Vector2(120f, 30f);

            Image placeBtnImage = placeBtnObj.AddComponent<Image>();
            placeBtnImage.color = new Color(0.1f, 0.45f, 0.9f, 1f); // Vibrant blue
            placeButton = placeBtnObj.AddComponent<Button>();

            GameObject placeBtnTextObj = new GameObject("Text");
            placeBtnTextObj.transform.SetParent(placeBtnObj.transform, false);
            RectTransform placeBtnTextRect = placeBtnTextObj.AddComponent<RectTransform>();
            placeBtnTextRect.anchorMin = Vector2.zero;
            placeBtnTextRect.anchorMax = Vector2.one;
            placeBtnTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI placeBtnText = placeBtnTextObj.AddComponent<TextMeshProUGUI>();
            placeBtnText.text = "Place in Scene";
            placeBtnText.color = Color.white;
            placeBtnText.fontSize = 13f;
            placeBtnText.alignment = TextAlignmentOptions.Center;

            // 5. Error Panel (with Error Text and Retry Button)
            errorPanel = new GameObject("ErrorPanel");
            errorPanel.transform.SetParent(panelObj.transform, false);
            RectTransform errPanelRect = errorPanel.AddComponent<RectTransform>();
            errPanelRect.anchorMin = new Vector2(0.5f, 0f);
            errPanelRect.anchorMax = new Vector2(0.5f, 0f);
            errPanelRect.pivot = new Vector2(0.5f, 0f);
            errPanelRect.anchoredPosition = new Vector2(0f, 10f);
            errPanelRect.sizeDelta = new Vector2(300f, 50f);

            GameObject errTextObj = new GameObject("ErrorText");
            errTextObj.transform.SetParent(errorPanel.transform, false);
            RectTransform errTextRect = errTextObj.AddComponent<RectTransform>();
            errTextRect.anchorMin = new Vector2(0.5f, 1f);
            errTextRect.anchorMax = new Vector2(0.5f, 1f);
            errTextRect.pivot = new Vector2(0.5f, 1f);
            errTextRect.anchoredPosition = new Vector2(0f, 0f);
            errTextRect.sizeDelta = new Vector2(300f, 25f);
            errorText = errTextObj.AddComponent<TextMeshProUGUI>();
            errorText.color = new Color(0.9f, 0.2f, 0.2f, 1f); // Error red
            errorText.fontSize = 11f;
            errorText.alignment = TextAlignmentOptions.Center;

            GameObject retryBtnObj = new GameObject("RetryButton");
            retryBtnObj.transform.SetParent(errorPanel.transform, false);
            RectTransform retryBtnRect = retryBtnObj.AddComponent<RectTransform>();
            retryBtnRect.anchorMin = new Vector2(0.5f, 0f);
            retryBtnRect.anchorMax = new Vector2(0.5f, 0f);
            retryBtnRect.pivot = new Vector2(0.5f, 0f);
            retryBtnRect.anchoredPosition = new Vector2(0f, 2f);
            retryBtnRect.sizeDelta = new Vector2(80f, 20f);

            Image retryBtnImage = retryBtnObj.AddComponent<Image>();
            retryBtnImage.color = new Color(0.4f, 0.4f, 0.4f, 1f);
            retryButton = retryBtnObj.AddComponent<Button>();

            GameObject retryBtnTextObj = new GameObject("Text");
            retryBtnTextObj.transform.SetParent(retryBtnObj.transform, false);
            RectTransform retryBtnTextRect = retryBtnTextObj.AddComponent<RectTransform>();
            retryBtnTextRect.anchorMin = Vector2.zero;
            retryBtnTextRect.anchorMax = Vector2.one;
            retryBtnTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI retryBtnText = retryBtnTextObj.AddComponent<TextMeshProUGUI>();
            retryBtnText.text = "Retry";
            retryBtnText.color = Color.white;
            retryBtnText.fontSize = 11f;
            retryBtnText.alignment = TextAlignmentOptions.Center;

            // 6. Screenshot Button
            GameObject ssBtnObj = new GameObject("ScreenshotButton");
            ssBtnObj.transform.SetParent(panelObj.transform, false);
            RectTransform ssBtnRect = ssBtnObj.AddComponent<RectTransform>();
            ssBtnRect.anchorMin = new Vector2(0.5f, 1f);
            ssBtnRect.anchorMax = new Vector2(0.5f, 1f);
            ssBtnRect.pivot = new Vector2(0.5f, 1f);
            ssBtnRect.anchoredPosition = new Vector2(-60f, -100f);
            ssBtnRect.sizeDelta = new Vector2(110f, 30f);

            Image ssBtnImage = ssBtnObj.AddComponent<Image>();
            ssBtnImage.color = new Color(0.4f, 0.2f, 0.7f, 1f); // Sleek Indigo
            screenshotButton = ssBtnObj.AddComponent<Button>();

            GameObject ssBtnTextObj = new GameObject("Text");
            ssBtnTextObj.transform.SetParent(ssBtnObj.transform, false);
            RectTransform ssBtnTextRect = ssBtnTextObj.AddComponent<RectTransform>();
            ssBtnTextRect.anchorMin = Vector2.zero;
            ssBtnTextRect.anchorMax = Vector2.one;
            ssBtnTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI ssBtnText = ssBtnTextObj.AddComponent<TextMeshProUGUI>();
            ssBtnText.text = "Screenshot";
            ssBtnText.color = Color.white;
            ssBtnText.fontSize = 13f;
            ssBtnText.alignment = TextAlignmentOptions.Center;

            // 7. Video Button
            GameObject vidBtnObj = new GameObject("VideoButton");
            vidBtnObj.transform.SetParent(panelObj.transform, false);
            RectTransform vidBtnRect = vidBtnObj.AddComponent<RectTransform>();
            vidBtnRect.anchorMin = new Vector2(0.5f, 1f);
            vidBtnRect.anchorMax = new Vector2(0.5f, 1f);
            vidBtnRect.pivot = new Vector2(0.5f, 1f);
            vidBtnRect.anchoredPosition = new Vector2(60f, -100f);
            vidBtnRect.sizeDelta = new Vector2(110f, 30f);

            Image vidBtnImage = vidBtnObj.AddComponent<Image>();
            vidBtnImage.color = new Color(0.8f, 0.3f, 0.3f, 1f); // Sleek Coral/Red
            videoButton = vidBtnObj.AddComponent<Button>();

            GameObject vidBtnTextObj = new GameObject("Text");
            vidBtnTextObj.transform.SetParent(vidBtnObj.transform, false);
            RectTransform vidBtnTextRect = vidBtnTextObj.AddComponent<RectTransform>();
            vidBtnTextRect.anchorMin = Vector2.zero;
            vidBtnTextRect.anchorMax = Vector2.one;
            vidBtnTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI vidBtnText = vidBtnTextObj.AddComponent<TextMeshProUGUI>();
            vidBtnText.text = "Capture Clip";
            vidBtnText.color = Color.white;
            vidBtnText.fontSize = 13f;
            vidBtnText.alignment = TextAlignmentOptions.Center;

            // 8. Voice Button
            GameObject voiceBtnObj = new GameObject("VoiceButton");
            voiceBtnObj.transform.SetParent(panelObj.transform, false);
            RectTransform voiceBtnRect = voiceBtnObj.AddComponent<RectTransform>();
            voiceBtnRect.anchorMin = new Vector2(0.5f, 1f);
            voiceBtnRect.anchorMax = new Vector2(0.5f, 1f);
            voiceBtnRect.pivot = new Vector2(0.5f, 1f);
            voiceBtnRect.anchoredPosition = new Vector2(0f, -140f);
            voiceBtnRect.sizeDelta = new Vector2(110f, 30f);

            Image voiceBtnImage = voiceBtnObj.AddComponent<Image>();
            voiceBtnImage.color = new Color(0.15f, 0.5f, 0.55f, 1f);
            voiceButton = voiceBtnObj.AddComponent<Button>();

            GameObject voiceBtnTextObj = new GameObject("Text");
            voiceBtnTextObj.transform.SetParent(voiceBtnObj.transform, false);
            RectTransform voiceBtnTextRect = voiceBtnTextObj.AddComponent<RectTransform>();
            voiceBtnTextRect.anchorMin = Vector2.zero;
            voiceBtnTextRect.anchorMax = Vector2.one;
            voiceBtnTextRect.sizeDelta = Vector2.zero;
            TextMeshProUGUI voiceBtnText = voiceBtnTextObj.AddComponent<TextMeshProUGUI>();
            voiceBtnText.text = "Voice";
            voiceBtnText.color = Color.white;
            voiceBtnText.fontSize = 13f;
            voiceBtnText.alignment = TextAlignmentOptions.Center;
        }

        private static byte[] EncodeWav(AudioClip clip, int sampleCount)
        {
            int channels = clip.channels;
            int frequency = clip.frequency;
            int clampedSamples = Mathf.Clamp(sampleCount, 0, clip.samples);
            float[] samples = new float[clampedSamples * channels];
            clip.GetData(samples, 0);

            using (MemoryStream stream = new MemoryStream())
            using (BinaryWriter writer = new BinaryWriter(stream))
            {
                int dataLength = samples.Length * 2;
                writer.Write(Encoding.ASCII.GetBytes("RIFF"));
                writer.Write(36 + dataLength);
                writer.Write(Encoding.ASCII.GetBytes("WAVE"));
                writer.Write(Encoding.ASCII.GetBytes("fmt "));
                writer.Write(16);
                writer.Write((short)1);
                writer.Write((short)channels);
                writer.Write(frequency);
                writer.Write(frequency * channels * 2);
                writer.Write((short)(channels * 2));
                writer.Write((short)16);
                writer.Write(Encoding.ASCII.GetBytes("data"));
                writer.Write(dataLength);

                for (int i = 0; i < samples.Length; i++)
                {
                    short value = (short)Mathf.Clamp(samples[i] * short.MaxValue, short.MinValue, short.MaxValue);
                    writer.Write(value);
                }

                return stream.ToArray();
            }
        }

        private System.Collections.IEnumerator CoWatchVoiceRecordingTimeout()
        {
            yield return new WaitForSeconds(voiceMaxSeconds);
            voiceTimeoutCoroutine = null;
            if (isVoiceRecording)
            {
                FinishVoiceRecording();
            }
        }
    }
}
