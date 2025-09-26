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

function handleInferenceResult({
  result,
  mapController,
  ui,
  toggles,
  context,
}) {
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
    const metadata = result.metadata ?? {};
    const processed = metadata.tiles_processed ?? 0;
    const modelName = metadata.model_type ?? context.model;
    const displayModelName = context.modelLabel ?? modelName;
    const inputLabel = context.fileName ?? metadata.input_file ?? "uploaded input";
    const overlayLabel = `${displayModelName} · ${inputLabel}`;

    mapController.renderMask(leafletConfig, {
      opacity: context.opacity,
      fit: true,
      layerName: overlayLabel,
      metadata,
    });
    mapController.fitToBounds(leafletConfig.bounds);

    const activeMaskToggle = toggles.maskToggle?.checked ?? true;
    mapController.toggleMask(activeMaskToggle);
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

  const mapController = createMapController({
    containerId: "leaflet-map",
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

  bindHeroInteractions({
    navLinks: document.querySelectorAll(".nav-link"),
    navContainer: document.querySelector(".floating-nav"),
    navHandle: document.querySelector(".floating-nav .nav-handle"),
  });

  initializeUploadWorkflow({
    elements,
    ui,
    mapController,
    onResult: (result, context) => {
      handleInferenceResult({
        result,
        mapController,
        ui,
        toggles: {
          maskToggle: elements.toggleMask,
        },
        context,
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
