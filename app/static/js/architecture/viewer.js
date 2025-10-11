import { DEFAULT_SCALE } from "./modules.js";

const FALLBACK_STATE = {
  title: "Hover a module",
  summary: "Highlight a block to read its tensor size and layers.",
  details: [],
};

function applyModelScale(scale) {
  const resolved = {
    base: typeof scale?.base === "number" ? scale.base : DEFAULT_SCALE.base,
    medium: typeof scale?.medium === "number" ? scale.medium : DEFAULT_SCALE.medium,
    small: typeof scale?.small === "number" ? scale.small : DEFAULT_SCALE.small,
  };

  const style = document.documentElement.style;
  style.setProperty("--model-scale", String(resolved.base));
  style.setProperty("--model-scale-medium", String(resolved.medium));
  style.setProperty("--model-scale-small", String(resolved.small));
}

export function createArchitectureViewer({
  registry,
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
  assetBase = "/static/",
  defaultState = FALLBACK_STATE,
  initialModelId,
}) {
  if (!registry || !svgObject || !infoPanel || !infoTitle || !infoSummary || !infoStats || !infoDetails || !infoMedia) {
    throw new Error("createArchitectureViewer requires registry, svgObject, and info panel nodes");
  }

  let currentModelId = null;
  let currentModules = [];
  let activeModule = null;
  let svgRoot = null;
  let overlayLayer = null;
  const elementToModule = new Map();
  let cleanupInteractiveBindings = () => {};

  const assetPrefix = assetBase.endsWith("/") ? assetBase : `${assetBase}/`;

  const prefixAssetPath = (path) => {
    if (!path) return path;
    return path.startsWith("/") ? path : `${assetPrefix}${path}`;
  };

  function resetInfo() {
    infoTitle.textContent = defaultState.title;
    infoSummary.textContent = defaultState.summary;
    infoStats.innerHTML = "";
    infoDetails.innerHTML = "";
    infoMedia.innerHTML = "";
    infoMedia.hidden = true;
  infoPanel.classList.remove("has-media");
  const container = infoPanel.closest("[data-architecture-viewer]");
  container?.classList.remove("has-media");
    infoPanel.classList.remove("is-pinned");

    for (const detail of defaultState.details) {
      const li = document.createElement("li");
      li.textContent = detail;
      infoDetails.appendChild(li);
    }
  }

  function renderModule(module, pinned) {
    infoTitle.textContent = module.title;
    infoSummary.textContent = module.summary;
    infoStats.innerHTML = "";
    infoDetails.innerHTML = "";

    const container = infoPanel.closest("[data-architecture-viewer]");

    if (module.image) {
      const img = document.createElement("img");
      img.src = prefixAssetPath(module.image);
      img.alt = module.imageAlt ?? "";
      infoMedia.innerHTML = "";
      infoMedia.appendChild(img);
      infoMedia.hidden = false;
      infoPanel.classList.add("has-media");
      container?.classList.add("has-media");
    } else {
      infoMedia.innerHTML = "";
      infoMedia.hidden = true;
      infoPanel.classList.remove("has-media");
      container?.classList.remove("has-media");
    }

    module.stats.forEach((stat) => {
      const dt = document.createElement("dt");
      dt.textContent = stat.label;
      const dd = document.createElement("dd");
      dd.textContent = stat.value;
      infoStats.appendChild(dt);
      infoStats.appendChild(dd);
    });

    module.details.forEach((detail) => {
      const li = document.createElement("li");
      li.textContent = detail;
      infoDetails.appendChild(li);
    });

    infoPanel.classList.toggle("is-pinned", Boolean(pinned));
    infoPanel.scrollTop = 0;
  }

  function applyVisualState(module, state) {
    if (!module.targets) return;

    const isActive = state === "active";
    const fillColor = isActive ? "#9f3f16" : "#c06038";
    const fontWeight = state === "idle" ? "" : "700";

    module.targets.forEach((target) => {
      if (!target.dataset.originalFillCaptured) {
        const ownerDocument = target.ownerDocument;
        const view = ownerDocument?.defaultView ?? null;
        const computed = view ? view.getComputedStyle(target) : null;
        const originalFill = target.style?.fill ? target.style.fill : computed?.fill ?? "";
        const originalStroke = target.style?.stroke ? target.style.stroke : computed?.stroke ?? "";
        if (originalFill) target.dataset.originalFill = originalFill;
        if (originalStroke) target.dataset.originalStroke = originalStroke;
        target.dataset.originalFillCaptured = "true";
      }

      target.style.cursor = "pointer";
      target.style.transition = "fill 0.2s ease, font-weight 0.2s ease";

      if (state === "idle") {
        if (target.dataset.originalFill) {
          target.style.fill = target.dataset.originalFill;
        } else {
          target.style.removeProperty("fill");
        }
        target.style.fontWeight = "";
      } else {
        target.style.fill = fillColor;
        target.style.fontWeight = fontWeight;
      }
    });

    if (module.overlay) {
      if (state === "idle") {
        module.overlay.style.opacity = "0";
        module.overlay.style.strokeWidth = "0.6";
      } else {
        module.overlay.style.opacity = isActive ? "0.5" : "0.28";
        module.overlay.style.strokeWidth = isActive ? "0.9" : "0.6";
      }
    }
  }

  function clearActive() {
    if (activeModule) {
      applyVisualState(activeModule, "idle");
      activeModule = null;
    }
    resetInfo();
  }

  function findModuleForNode(node) {
    let current = node;
    while (current) {
      const match = elementToModule.get(current);
      if (match) return match;
      current = current.parentNode;
    }
    return null;
  }

  function computeUnionBBox(targets, margin) {
    if (!svgRoot || !targets.length) return null;

    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    const point = svgRoot.createSVGPoint();

    targets.forEach((el) => {
      const bbox = el.getBBox?.();
      const matrix = el.getCTM?.();
      if (!bbox) return;

      const corners = [
        { x: bbox.x, y: bbox.y },
        { x: bbox.x + bbox.width, y: bbox.y },
        { x: bbox.x, y: bbox.y + bbox.height },
        { x: bbox.x + bbox.width, y: bbox.y + bbox.height },
      ];

      corners.forEach((corner) => {
        point.x = corner.x;
        point.y = corner.y;
        const transformed = matrix ? point.matrixTransform(matrix) : corner;
        if (transformed.x < minX) minX = transformed.x;
        if (transformed.y < minY) minY = transformed.y;
        if (transformed.x > maxX) maxX = transformed.x;
        if (transformed.y > maxY) maxY = transformed.y;
      });
    });

    if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
      return null;
    }

    const inflate = margin ?? 1.4;
    return {
      x: minX - inflate,
      y: minY - inflate,
      width: maxX - minX + inflate * 2,
      height: maxY - minY + inflate * 2,
    };
  }

  function createOverlay(bounds) {
    if (!svgRoot || !overlayLayer || !bounds) return null;

    const rect = svgRoot.ownerDocument.createElementNS(svgRoot.namespaceURI, "rect");
    rect.setAttribute("x", bounds.x.toFixed(2));
    rect.setAttribute("y", bounds.y.toFixed(2));
    rect.setAttribute("width", bounds.width.toFixed(2));
    rect.setAttribute("height", bounds.height.toFixed(2));
    rect.setAttribute("rx", "2.8");
    rect.setAttribute("ry", "2.8");
    rect.setAttribute("fill", "#c06038");
    rect.setAttribute("fill-opacity", "0.18");
    rect.setAttribute("stroke", "#c06038");
    rect.setAttribute("stroke-opacity", "0.85");
    rect.setAttribute("stroke-dasharray", "1.5 2.2");
    rect.setAttribute("stroke-width", "0.6");
    rect.style.transition = "opacity 0.2s ease, stroke-width 0.2s ease";
    rect.style.pointerEvents = "visiblePainted";
    rect.style.opacity = "0";
    overlayLayer.appendChild(rect);
    return rect;
  }

  function bindInteractiveTarget(node, module) {
    if (!node) return;

    elementToModule.set(node, module);

    const ensureOriginalFill = () => {
      if (node.dataset.originalFillCaptured) return;
      const ownerDocument = node.ownerDocument;
      const view = ownerDocument?.defaultView ?? null;
      const computed = view ? view.getComputedStyle(node) : null;
      const originalFill = node.style?.fill ? node.style.fill : computed?.fill ?? "";
      const originalStroke = node.style?.stroke ? node.style.stroke : computed?.stroke ?? "";
      if (originalFill) node.dataset.originalFill = originalFill;
      if (originalStroke) node.dataset.originalStroke = originalStroke;
      node.dataset.originalFillCaptured = "true";
    };

    ensureOriginalFill();
    node.style.cursor = "pointer";
    node.style.touchAction = "manipulation";

    const handleEnter = () => {
      if (activeModule?.id === module.id) return;
      applyVisualState(module, "hover");
      renderModule(module, false);
    };

    const handleLeave = () => {
      if (activeModule?.id === module.id) return;
      applyVisualState(module, "idle");
      if (!activeModule) resetInfo();
    };

    const handleClick = (event) => {
      event.preventDefault();
      event.stopPropagation();

      if (activeModule?.id === module.id) {
        clearActive();
        return;
      }

      if (activeModule) {
        applyVisualState(activeModule, "idle");
      }

      activeModule = module;
      applyVisualState(module, "active");
      renderModule(module, true);
    };

    node.addEventListener("pointerenter", handleEnter);
    node.addEventListener("pointerleave", handleLeave);
    node.addEventListener("click", handleClick);

    module.listeners.push(() => {
      node.removeEventListener("pointerenter", handleEnter);
      node.removeEventListener("pointerleave", handleLeave);
      node.removeEventListener("click", handleClick);
    });
  }

  function detachInteractiveBindings() {
    cleanupInteractiveBindings();
    cleanupInteractiveBindings = () => {};
    elementToModule.clear();
  }

  function attachModuleInteractions(modules) {
    detachInteractiveBindings();

    if (!svgRoot || !modules.length) return;

    if (overlayLayer) {
      overlayLayer.remove();
      overlayLayer = null;
    }

    overlayLayer = svgRoot.ownerDocument.createElementNS(svgRoot.namespaceURI, "g");
    overlayLayer.setAttribute("id", "module-overlays");
    overlayLayer.setAttribute("pointer-events", "visiblePainted");
    svgRoot.appendChild(overlayLayer);

    modules.forEach((module) => {
      module.targets = module.targetIds
        .map((id) => svgRoot.getElementById(id))
        .filter(Boolean);
      module.overlay = undefined;
      module.listeners = [];

      if (!module.targets.length) {
        console.warn("Interactive module skipped", module.id, module.targetIds);
        return;
      }

      const bounds = computeUnionBBox(module.targets, module.margin);
      if (bounds) {
        const overlay = createOverlay(bounds);
        if (overlay) {
          module.overlay = overlay;
          bindInteractiveTarget(overlay, module);
        }
      }

      module.targets.forEach((target) => {
        bindInteractiveTarget(target, module);
      });
    });

    const handlePointerDown = (event) => {
      const module = findModuleForNode(event.target);
      if (!module && activeModule) {
        clearActive();
      }
    };

    svgRoot.addEventListener("pointerdown", handlePointerDown);

    cleanupInteractiveBindings = () => {
      modules.forEach((module) => {
        module.listeners?.forEach((cleanup) => cleanup());
        module.listeners = [];
      });
      svgRoot.removeEventListener("pointerdown", handlePointerDown);
    };
  }

  function activateModel(modelId) {
    if (currentModelId === modelId) return;

    const config = registry[modelId];
    if (!config) {
      console.warn("Unknown architecture model", modelId);
      return;
    }

    applyModelScale(config.scale);
    clearActive();
    detachInteractiveBindings();

    currentModelId = config.id;
    currentModules = config.buildModules();

    if (panelHeading) {
      panelHeading.textContent = config.panelTitle;
    }

    if (modelSelect && modelSelect.value !== currentModelId) {
      modelSelect.value = currentModelId;
    }

    svgObject.setAttribute("aria-label", config.ariaLabel);

    if (loadingIndicator) {
      loadingIndicator.style.display = "block";
      loadingIndicator.textContent = "Loading architecture…";
    }

    svgObject.classList.remove("loaded");
    svgObject.setAttribute("data", prefixAssetPath(config.svgPath));
  }

  const handleSvgLoad = () => {
    if (loadingIndicator) {
      loadingIndicator.style.display = "none";
    }

    svgObject.classList.add("loaded");
    const doc = svgObject.contentDocument;
    if (!doc) {
      console.error("Unable to access embedded SVG document. Ensure the file is served over HTTP.");
      return;
    }

    svgRoot = doc.querySelector("svg");
    if (!svgRoot) return;

    // Ensure SVG fills container properly
    svgRoot.setAttribute("width", "100%");
    svgRoot.setAttribute("height", "100%");
    svgRoot.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svgRoot.style.display = "block";

    attachModuleInteractions(currentModules);
    resetInfo();
  };

  const handleSvgError = () => {
    if (loadingIndicator) {
      loadingIndicator.textContent = "Failed to load SVG";
      loadingIndicator.style.display = "block";
    }
    svgObject.classList.remove("loaded");
  };

  const handleEscape = (event) => {
    if (event.key === "Escape") {
      clearActive();
    }
  };

  svgObject.addEventListener("load", handleSvgLoad);
  svgObject.addEventListener("error", handleSvgError);
  document.addEventListener("keydown", handleEscape);

  let handleModelChange = null;
  if (modelSelect) {
    handleModelChange = (event) => {
      activateModel(event.target.value);
    };
    modelSelect.addEventListener("change", handleModelChange);
  }

  resetInfo();

  const startupModelId = initialModelId ?? modelSelect?.value ?? Object.keys(registry)[0];
  if (startupModelId) {
    activateModel(startupModelId);
  }

  function destroy() {
    detachInteractiveBindings();
    svgObject.removeEventListener("load", handleSvgLoad);
    svgObject.removeEventListener("error", handleSvgError);
    document.removeEventListener("keydown", handleEscape);
    if (modelSelect && handleModelChange) {
      modelSelect.removeEventListener("change", handleModelChange);
    }
  }

  return {
    activateModel,
    destroy,
  };
}