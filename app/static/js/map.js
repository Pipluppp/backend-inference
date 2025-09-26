const DEFAULT_VIEW = [14.65, 121.05];
const DEFAULT_ZOOM = 11;
const RASTER_PANE = "rasterPane";

function ensureGoogleMapsReady(timeout = 8000) {
  return new Promise((resolve, reject) => {
    if (window.google && window.google.maps) {
      resolve();
      return;
    }

    let waited = 0;
    const interval = window.setInterval(() => {
      if (window.google && window.google.maps) {
        window.clearInterval(interval);
        resolve();
        return;
      }

      waited += 200;
      if (waited >= timeout) {
        window.clearInterval(interval);
        reject(new Error("Google Maps API not available"));
      }
    }, 200);
  });
}

async function createBaseLayers(map, onStatusUpdate) {
  let baseLayers = {};
  const voyager = L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
    {
      maxZoom: 20,
      subdomains: "abcd",
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
    },
  );

  try {
    await ensureGoogleMapsReady();
    const satellite = L.gridLayer
      .googleMutant({ maxZoom: 24, type: "satellite" })
      .addTo(map);
    baseLayers = {
      "Satellite (Google)": satellite,
    };
  } catch (error) {
    console.warn("Google Maps not ready, using OSM fallback", error);
    const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);
    baseLayers = { OSM: osm };
    if (onStatusUpdate) {
      onStatusUpdate("Google Maps unavailable. Using OSM base layer.");
    }
  }

  baseLayers["Voyager (Carto)"] = voyager;

  const layerControl = L.control.layers(baseLayers, {}, {
    collapsed: true,
    position: "topright",
  }).addTo(map);

  return layerControl;
}

export function createMapController({
  containerId,
  onStatusUpdate,
} = {}) {
  if (!containerId) {
    throw new Error("Map container id is required");
  }

  const map = L.map(containerId, { zoomSnap: 0.25, zoomControl: false }).setView(
    DEFAULT_VIEW,
    DEFAULT_ZOOM,
  );
  map.createPane(RASTER_PANE);
  map.getPane(RASTER_PANE).style.zIndex = 650;

  const defaultFlyPadding = L.point(48, 48);
  const defaultFlyOptions = {
    paddingTopLeft: defaultFlyPadding,
    paddingBottomRight: defaultFlyPadding,
    duration: 1.1,
    easeLinearity: 0.25,
  };

  const pendingOverlayRegistrations = [];
  let layerControl = null;
  createBaseLayers(map, onStatusUpdate)
    .then((control) => {
      layerControl = control;
      while (pendingOverlayRegistrations.length > 0) {
        const { layer, name } = pendingOverlayRegistrations.shift();
        layerControl.addOverlay(layer, name);
      }
    })
    .catch((error) => {
      console.error("Failed to initialise base layers", error);
    });

  let maskVisible = true;
  let currentBounds = null;
  let currentOpacity = 0.6;

  let inputLayer = null;
  let inputVisible = true;

  const overlays = new Map();
  let overlayCounter = 0;
  let latestOverlayId = null;
  let isGlobalMaskToggleInProgress = false;

  function removeLayerSafely(layer) {
    if (layer && map.hasLayer(layer)) {
      map.removeLayer(layer);
    }
  }

  function addLayerSafely(layer) {
    if (layer && !map.hasLayer(layer)) {
      layer.addTo(map);
    }
  }

  function registerOverlayWithControl(layer, name) {
    if (layerControl) {
      layerControl.addOverlay(layer, name);
    } else {
      pendingOverlayRegistrations.push({ layer, name });
    }
  }

  function findOverlayByLayer(layerInstance) {
    for (const overlay of overlays.values()) {
      if (overlay.layer === layerInstance) {
        return overlay;
      }
    }
    return null;
  }

  map.on("overlayadd", (event) => {
    const overlay = findOverlayByLayer(event.layer);
    if (overlay) {
      overlay.isActive = true;
      if (!isGlobalMaskToggleInProgress) {
        overlay.shouldDisplay = true;
      }
    }
  });

  map.on("overlayremove", (event) => {
    const overlay = findOverlayByLayer(event.layer);
    if (overlay) {
      overlay.isActive = false;
      if (!isGlobalMaskToggleInProgress) {
        overlay.shouldDisplay = false;
      }
    }
  });

  return {
    renderMask(leafletConfig, options = {}) {
      if (!leafletConfig || !leafletConfig.bounds || !leafletConfig.tiff_url) {
        throw new Error("Invalid mask configuration");
      }

      const { bounds, tiff_url: url } = leafletConfig;
      currentBounds = [[bounds.south, bounds.west], [bounds.north, bounds.east]];
      currentOpacity = Number(options.opacity ?? currentOpacity ?? 0.6);

      const overlayId = ++overlayCounter;
      const layerName = options.layerName || `Inference ${overlayId}`;
      const overlayMetadata = options.metadata ?? {};

      const overlayLayer = L.imageOverlay(url, currentBounds, {
        opacity: currentOpacity,
        pane: RASTER_PANE,
        interactive: false,
      });

      const overlayRecord = {
        id: overlayId,
        name: layerName,
        layer: overlayLayer,
        metadata: overlayMetadata,
        shouldDisplay: true,
        isActive: false,
      };

      overlays.set(overlayId, overlayRecord);
      latestOverlayId = overlayId;

      registerOverlayWithControl(overlayLayer, layerName);

      if (maskVisible) {
        addLayerSafely(overlayLayer);
        overlayRecord.isActive = true;
      }

      if (options.fit) {
        this.fitToBounds(bounds);
      }
    },

    clearMask() {
      isGlobalMaskToggleInProgress = true;
      try {
        overlays.forEach((overlay) => {
          removeLayerSafely(overlay.layer);
          if (layerControl) {
            layerControl.removeLayer(overlay.layer);
          }
        });
      } finally {
        isGlobalMaskToggleInProgress = false;
      }
      overlays.clear();
      pendingOverlayRegistrations.length = 0;
      latestOverlayId = null;
      currentBounds = null;
    },

    updateMaskOpacity(opacity) {
      currentOpacity = Number(opacity);
      overlays.forEach((overlay) => {
        overlay.layer.setOpacity(currentOpacity);
      });
    },

    toggleMask(visible) {
      maskVisible = Boolean(visible);
      isGlobalMaskToggleInProgress = true;
      try {
        overlays.forEach((overlay) => {
          if (maskVisible) {
            if (overlay.shouldDisplay) {
              addLayerSafely(overlay.layer);
            }
          } else {
            removeLayerSafely(overlay.layer);
          }
        });
      } finally {
        isGlobalMaskToggleInProgress = false;
      }
    },

    setInputLayer(layerInstance) {
      removeLayerSafely(inputLayer);
      inputLayer = layerInstance;
      if (inputVisible && inputLayer) {
        addLayerSafely(inputLayer);
      }
    },

    toggleInput(visible) {
      inputVisible = Boolean(visible);
      if (!inputLayer) return;
      if (inputVisible) {
        addLayerSafely(inputLayer);
      } else {
        removeLayerSafely(inputLayer);
      }
    },

    fitToBounds(boundsObject, options = {}) {
      if (!boundsObject && !currentBounds) return;
      const bounds = boundsObject
        ? [[boundsObject.south, boundsObject.west], [boundsObject.north, boundsObject.east]]
        : currentBounds;
      if (bounds) {
        const flyOptions = {
          ...defaultFlyOptions,
          ...(options.flyOptions ?? {}),
        };

        try {
          map.flyToBounds(bounds, flyOptions);
        } catch (error) {
          console.warn("Smooth flyToBounds failed, falling back to fitBounds", error);
          map.fitBounds(bounds, flyOptions);
        }
      }
    },

    get mapInstance() {
      return map;
    },
  };
}
