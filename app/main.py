import asyncio
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
MODEL_CACHE_LOCK = threading.Lock()

PROGRESS_REGISTRY: Dict[str, Dict[str, Any]] = {}
PROGRESS_REGISTRY_LOCK = threading.Lock()


def initialize_progress(job_id: str) -> None:
    with PROGRESS_REGISTRY_LOCK:
        PROGRESS_REGISTRY[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "progress": 0.0,
            "message": "Queued",
            "tiles_total": 0,
            "tiles_processed": 0,
            "result": None,
            "error": None,
        }


def update_progress(job_id: str, **updates: Any) -> None:
    with PROGRESS_REGISTRY_LOCK:
        if job_id not in PROGRESS_REGISTRY:
            PROGRESS_REGISTRY[job_id] = {"job_id": job_id}
        PROGRESS_REGISTRY[job_id].update(updates)


def get_progress(job_id: str) -> Dict[str, Any]:
    with PROGRESS_REGISTRY_LOCK:
        return PROGRESS_REGISTRY.get(job_id, {}).copy()


def load_model_by_type(model_type: str) -> Tuple[torch.nn.Module, "Config"]:
    """Load (and cache) a model based on the frontend selection."""
    model_config = get_model_config(model_type)
    modality = model_config["modality"]
    model_name = model_config["model_name"]
    model_file = model_config["model_file"]

    with MODEL_CACHE_LOCK:
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

        cached_model = MODEL_CACHE[model_type]

    # Always create a fresh config so request-specific changes don't leak
    config = setup_config(modality)
    return cached_model, config


async def run_job(
    job_id: str, job_dir: Path, uploaded_path: Path, model_type: str, threshold: float
) -> None:
    try:
        await asyncio.to_thread(
            process_upload_job,
            job_id,
            job_dir,
            uploaded_path,
            model_type,
            threshold,
        )
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def process_upload_job(
    job_id: str,
    job_dir: Path,
    uploaded_path: Path,
    model_type: str,
    threshold: float,
) -> None:
    try:
        update_progress(
            job_id, status="processing", message="Loading model", progress=0.05
        )
        model, config = load_model_by_type(model_type)

        if not uploaded_path.name.lower().endswith(".zip"):
            raise ValueError("Only ZIP files are supported")

        extracted_dir = job_dir / "extracted"
        update_progress(job_id, message="Extracting archive", progress=0.1)
        with zipfile.ZipFile(uploaded_path, "r") as zip_ref:
            zip_ref.extractall(extracted_dir)

        tile_dirs = {
            "satellite": extracted_dir / "satellite-256",
            "bc": extracted_dir / "bc-256",
            "bh": extracted_dir / "bh-256",
        }

        required_dirs: List[str] = []
        if config.MODALITY_TO_RUN in ["satellite", "bc+sat", "all"]:
            required_dirs.append("satellite")
        if config.MODALITY_TO_RUN in ["bc", "bc+sat", "all"]:
            required_dirs.append("bc")
        if config.MODALITY_TO_RUN in ["bh", "all"]:
            required_dirs.append("bh")

        missing = [d for d in required_dirs if not tile_dirs[d].exists()]
        if missing:
            missing_dirs = ", ".join(f"{name}-256" for name in missing)
            raise ValueError(f"Required directories missing from ZIP: {missing_dirs}")

        available_files: Dict[str, List[Path]] = {}
        for dir_key in required_dirs:
            files = list(tile_dirs[dir_key].glob("*.tif"))
            if not files:
                raise ValueError(f"No .tif files found in {dir_key}-256 directory")
            available_files[dir_key] = files

        if "satellite" in available_files:
            reference_key = "satellite"
        else:
            reference_key = required_dirs[0]

        file_ids = [f.stem for f in available_files[reference_key]]

        for dir_key in required_dirs:
            if dir_key == reference_key:
                continue
            missing_files = [
                file_id
                for file_id in file_ids
                if not (tile_dirs[dir_key] / f"{file_id}.tif").exists()
            ]
            if missing_files:
                raise ValueError(
                    f"Missing tiles in {dir_key}-256 directory: {', '.join(missing_files[:5])}"
                )
        total_tiles = len(file_ids)
        update_progress(
            job_id,
            message=f"Processing {total_tiles} tiles",
            tiles_total=total_tiles,
            tiles_processed=0,
            progress=0.15,
        )

        prediction_masks: List[np.ndarray] = []
        original_data_root = config.DATA_ROOT
        config.DATA_ROOT = extracted_dir

        try:
            for index, file_id in enumerate(file_ids, start=1):
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

                progress_value = 0.15 + (0.7 * index / total_tiles)
                update_progress(
                    job_id,
                    tiles_processed=index,
                    progress=min(progress_value, 0.9),
                    message=f"Processed {index}/{total_tiles} tiles",
                )

            if not prediction_masks:
                raise RuntimeError("No tiles were successfully processed")

            update_progress(job_id, message="Merging predictions", progress=0.92)
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

            result_payload = {
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

            update_progress(
                job_id,
                status="completed",
                progress=1.0,
                message="Processing complete",
                result=result_payload,
            )
        finally:
            config.DATA_ROOT = original_data_root
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)
        update_progress(
            job_id,
            status="failed",
            progress=1.0,
            message=f"Failed: {error_message}",
            error=error_message,
        )


@app.post("/upload")
async def upload_and_analyze(
    file: UploadFile = File(...),
    model_type: str = Form(...),
    threshold: float = Form(0.7),
    modality: str = Form(""),  # legacy field retained for backward compatibility
):
    """
    Handle file upload and kick off asynchronous inference with the selected model.
    Expected file: ZIP containing satellite-256, bc-256, bh-256 folders with matching tile names.
    """
    if not file.filename:
        return JSONResponse(status_code=400, content={"error": "No filename provided"})

    job_id = uuid.uuid4().hex
    initialize_progress(job_id)
    update_progress(job_id, message="Uploading file", status="pending")

    try:
        threshold_value = float(threshold)
    except (TypeError, ValueError):  # noqa: BLE001
        update_progress(
            job_id,
            status="failed",
            message="Invalid threshold value",
            error="Invalid threshold",
        )
        return JSONResponse(
            status_code=400, content={"error": "Invalid threshold value"}
        )

    job_dir = Path(tempfile.mkdtemp(prefix=f"settlenet_{job_id}_"))
    uploaded_path = job_dir / file.filename

    try:
        with open(uploaded_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:  # noqa: BLE001
        update_progress(
            job_id, status="failed", message=f"Upload failed: {exc}", error=str(exc)
        )
        shutil.rmtree(job_dir, ignore_errors=True)
        return JSONResponse(
            status_code=500, content={"error": f"Could not save upload: {exc}"}
        )

    update_progress(
        job_id, status="processing", message="Queued for processing", progress=0.02
    )
    asyncio.create_task(
        run_job(job_id, job_dir, uploaded_path, model_type, threshold_value)
    )

    return JSONResponse(content={"job_id": job_id})


@app.get("/progress/{job_id}")
async def get_job_progress(job_id: str):
    record = get_progress(job_id)
    if not record:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    return JSONResponse(content=record)


@app.get("/prototype", response_class=HTMLResponse)
async def serve_prototype():
    try:
        with open("prototype-v3.html", "r", encoding="utf-8") as proto_file:
            return HTMLResponse(content=proto_file.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Prototype file not found</h1>", status_code=404
        )
