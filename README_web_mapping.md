# Web Mapping Integration Guide

## Overview

The SettleNet inference application now includes **web-mapping ready** TIFF combination functionality specifically designed for Leaflet integration. This enables you to display model predictions on interactive web maps with proper geospatial positioning.

## Key Improvements for Web Mapping

### 🌍 Geographic Accuracy
- **Coordinate-based positioning**: Tiles are placed based on their actual geographic coordinates (parsed from `qc_x_y` file IDs)
- **Proper CRS handling**: Automatic reprojection to Web Mercator (EPSG:3857) for web maps
- **Geospatial metadata preservation**: Maintains coordinate reference systems and transforms

### 🗺️ Web Optimization
- **Cloud Optimized GeoTIFF (COG)**: Creates web-optimized TIFF files with tiling and compression
- **Leaflet-ready bounds**: Provides bounds in `[[south, west], [north, east]]` format
- **Complete metadata**: Returns all information needed for frontend integration

## API Endpoints for Frontend

### Get Prediction Metadata
```
GET /api/predictions/metadata/{num_files}
```
Returns Leaflet-compatible configuration for specific prediction dataset.

**Example Response:**
```json
{
  "tiff_url": "/static/web_predictions_10_files.tif",
  "bounds": [[14.667, 121.008], [14.669, 121.010]],
  "center": [14.668, 121.009],
  "zoom_levels": {
    "min": 10,
    "max": 18,
    "initial": 13
  },
  "tile_info": {
    "total_tiles": 10,
    "grid_size": "5x2",
    "dimensions": "1280x512"
  },
  "crs": "EPSG:3857",
  "format": "image/tiff"
}
```

### List Available Predictions
```
GET /api/predictions/list
```
Returns list of all available prediction datasets with basic info.

## Frontend Integration

### Basic Leaflet Integration

```javascript
// Fetch metadata
const response = await fetch('/api/predictions/metadata/10');
const config = await response.json();

// Create Leaflet map
const map = L.map('map').setView(config.center, config.zoom_levels.initial);

// Add base map
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

// Add prediction overlay
const imageOverlay = L.imageOverlay(config.tiff_url, config.bounds, {
    opacity: 0.7
});
imageOverlay.addTo(map);

// Fit map to bounds
map.fitBounds(config.bounds);
```

### Advanced Integration with GeoRaster

For better TIFF support, use `georaster-layer-for-leaflet`:

```javascript
import GeoRasterLayer from 'georaster-layer-for-leaflet';

// Fetch and display GeoTIFF
fetch(config.tiff_url)
  .then(response => response.arrayBuffer())
  .then(arrayBuffer => {
    parseGeoraster(arrayBuffer).then(georaster => {
      const layer = new GeoRasterLayer({
        georaster: georaster,
        opacity: 0.7,
        pixelValuesToColorFn: values => {
          const pixelValue = values[0];
          if (pixelValue === 1) return '#ff0000'; // Red for predictions
          return null; // Transparent for background
        }
      });
      layer.addTo(map);
    });
  });
```

## Function Reference

### Core Functions

#### `combine_predictions_for_web_mapping()`
Main function for creating web-mapping ready TIFFs.

```python
metadata = combine_predictions_for_web_mapping(
    prediction_masks=masks,
    file_ids=file_ids,
    config=config,
    output_dir="web_predictions",
    filename="predictions.tif"
)
```

#### `create_leaflet_config()`
Creates complete Leaflet configuration from metadata.

```python
leaflet_config = create_leaflet_config(metadata, tiff_url)
```

#### `validate_for_web_mapping()`
Validates data compatibility for web mapping.

```python
validation = validate_for_web_mapping(file_ids, config)
```

### Utility Functions

- `get_leaflet_bounds_from_metadata()`: Convert bounds to Leaflet format
- `parse_tile_coordinates()`: Extract coordinates from file IDs

## File Structure

```
settlenet/
├── app/
│   ├── main.py                    # Updated with web mapping APIs
│   ├── utils/
│   │   └── data_processing.py     # Enhanced with web mapping functions
│   └── static/                    # Contains web-ready TIFF files
├── web_demo/                      # Example output directory
│   ├── demo_web_predictions.tif   # Web-optimized TIFF
│   └── leaflet_config.json       # Frontend configuration
├── example_web_mapping.py         # Demonstration script
└── README_web_mapping.md          # This file
```

## Data Requirements

### File Naming Convention
Files must follow the `qc_x_y.tif` pattern where:
- `x` and `y` are tile coordinates
- Coordinates determine geographic positioning

### Geospatial Metadata
- Source TIFF files must contain CRS information
- Transform information should be present
- Currently supports EPSG:4326 (WGS84) input data

## Example Usage

### Command Line Demo
```bash
python example_web_mapping.py
```

### Web Application
1. Start the FastAPI server: `uvicorn app.main:app --reload`
2. Navigate to `http://localhost:8000` to run inference
3. Access metadata via API endpoints
4. Use the TIFF files and metadata in your frontend

## Troubleshooting

### Common Issues

1. **"Cannot parse coordinates from file_id"**
   - Ensure file IDs follow `qc_x_y` format
   - Check that coordinate parsing is working correctly

2. **"No CRS information in source files"**
   - Source TIFF files must contain geospatial metadata
   - Use `gdalinfo` to check file metadata

3. **"Missing tiles from complete grid"** 
   - Not all tiles in the coordinate range are present
   - This is usually fine, just creates gaps in coverage

### Performance Considerations

- **Large areas**: Consider breaking into smaller chunks
- **File size**: COG format helps with web serving performance
- **Coordinate system**: Web Mercator provides best web map performance

## Next Steps

1. **Tile server**: Consider implementing a proper tile server for large datasets
2. **Styling**: Add visualization options (color schemes, opacity controls)
3. **Interactivity**: Add click handlers and popup information
4. **Caching**: Implement caching for frequently accessed predictions
5. **Authentication**: Add access controls if needed

## Dependencies

The web mapping functionality requires:
- `rasterio` (already included)
- `rasterio.warp` for coordinate transformations
- Standard libraries: `numpy`, `pathlib`, `json`

Frontend integration works best with:
- Leaflet.js
- `georaster-layer-for-leaflet` (recommended)
- Modern browser with CORS support