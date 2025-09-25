# SettleNet Frontend-Backend Integration Usage Guide

## Overview
This guide explains how to use the updated SettleNet system with the new frontend-backend integration.

## Model Mapping
The system now supports multiple models with automatic modality selection:

| Frontend Selection | Model File | Modality | Description |
|-------------------|------------|----------|-------------|
| ConvNeXt All | `convnext-all-7ir38hd4.pth` | all | Uses satellite + building count + building height |
| ConvNeXt BC | `convnext-bc-g00wx4xl.pth` | bc | Uses only building count data |
| ConvNeXt Satellite | `convnext-sat-xqkdckas.pth` | satellite | Uses only satellite imagery |
| SettleNet | `settlenet-rxrj9b9b.pth` | all | SettleNet model with all modalities |

## Data Format
Upload a ZIP file containing the following structure:
```
your_data.zip
├── satellite-256/
│   ├── tile_001.tif
│   ├── tile_002.tif
│   └── ...
├── bc-256/
│   ├── tile_001.tif
│   ├── tile_002.tif
│   └── ...
└── bh-256/
    ├── tile_001.tif
    ├── tile_002.tif
    └── ...
```

**Important:** All tile files must have matching names across directories.

## Workflow
1. **Start the backend:** Run `python -m app.main` or use `uvicorn app.main:app --reload`
2. **Access frontend:** Navigate to `http://localhost:8000/prototype`
3. **Select model:** Choose from the dropdown (SettleNet is default)
4. **Upload data:** Choose your ZIP file with the required structure
5. **Analyze:** Click "Analyze" to run inference
6. **View results:** The prediction mask will be automatically added to the Leaflet map

## API Endpoints
- `GET /prototype` - Serves the frontend interface
- `POST /upload` - Handles file upload and inference
- `GET /static/{filename}` - Serves generated prediction files
- `GET /` - Original benchmark interface (still available)

## Key Features
- **Dynamic model loading:** Models are loaded on-demand based on selection
- **Automatic modality handling:** The system automatically uses the correct input channels
- **Web-mapping integration:** Results are converted to web-compatible format with proper CRS
- **Real-time feedback:** Progress updates and error handling
- **Leaflet integration:** Results are automatically displayed on the interactive map

## Troubleshooting
- Ensure all model files are present in the `trained_models/` directory
- Check that uploaded ZIP files contain the required directory structure
- Verify that tile names match across all modality directories
- Monitor the backend console for detailed error messages

## Technical Notes
- The system uses temporary directories for processing uploaded files
- Predictions are saved to the `app/static/` directory for web serving
- CORS is enabled for cross-origin requests
- All models run on CPU by default (can be changed in configuration)