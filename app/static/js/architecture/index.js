import { MODEL_REGISTRY } from "./modules.js";
import { createArchitectureViewer } from "./viewer.js";

const ROOT_SELECTOR = "[data-architecture-viewer]";

function populateModelOptions(selectEl) {
  if (!selectEl) return;
  selectEl.innerHTML = "";

  Object.values(MODEL_REGISTRY).forEach((model) => {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = model.label;
    selectEl.appendChild(option);
  });
}

function resolveElement(root, token) {
  const el = root.querySelector(`[data-architecture="${token}"]`);
  if (!el) {
    throw new Error(`Architecture viewer element missing: ${token}`);
  }
  return el;
}

export function initArchitectureViewer({
  root = document.querySelector(ROOT_SELECTOR),
  assetBase = "/static/",
  initialModelId,
} = {}) {
  if (!root) return null;
  if (root.dataset.architectureInitialised === "true") return null;

  const svgObject = resolveElement(root, "svg-object");
  const loadingIndicator = resolveElement(root, "loading");
  const infoPanel = resolveElement(root, "info-panel");
  const infoTitle = resolveElement(root, "info-title");
  const infoSummary = resolveElement(root, "info-summary");
  const infoStats = resolveElement(root, "info-stats");
  const infoDetails = resolveElement(root, "info-details");
  const infoMedia = resolveElement(root, "info-media");
  const panelHeading = resolveElement(root, "panel-heading");
  const modelSelect = resolveElement(root, "model-select");

  populateModelOptions(modelSelect);

  const viewer = createArchitectureViewer({
    registry: MODEL_REGISTRY,
    svgObject,
    loadingIndicator,
    infoPanel,
    infoTitle,
    infoSummary,
    infoStats,
    infoDetails,
    infoMedia,
    panelHeading,
    modelSelect,
    assetBase,
    initialModelId,
  });

  root.dataset.architectureInitialised = "true";
  return viewer;
}

export function mountArchitectureViewerLazy({
  root = document.querySelector(ROOT_SELECTOR),
  assetBase = "/static/",
  initialModelId,
  threshold = 0.1,
} = {}) {
  if (!root) return null;

  if (!("IntersectionObserver" in window)) {
    return initArchitectureViewer({ root, assetBase, initialModelId });
  }

  let viewerInstance = null;
  const observer = new IntersectionObserver((entries) => {
    const entry = entries.find((e) => e.isIntersecting);
    if (entry && !viewerInstance) {
      viewerInstance = initArchitectureViewer({ root, assetBase, initialModelId });
      observer.disconnect();
    }
  }, { threshold });

  observer.observe(root);
  return {
    disconnect() {
      observer.disconnect();
    },
    get viewer() {
      return viewerInstance;
    },
  };
}