# 🎉 SettleNet Web-Ready Inference - Complete Setup

## ✅ **Integration Complete!**

Your SettleNet application now has **full web-mapping integration** built directly into the inference pipeline. Here's what you can do:

## 🚀 **Two Ways to Run Inference**

### 1. **Web Interface** (Visual + Multiple Benchmarks)
```bash
# Option A: Using the startup helper
python start_inference.py
# Then choose option 1

# Option B: Direct command
uvicorn app.main:app --reload
# Then visit http://localhost:8000
```

**What it does:**
- Runs inference on 1, 10, and 100 files (benchmarks)
- Shows visual results in browser
- Creates multiple web-ready TIFF files:
  - `web_predictions_1_files.tif`
  - `web_predictions_10_files.tif` 
  - `web_predictions_100_files.tif`
- Provides API endpoints for frontend integration

### 2. **Command Line** (Single Inference Job)
```bash
# Basic usage - process all files
python run_inference.py

# Process specific number of files
python run_inference.py --num-files 25

# Custom output location
python run_inference.py --num-files 50 --output-dir results --output-filename my_predictions.tif

# Different modality
python run_inference.py --modality satellite --num-files 10
```

**What it creates:**
- Single web-ready TIFF file (properly georeferenced)
- Leaflet configuration JSON file
- Complete geographic metadata

## 🗺️ **Web-Ready Output Files**

Every inference run creates:

1. **GeoTIFF File** (`*.tif`)
   - Properly georeferenced in Web Mercator (EPSG:3857)
   - Cloud Optimized GeoTIFF format
   - Tiles positioned by actual coordinates (not visual grid)
   - Ready for Leaflet integration

2. **Leaflet Config** (`*_leaflet_config.json`)
   - Bounds in `[[south, west], [north, east]]` format
   - Center coordinates for map initialization
   - Zoom level recommendations
   - Complete metadata for frontend use

## 🌐 **Frontend Integration**

### Basic Leaflet Integration
```javascript
// Load the config
const response = await fetch('/path/to/leaflet_config.json');
const config = await response.json();

// Create map
const map = L.map('map').setView(config.center, config.zoom_levels.initial);

// Add base layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

// Add prediction overlay
const imageOverlay = L.imageOverlay(config.tiff_url, config.bounds, {
    opacity: 0.7
});
imageOverlay.addTo(map);

// Fit to bounds
map.fitBounds(config.bounds);
```

### API Endpoints (Web Interface Only)
```javascript
// Get metadata for specific benchmark
GET /api/predictions/metadata/10

// List all available predictions
GET /api/predictions/list
```

## 📋 **Example Output**

When you run inference, you'll see:
```
🚀 SettleNet Inference Pipeline
==================================================
✅ Loaded model 'ConvNeXtUNet' from 'trained_models\bc+sat-5z2uadhtpth.pth'
📊 Processing 10 files with modality: bc+sat
🔍 Validating data for web mapping...
✅ Data validation passed
🔮 Running inference...
✅ Inference completed in 2.15 seconds
🗺️  Creating web-ready TIFF...
Combined 10 prediction masks geospatially into predictions\my_predictions.tif
Geographic bounds: {'west': 121.008, 'south': 14.667, 'east': 121.011, 'north': 14.670}
CRS: EPSG:3857
🎉 Pipeline completed successfully!
```

## 🔧 **Key Features**

- **Geographic Accuracy**: Tiles positioned by real coordinates (`qc_x_y`)
- **Web Mercator CRS**: Perfect for Leaflet/web maps
- **Data Validation**: Checks for missing tiles and metadata issues
- **Performance Tracking**: Reports inference times and statistics
- **Cloud Optimized**: GeoTIFF files optimized for web serving
- **Complete Metadata**: Everything your frontend needs

## 📁 **File Structure After Running**

```
settlenet/
├── app/static/                    # Web interface results
│   ├── web_predictions_1_files.tif
│   ├── web_predictions_10_files.tif
│   └── web_predictions_100_files.tif
├── predictions/                   # Command line results  
│   ├── my_predictions.tif
│   └── my_predictions_leaflet_config.json
├── run_inference.py              # Command line interface
├── start_inference.py            # User-friendly launcher
└── app/main.py                   # Web interface (enhanced)
```

## 🎯 **Ready for Production**

Your TIFF files are now:
- ✅ Properly georeferenced for web maps
- ✅ Positioned by actual geographic coordinates
- ✅ Optimized for web serving (COG format)
- ✅ Compatible with Leaflet, OpenLayers, etc.
- ✅ Include complete metadata for frontend integration

## 💡 **Next Steps**

1. **Test with your frontend**: Use the generated JSON config and TIFF files
2. **Serve the files**: Set up a web server to serve the TIFF files
3. **Style the predictions**: Add colors, opacity controls, etc.
4. **Add interactivity**: Click handlers, popups, analysis tools

**The inference pipeline is now complete and ready for web mapping integration!** 🌍✨