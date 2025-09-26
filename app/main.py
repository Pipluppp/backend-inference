import time
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import torch
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import tempfile
import zipfile
import shutil

from app.models.architectures import ConvNeXtUNet, SettleNet
from app.utils.config import Config, setup_config, get_model_config
from app.utils.data_processing import (
    load_and_preprocess_image,
    combine_predictions_for_web_mapping,
    create_leaflet_config,
)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

device = torch.device("cpu")
static_dir = Path("app/static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


MODEL_CACHE: Dict[str, torch.nn.Module] = {}


def load_model_by_type(model_type: str) -> Tuple[torch.nn.Module, "Config"]:
    """Load (and cache) a model based on the frontend selection."""
    model_config = get_model_config(model_type)
    modality = model_config["modality"]
    model_name = model_config["model_name"]
    model_file = model_config["model_file"]

    model = MODEL_CACHE.get(model_type)
    if model is None:
        model_path = Path("./trained_models") / model_file
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file not found at {model_path}. Place it in 'trained_models/'."
            )

        config_for_shape = setup_config(modality)

        if model_name == "ConvNeXtUNet":
            model = ConvNeXtUNet(config_for_shape)
        elif model_name == "SettleNet":
            model = SettleNet(config_for_shape)
        else:
            raise ValueError(f"Model name '{model_name}' not recognized.")

        state_dict = torch.load(model_path, map_location=device)
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()
        MODEL_CACHE[model_type] = model

    # Always create a fresh config so request-specific changes don't leak
    config = setup_config(modality)
    return model, config


@app.post("/upload")
async def upload_and_analyze(
    file: UploadFile = File(...),
    model_type: str = Form(...),
    threshold: float = Form(0.7),
    modality: str = Form(""),  # legacy field retained for backward compatibility
):
    """
    Handle file upload and run inference with the selected model.
    Expected file: ZIP containing satellite-256, bc-256, bh-256 folders with matching tile names.
    """
    try:
        model, config = load_model_by_type(model_type)

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)

            if not file.filename:
                return JSONResponse(
                    status_code=400, content={"error": "No filename provided"}
                )

            file_path = temp_dir / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            if not file.filename.lower().endswith(".zip"):
                return JSONResponse(
                    status_code=400, content={"error": "Only ZIP files are supported"}
                )

            extracted_dir = temp_dir / "extracted"
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(extracted_dir)

            tile_dirs = {
                "satellite": extracted_dir / "satellite-256",
                "bc": extracted_dir / "bc-256",
                "bh": extracted_dir / "bh-256",
            }

            required_dirs = []
            if config.MODALITY_TO_RUN in ["satellite", "bc+sat", "all"]:
                required_dirs.append("satellite")
            if config.MODALITY_TO_RUN in ["bc", "bc+sat", "all"]:
                required_dirs.append("bc")
            if config.MODALITY_TO_RUN in ["bh", "all"]:
                required_dirs.append("bh")

            missing = [d for d in required_dirs if not tile_dirs[d].exists()]
            if missing:
                missing_dirs = ", ".join(f"{name}-256" for name in missing)
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": f"Required directories missing from ZIP: {missing_dirs}"
                    },
                )

            satellite_files = list(tile_dirs["satellite"].glob("*.tif"))
            if not satellite_files:
                return JSONResponse(
                    status_code=400,
                    content={"error": "No .tif files found in satellite-256 directory"},
                )

            file_ids = [f.stem for f in satellite_files]

            prediction_masks = []
            original_data_root = config.DATA_ROOT
            config.DATA_ROOT = extracted_dir

            for file_id in file_ids:
                try:
                    image_tensor, _ = load_and_preprocess_image(file_id, config)
                    image_tensor = image_tensor.unsqueeze(0).to(device)

                    with torch.no_grad():
                        logits = model(image_tensor)
                        pred_mask_np = (
                            (torch.sigmoid(logits) > threshold)
                            .squeeze()
                            .cpu()
                            .numpy()
                            .astype(np.uint8)
                        )

                    prediction_masks.append(pred_mask_np)
                except Exception as exc:  # noqa: BLE001
                    print(f"Error processing tile {file_id}: {exc}")

            config.DATA_ROOT = original_data_root

            if not prediction_masks:
                return JSONResponse(
                    status_code=500,
                    content={"error": "No tiles were successfully processed"},
                )

            timestamp = int(time.time())
            output_filename = (
                f"predictions_{model_type}_{len(prediction_masks)}tiles_{timestamp}.tif"
            )

            web_metadata = combine_predictions_for_web_mapping(
                prediction_masks=prediction_masks,
                file_ids=file_ids[: len(prediction_masks)],
                config=config,
                output_dir=str(static_dir),
                filename=output_filename,
            )

            png_filename = output_filename.replace(".tif", ".png")
            png_url = f"/static/{png_filename}"
            leaflet_config = create_leaflet_config(web_metadata, png_url)

            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Processed {len(prediction_masks)} tiles",
                    "leaflet_config": leaflet_config,
                    "metadata": {
                        "model_type": model_type,
                        "modality": config.MODALITY_TO_RUN,
                        "threshold": threshold,
                        "tiles_processed": len(prediction_masks),
                        "output_file": output_filename,
                    },
                }
            )

    except Exception as exc:  # noqa: BLE001
        print(f"Error in upload_and_analyze: {exc}")
        return JSONResponse(
            status_code=500, content={"error": f"Processing failed: {exc}"}
        )


@app.get("/prototype", response_class=HTMLResponse)
async def serve_prototype():
    try:
        with open("prototype-v3.html", "r", encoding="utf-8") as proto_file:
            return HTMLResponse(content=proto_file.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Prototype file not found</h1>", status_code=404
        )
