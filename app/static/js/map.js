const DEFAULT_VIEW = [14.65, 121.05];
const DEFAULT_ZOOM = 11;
const RASTER_PANE = "rasterPane";
const QC_BOUNDARY_PANE = "qcBoundaryPane";

// --- Custom Leaflet Control for Info Labels ---
const InfoLabelControl = L.Control.extend({
    onAdd: function(map) {
        this._div = L.DomUtil.create('div', 'leaflet-control-infolabel');
        this.update();
        return this._div;
    },
    update: function(text = '') {
        if (this._div) {
            this._div.innerHTML = text ? `<span>${text}</span>` : '';
            this._div.style.display = text ? 'block' : 'none';
        }
    }
});
L.control.infoLabel = function(opts) { return new InfoLabelControl(opts); };
// ---

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
  map.getPane(RASTER_PANE).style.zIndex = 450;

  map.createPane(QC_BOUNDARY_PANE);
  map.getPane(QC_BOUNDARY_PANE).style.zIndex = 500; 
  map.getPane(QC_BOUNDARY_PANE).style.pointerEvents = 'none'; 

  let qcBoundaryLayer = null;

  const qcBoundaryStyle = {
      "color": "#ffffff",
      "weight": 2.5,
      "opacity": 0.75,
      "fillOpacity": 0.05,
      "pane": QC_BOUNDARY_PANE
  };

  // Fetch the GeoJSON data
  fetch('/static/map/qc-boundary-merged.geojson')
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok for qc-boundary.geojson');
        }
        return response.json();
    })
    .then(data => {
        qcBoundaryLayer = L.geoJSON(data, { style: qcBoundaryStyle });
        // Optionally add it to the map by default if the checkbox is checked
        const toggle = document.querySelector('#toggle-qc-boundary');
        if (toggle && toggle.checked) {
            qcBoundaryLayer.addTo(map);
        }
    })
    .catch(error => {
        console.error('Error loading or parsing qc-boundary.geojson:', error);
        if (onStatusUpdate) onStatusUpdate("Could not load QC boundary.");
    });

  const infoLabel = L.control.infoLabel({ position: 'bottomright' }).addTo(map);

  const defaultFlyPadding = L.point(48, 48);
  const defaultFlyOptions = {
    paddingTopLeft: defaultFlyPadding,
    paddingBottomRight: defaultFlyPadding,
    duration: 1.1,
    easeLinearity: 0.25,
  };

  const pendingOverlayRegistrations = [];
  let layerControl = null;

  function registerOverlayWithControl(layer, name) {
    if (layerControl) {
        layerControl.addOverlay(layer, name);
    } else {
        pendingOverlayRegistrations.push({ layer, name });
    }
  }

  createBaseLayers(map, onStatusUpdate)
    .then((control) => { 
      layerControl = control;
      while (pendingOverlayRegistrations.length > 0) {
        const { layer, name } = pendingOverlayRegistrations.shift();
        layerControl.addOverlay(layer, name);
      }
    })
    .catch((error) => console.error("Failed to initialise base layers", error));

  let maskVisible = true;
  let inputLayer = null;
  let inputVisible = true;
  const overlays = new Map();
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

  function updateActiveLabel() {
    let activeOverlayName = '';
    const activeLayers = Array.from(overlays.entries()).reverse();
    for (const [layer, state] of activeLayers) {
        if (map.hasLayer(layer)) {
            activeOverlayName = state.name;
            break;
        }
    }
    infoLabel.update(activeOverlayName);
  }

  map.on("overlayadd", (event) => {
    const overlay = overlays.get(event.layer);
    if (overlay) {
        if (!isGlobalMaskToggleInProgress) overlay.shouldDisplay = true;
    }
    updateActiveLabel();
  });

  map.on("overlayremove", (event) => {
    const overlay = overlays.get(event.layer);
    if (overlay) {
        if (!isGlobalMaskToggleInProgress) overlay.shouldDisplay = false;
    }
    updateActiveLabel();
  });

  return {
    addNamedOverlay(name, layer, options = {}) {
        if (!layer || !name) return;

        overlays.set(layer, { name, shouldDisplay: true });
        registerOverlayWithControl(layer, name);

        if (maskVisible) {
            addLayerSafely(layer);
            updateActiveLabel();
        }
        
        if (options.fit) {
            this.fitToBounds(layer.getBounds());
        }
    },

    clearAllOverlays() {
      isGlobalMaskToggleInProgress = true;
      try {
        overlays.forEach((_state, layer) => {
          removeLayerSafely(layer);
          if (layerControl) layerControl.removeLayer(layer);
        });
      } finally {
        isGlobalMaskToggleInProgress = false;
      }
      overlays.clear();
      pendingOverlayRegistrations.length = 0;
      infoLabel.update('');
    },

    updateMaskOpacity(opacity) {
      overlays.forEach((_value, layer) => {
        if(layer.setOpacity) layer.setOpacity(Number(opacity));
      });
    },

    toggleMask(visible) {
      maskVisible = Boolean(visible);
      isGlobalMaskToggleInProgress = true;
      try {
        overlays.forEach((state, layer) => {
          if (maskVisible && state.shouldDisplay) {
            addLayerSafely(layer);
          } else {
            removeLayerSafely(layer);
          }
        });
      } finally {
        isGlobalMaskToggleInProgress = false;
      }
      updateActiveLabel();
    },

    setInputLayer(layerInstance) {
      removeLayerSafely(inputLayer);
      inputLayer = layerInstance;
      if (inputVisible && inputLayer) addLayerSafely(inputLayer);
    },

    toggleInput(visible) {
      inputVisible = Boolean(visible);
      if (!inputLayer) return;
      if (inputVisible) addLayerSafely(inputLayer);
      else removeLayerSafely(inputLayer);
    },

    toggleQCBoundary(visible) {
        if (!qcBoundaryLayer) return; 

        if (visible) {
            map.addLayer(qcBoundaryLayer);
        } else {
            map.removeLayer(qcBoundaryLayer);
        }
    },

    fitToBounds(boundsObject, options = {}) {
      if (!boundsObject) return;
      
      const bounds = (boundsObject instanceof L.LatLngBounds) ? boundsObject :
        (boundsObject.south) ? [[boundsObject.south, boundsObject.west], [boundsObject.north, boundsObject.east]] :
        boundsObject;

      if (bounds) {
        const flyOptions = { ...defaultFlyOptions, ...(options.flyOptions ?? {}) };
        try {
          map.flyToBounds(bounds, flyOptions);
        } catch (error) {
          console.warn("Smooth flyToBounds failed, falling back to fitBounds", error);
          map.fitBounds(bounds, flyOptions);
        }
      }
    },
    
    invalidateSize() {
      setTimeout(() => map.invalidateSize({ debounceMoveend: true }), 10);
    },

    teardown() {
      map.remove();
    },

    get mapInstance() {
      return map;
    },
  };
}