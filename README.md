# SettleNet Prototype Inference TESTING AGAIN

FastAPI backend plus a single-page Leaflet prototype that accepts tiled imagery, runs a selected PyTorch checkpoint, and renders the merged prediction mask in the browser.

## Swagger API Docs

Check api and usage after running

```
http://localhost:8000/docs
```

## At a Glance

- **Backend**: `FastAPI` app with `/prototype`, `/upload`, and `/progress/{job_id}` endpoints
- **Frontend**: `prototype-v3.html` served by the backend; handles uploads and polls progress
- **Models**: Drop `.pth` checkpoints into `trained_models/` and wire them via `MODEL_MAPPING`
- **Outputs**: Combined GeoTIFF + PNG overlays written to `app/static/` for immediate Leaflet use

```
settlenet/
├── app/
│   ├── main.py            # FastAPI application & progress tracking
│   ├── models/
│   │   ├── components.py  # Shared ConvNeXt / SettleNet blocks
│   │   └── architectures.py
│   ├── static/            # Runtime artefacts served back to the frontend
│   └── utils/
│       ├── config.py      # Model registry & modality setup
│       └── data_processing.py
├── prototype-v3.html      # Leaflet prototype fetched from /prototype
├── requirements.txt
├── trained_models/        # Place model checkpoints here
└── README.md
```

## Requirements

- Python 3.10+
- GDAL-compatible dependencies used by `rasterio`
- Optional: `pyproj` for reprojection to EPSG:3857 (Leaflet friendly)

Install Python packages:

```bash
pip install -r requirements.txt
```

## Setup Checklist

1. **Model weights** – copy the desired `.pth` files into `trained_models/`.
     - Supported keys live in `app/utils/config.py` under `MODEL_MAPPING` (e.g. `settlenet`, `convnext_all`).
     - Frontend dropdown values must match these keys exactly.

2. **Prepare upload ZIP** – create a ZIP containing the modality folders required by the chosen model:

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

     The backend validates only the folders needed for the selected modality (satellite, bc, bh).

3. **Run the server**

     ```bash
     uvicorn app.main:app --reload
     ```

4. **Open the prototype** – visit [http://localhost:8000/prototype](http://localhost:8000/prototype), choose a model, upload your ZIP, and click **Analyse**. The UI shows real-time progress as the backend processes each tile.

## Request Flow

1. **Frontend upload** – the browser posts the ZIP and selected model to `/upload`.
2. **Job creation** – the backend saves the archive, returns a `job_id`, and runs inference asynchronously.
3. **Progress polling** – the frontend polls `/progress/{job_id}` once per second and updates the progress bar.
4. **Completion** – when the job finishes, the progress endpoint embeds the Leaflet configuration. The frontend renders the merged prediction overlay and announces completion.

### API Reference

#### `POST /upload`

- **Body**: multipart form containing `file`, `model_type`, optional `threshold` (default 0.7)
- **Response**: `{ "job_id": "..." }`

> The endpoint always returns quickly; inference happens in a background task.

#### `GET /progress/{job_id}`

- **Response** (during processing):

    ```json
    {
        "job_id": "...",
        "status": "processing",
        "progress": 0.42,
        "tiles_total": 12,
        "tiles_processed": 5,
        "message": "Processed 5/12 tiles"
    }
    ```

- **Response** (on completion):

    ```json
    {
        "job_id": "...",
        "status": "completed",
        "progress": 1.0,
        "result": {
            "success": true,
            "leaflet_config": {
                "tiff_url": "/static/predictions_settlenet_12tiles_1700000000.tif",
                "bounds": {"south": 14.6, "west": 121.0, "north": 14.7, "east": 121.1},
                "zoom_levels": {"min": 10, "max": 18, "initial": 13},
                ...
            },
            "metadata": {"model_type": "settlenet", "tiles_processed": 12, ...}
        }
    }
    ```

#### `GET /prototype`

Serves `prototype-v3.html`.

#### `GET /static/{filename}`

Exposes generated GeoTIFF/PNG overlays.

## Output Artefacts

- Combined GeoTIFF (`*.tif`) and PNG previews (`*.png`) are placed in `app/static/` by default.
- Filenames include the selected model type, tile count, and timestamp for traceability.
- Existing artefacts remain until manually deleted—clear the directory periodically if disk space is a concern.

## Configuration & Customisation

- **Model registry** – update `MODEL_MAPPING` in `app/utils/config.py` to add or rename models.
- **Normalisation stats** – adjust the RGB/BC/BH means and standard deviations if your training data differs.
- **Device selection** – change `device = torch.device("cpu")` at the top of `app/main.py` if GPU inference is required.
- **Leaflet defaults** – tweak initial bounds/zoom or UI styling inside `prototype-v3.html`.

## Troubleshooting

- **Zip validation errors** – ensure the uploaded archive contains the modality folders required by the chosen model.
- **Missing checkpoint** – confirm the `.pth` filename matches the mapping entry.
- **CRS reprojection issues** – install `pyproj`; without it, output stays in the source CRS.
- **Stale static artefacts** – clear `app/static/` if you want to avoid serving outdated overlays.

## Housekeeping

- The legacy benchmarking scripts (`run_inference.py`, `start_inference.py`) are no longer part of the supported workflow.
- Keep dependencies lean—`requirements.txt` mirrors the modules imported in `app/`.
- Consider adding authentication/CORS restrictions before exposing the prototype publicly.