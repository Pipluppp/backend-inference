import { createMapController } from "./map.js";
import { bindHeroInteractions, createUIController, wireModelModalityBehavior } from "./ui.js";
import { initializeUploadWorkflow } from "./upload.js";

function selectElement(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Element not found for selector: ${selector}`);
  }
  return element;
}

// --- NEW STATE AND HELPER FUNCTIONS ---

let mapControllerA = null;
let mapControllerB = null;
let mapAState = { model: null, label: null, modality: null };
let mapBState = { model: null, label: null, modality: null };

function updateMapLabel(labelId, modelLabel, modalityLabel) {
  const labelEl = document.getElementById(labelId);
  if (labelEl) {
    labelEl.textContent = `${modelLabel} · ${modalityLabel}`;
    labelEl.classList.remove('is-hidden');
  }
}

// --- REFACTORED RESULT HANDLER ---

function handleAnalysisResult({ result, context, ui, toggles }) {
  const newModel = context.model;

  let targetMapController;
  let targetMapState;
  let targetMapLabelId;

  // Case 1: First analysis, or re-analyzing with the model already on map A
  if (mapAState.model === null || mapAState.model === newModel) {
    targetMapController = mapControllerA;
    targetMapState = mapAState;
    targetMapLabelId = "map-label-a";
  }
  // Case 2: A different model is chosen, triggering comparison view
  else {
    const mapSection = selectElement('#map-section');
    const mapWrapperB = selectElement('#map-wrapper-b');

    mapSection.classList.add('is-comparison-view');
    mapWrapperB.classList.remove('is-hidden');

    if (!mapControllerB) {
      mapControllerB = createMapController({ containerId: 'leaflet-map-b' });
    }

    targetMapController = mapControllerB;
    targetMapState = mapBState;
    targetMapLabelId = "map-label-b";
  }

  // Update state and UI
  targetMapState.model = newModel;
  targetMapState.label = context.modelLabel;
  targetMapState.modality = context.modalityLabel;
  updateMapLabel(targetMapLabelId, context.modelLabel, context.modalityLabel);

  // Render the result on the target map
  if (!result || !result.success) {
    const errorMessage = result?.error || "Analysis failed";
    ui.setStatus(`Error: ${errorMessage}`, { isError: true });
    return;
  }

  const leafletConfig = result.leaflet_config;
  if (!leafletConfig || !leafletConfig.bounds) {
    ui.setStatus("Error: Invalid inference response.", { isError: true });
    return;
  }

  try {
    // Always clear old masks on the target map before rendering a new one
    targetMapController.clearMask();

    const metadata = result.metadata ?? {};
    const processed = metadata.tiles_processed ?? 0;
    const displayModelName = context.modelLabel ?? newModel;
    const inputLabel = context.fileName ?? metadata.input_file ?? "uploaded input";
    const overlayLabel = `${displayModelName} · ${inputLabel}`;

    targetMapController.renderMask(leafletConfig, {
      opacity: context.opacity,
      fit: true, // Let each map fit to its own bounds
      layerName: overlayLabel,
      metadata,
    });
    
    const activeMaskToggle = toggles.maskToggle?.checked ?? true;
    targetMapController.toggleMask(activeMaskToggle);
    ui.setStatus(`Done · ${processed} tiles (${displayModelName})`);
  } catch (error) {
    console.error("Failed to render inference result", error);
    const message = error instanceof Error ? error.message : String(error);
    ui.setStatus(`Error: ${message}`, { isError: true });
  }
}

function initialise() {
  const statusElement = selectElement("#status");
  const progressIndicator = selectElement("#progress-indicator");
  const progressBarFill = selectElement("#progress-bar-fill");
  const progressLabel = selectElement("#progress-message");
  const uploadButton = selectElement("#upload-btn");
  const fileNameDisplay = selectElement("#file-name-display");

  const ui = createUIController({
    statusElement,
    progressIndicator,
    progressBarFill,
    progressLabel,
    uploadButton,
    fileNameDisplay,
  });

  // Create the primary map controller
  mapControllerA = createMapController({
    containerId: "leaflet-map-a",
    onStatusUpdate: (message) => ui.setStatus(message),
  });

  const modelSelect = selectElement("#model-select");
  const modalitySelect = selectElement("#modality-select");
  wireModelModalityBehavior(modelSelect, modalitySelect);

  const elements = {
    fileInput: selectElement("#file-input"),
    uploadButton,
    modelSelect,
    modalitySelect,
    opacitySlider: selectElement("#opacity"),
    toggleInput: document.querySelector("#toggle-input"),
    toggleMask: document.querySelector("#toggle-mask"),
  };

  // Centralize map control listeners
  elements.opacitySlider.addEventListener("input", () => {
    const opacity = Number(elements.opacitySlider.value);
    mapControllerA?.updateMaskOpacity(opacity);
    mapControllerB?.updateMaskOpacity(opacity);
  });
  elements.toggleInput.addEventListener("change", () => {
    const visible = elements.toggleInput.checked;
    mapControllerA?.toggleInput(visible);
    mapControllerB?.toggleInput(visible);
  });
  elements.toggleMask.addEventListener("change", () => {
    const visible = elements.toggleMask.checked;
    mapControllerA?.toggleMask(visible);
    mapControllerB?.toggleMask(visible);
  });

  bindHeroInteractions({
    navLinks: document.querySelectorAll(".nav-link"),
    navContainer: document.querySelector(".floating-nav"),
    navHandle: document.querySelector(".floating-nav .nav-handle"),
  });

  initializeUploadWorkflow({
    elements,
    ui,
    mapController: mapControllerA,
    onResult: (result, context) => {
      handleAnalysisResult({
        result,
        context,
        ui,
        toggles: {
          maskToggle: elements.toggleMask,
        },
      });
    },
    onError: (message) => {
      console.warn("Upload workflow error", message);
    },
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialise, { once: true });
} else {
  initialise();
}