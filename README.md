# SettleNet Prototype Inference

A streamlined FastAPI backend paired with a single-page prototype (`prototype-v3.html`) that lets you upload tiled imagery, run the selected model, and visualize the merged prediction mask in Leaflet.

## Project Structure

```
settlenet/
├── app/
│   ├── main.py            # FastAPI application exposing /prototype and /upload
│   ├── static/            # Runtime artefacts generated for the Leaflet map
│   ├── models/
│   │   ├── components.py  # Shared ConvNeXt / SettleNet building blocks
│   │   └── architectures.py
│   └── utils/
│       ├── config.py      # Model registry & modality setup
│       └── data_processing.py
├── trained_models/        # Drop .pth checkpoints here
├── prototype-v3.html      # Frontend served at /prototype
├── requirements.txt
└── README.md
```

## Getting Started

1. **Install dependencies**

    ```bash
    pip install -r requirements.txt
    ```

2. **Place model weights**

    Copy the desired `.pth` file(s) into `trained_models/`. Supported options are defined in `app/utils/config.py` (`MODEL_MAPPING`). The prototype dropdown keys (`settlenet`, `convnext_all`, etc.) must match the mapping entries.

3. **Prepare your upload**

    Create a ZIP archive with modality folders that match the selected model:

    ```
    your_tiles.zip
    ├── satellite-256/
    │   ├── qc_100_48.tif
    │   └── ...
    ├── bc-256/
    │   └── qc_100_48.tif
    └── bh-256/
         └── qc_100_48.tif
    ```

    Only the folders required for the chosen modality are validated.

4. **Run the server**

    ```bash
    uvicorn app.main:app --reload
    ```

5. **Open the prototype**

    Visit [http://localhost:8000/prototype](http://localhost:8000/prototype), pick a model, upload the ZIP, and click **Analyse**. The backend streams results to `app/static/` and returns Leaflet-ready metadata that the frontend renders immediately.

## How It Works

- `/prototype` serves the bundled HTML frontend.
- `/upload` accepts a ZIP, determines the required modality from the selected model, loads the matching PyTorch checkpoint on CPU, runs inference per tile, merges predictions geospatially (EPSG:3857 by default), and returns a config payload for Leaflet.
- Combined GeoTIFF + PNG overlays are written to `app/static/` so the browser can fetch them directly.

## Configuration Notes

- Extend or adjust model options via `MODEL_MAPPING` in `app/utils/config.py`.
- Normalisation statistics live in the same file; update them if you trained with different preprocessing.
- The system currently runs inference on CPU. Switch `device` in `app/main.py` if GPU execution is needed.

## Troubleshooting

- **Missing folders in ZIP** – the backend responds with actionable error messages indicating which modality folders were expected.
- **Model not found** – confirm the `.pth` filename matches the entry in `MODEL_MAPPING`.
- **pyproj missing** – install `pyproj` to enable reprojection to Web Mercator; without it, the original CRS is preserved.

## Next Steps

- Add authentication or scoped CORS for production deployments.
- Extend the frontend to preview individual tiles or additional overlays.
- Wire in progress updates (e.g. WebSocket) if you expect very large batches.