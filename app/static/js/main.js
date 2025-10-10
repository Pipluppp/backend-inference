import { createMapController } from "./map.js";
import { bindHeroInteractions, createUIController, wireModelModalityBehavior } from "./ui.js";
import { initializeUploadWorkflow } from "./upload.js";

// --- Global state ---
let mapControllers = [];
const generatedOverlays = new Map(); // Key: overlayId, Value: { name, url, bounds, metadata }
let nextOverlayId = 0;
let isSyncing = false;
let ui;
// ---

function selectElement(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Element not found for selector: ${selector}`);
  }
  return element;
}

function handleInferenceResult({
  result,
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

    const overlayId = `overlay-${nextOverlayId++}`;
    const overlayConfig = {
      id: overlayId,
      name: overlayLabel,
      url: leafletConfig.tiff_url,
      bounds: [[leafletConfig.bounds.south, leafletConfig.bounds.west], [leafletConfig.bounds.north, leafletConfig.bounds.east]],
      metadata: metadata,
    };
    generatedOverlays.set(overlayId, overlayConfig);

    mapControllers.forEach((controller, index) => {
      const newLayer = L.imageOverlay(overlayConfig.url, overlayConfig.bounds, {
        opacity: context.opacity,
        pane: "rasterPane",
        interactive: false,
      });
      controller.addNamedOverlay(overlayConfig.name, newLayer, {
        fit: index === 0, // Only fit bounds on the first map
      });
    });

    const activeMaskToggle = toggles.maskToggle?.checked ?? true;
    mapControllers.forEach(c => c.toggleMask(activeMaskToggle));
    ui.setStatus(`Done · ${processed} tiles (${displayModelName})`);
  } catch (error) {
    console.error("Failed to render inference result", error);
    const message = error instanceof Error ? error.message : String(error);
    ui.setStatus(`Error: ${message}`, { isError: true });
  }
}

// --- Map Syncing Logic ---
const syncHandler = function(e) {
    if (isSyncing) return;
    isSyncing = true;
    
    const sourceMap = e.target;
    const center = sourceMap.getCenter();
    const zoom = sourceMap.getZoom();

    mapControllers.forEach(controller => {
        if (controller.mapInstance !== sourceMap) {
            controller.mapInstance.setView(center, zoom, { animate: false });
        }
    });

    isSyncing = false;
};

function syncMaps() {
    mapControllers.forEach(controller => {
        controller.mapInstance.on('move zoom', syncHandler);
    });
}

function unsyncMaps() {
    mapControllers.forEach(controller => {
        controller.mapInstance.off('move zoom', syncHandler);
    });
}
// ---

function updateMapLayout(count) {
    const container = selectElement("#map-view-container");
    container.innerHTML = '';
    container.dataset.mapCount = count;
    
    unsyncMaps();
    mapControllers.forEach(controller => controller.teardown());
    mapControllers = [];

    for (let i = 0; i < count; i++) {
        const mapId = `map-instance-${i}`;
        const mapDiv = document.createElement('div');
        mapDiv.id = mapId;
        mapDiv.className = 'map-instance';
        container.appendChild(mapDiv);

        const controller = createMapController({
            containerId: mapId,
            onStatusUpdate: (msg) => { if (i === 0 && ui) ui.setStatus(msg) },
        });
        mapControllers.push(controller);
    }
    
    const opacitySlider = selectElement("#opacity");
    generatedOverlays.forEach(overlayConfig => {
        mapControllers.forEach(controller => {
            const newLayer = L.imageOverlay(overlayConfig.url, overlayConfig.bounds, {
                opacity: Number(opacitySlider.value),
                pane: "rasterPane",
                interactive: false,
            });
            controller.addNamedOverlay(overlayConfig.name, newLayer);
        });
    });
    
    if (selectElement('#sync-maps-toggle').checked) {
        syncMaps();
    }
    
    setTimeout(() => {
        mapControllers.forEach(controller => controller.invalidateSize());
    }, 350); // Delay matches CSS transition for the panel
}


function initialise() {
  const statusElement = selectElement("#status");
  const progressIndicator = selectElement("#progress-indicator");
  const progressBarFill = selectElement("#progress-bar-fill");
  const progressLabel = selectElement("#progress-message");
  const uploadButton = selectElement("#upload-btn");
  const fileNameDisplay = selectElement("#file-name-display");

  ui = createUIController({
    statusElement,
    progressIndicator,
    progressBarFill,
    progressLabel,
    uploadButton,
    fileNameDisplay,
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
    syncMapsToggle: selectElement("#sync-maps-toggle"),
    clearHistoryBtn: selectElement("#clear-history-btn"),
    mapCountSelect: selectElement("#map-count-select"),
    mapSection: selectElement("#map-section"),
    panelToggleBtn: selectElement("#panel-toggle-btn"),
    toggleQCBoundary: selectElement("#toggle-qc-boundary"),
  };

  bindHeroInteractions({
    navLinks: document.querySelectorAll(".nav-link"),
    navContainer: document.querySelector(".floating-nav"),
    navHandle: document.querySelector(".floating-nav .nav-handle"),
  });

  // --- UI Event Listeners ---
  elements.mapCountSelect.addEventListener('change', (e) => {
      const count = parseInt(e.target.value, 10);
      updateMapLayout(count);
  });

  elements.syncMapsToggle.addEventListener('change', (e) => {
    if (e.target.checked) syncMaps();
    else unsyncMaps();
  });

  elements.clearHistoryBtn.addEventListener('click', () => {
    generatedOverlays.clear();
    nextOverlayId = 0;
    mapControllers.forEach(controller => controller.clearAllOverlays());
    ui.setStatus('Prediction history cleared.');
  });
  
  elements.panelToggleBtn.addEventListener('click', () => {
    const isCollapsed = elements.mapSection.classList.toggle('is-panel-collapsed');
    elements.panelToggleBtn.setAttribute('aria-expanded', String(!isCollapsed));
    setTimeout(() => {
      mapControllers.forEach(c => c.invalidateSize());
    }, 350);
  });

  elements.toggleQCBoundary.addEventListener('change', (e) => {
    mapControllers.forEach(c => c.toggleQCBoundary(e.target.checked));
  });

  updateMapLayout(1);

  initializeUploadWorkflow({
    elements,
    ui,
    mapController: {
        updateMaskOpacity: (opacity) => mapControllers.forEach(c => c.updateMaskOpacity(opacity)),
        setInputLayer: (layer) => mapControllers[0]?.setInputLayer(layer),
        toggleInput: (visible) => mapControllers[0]?.toggleInput(visible),
        toggleMask: (visible) => mapControllers.forEach(c => c.toggleMask(visible)),
        toggleQCBoundary: (visible) => mapControllers.forEach(c => c.toggleQCBoundary(visible)), 
    },
    onResult: (result, context) => {
      handleInferenceResult({
        result,
        toggles: { maskToggle: elements.toggleMask },
        context,
      });
    },
    onError: (message) => console.warn("Upload workflow error", message),
  });


}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialise, { once: true });
} else {
  initialise();
}