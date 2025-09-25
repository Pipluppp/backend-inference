# app/main.py

import os
import time
from pathlib import Path
import torch
from PIL import Image
import numpy as np
from tqdm import tqdm

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import zipfile
import shutil

# Local module imports
from app.utils.config import setup_config, get_model_config
from app.utils.data_processing import (
    get_test_file_ids,
    load_and_preprocess_image,
    load_ground_truth_mask,
    combine_predictions_from_inference,
    combine_predictions_for_web_mapping,
    create_leaflet_config,
)
from app.models.architectures import ConvNeXtUNet, SettleNet

# --- USER CONFIGURATION ---
# Change these values to test different models and data modalities.
APP_CONFIG = {
    "MODALITY_TO_RUN": "bc+sat",  # one of: "satellite", "bc", "bh", "bc+sat", "all"
    "MODEL_NAME": "ConvNeXtUNet",  # one of: "ConvNeXtUNet", "SettleNet"
    "MODEL_FILENAME": "bc+sat-5z2uadhtpth.pth",  # Filename in the 'trained_models' directory
    "BENCHMARKS": [1, 10, 100],  # Number of files to test for each benchmark
}
# --------------------------

# --- SETUP ---
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = setup_config(APP_CONFIG["MODALITY_TO_RUN"])
device = torch.device("cpu")

# Mount static files and templates
static_dir = Path("app/static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory="app/templates")


# --- MODEL LOADING ---
def load_inference_model():
    model_path = Path("./trained_models") / APP_CONFIG["MODEL_FILENAME"]
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file not found at {model_path}. Please place it in the 'trained_models' directory."
        )

    # Select model architecture
    if APP_CONFIG["MODEL_NAME"] == "ConvNeXtUNet":
        model = ConvNeXtUNet(config)
    elif APP_CONFIG["MODEL_NAME"] == "SettleNet":
        model = SettleNet(config)
    else:
        raise ValueError(f"Model name '{APP_CONFIG['MODEL_NAME']}' not recognized.")

    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    print(
        f"Successfully loaded model '{APP_CONFIG['MODEL_NAME']}' from '{model_path}' onto CPU."
    )
    return model


model = load_inference_model()
test_file_ids = get_test_file_ids(config)

# Global variable to store benchmark results for API access
all_benchmarks = []


# --- DYNAMIC MODEL LOADING ---
def load_model_by_type(model_type: str):
    """Load a model based on the frontend model type selection."""
    model_config = get_model_config(model_type)
    modality = model_config["modality"]
    model_name = model_config["model_name"]
    model_file = model_config["model_file"]

    # Setup configuration for the specific modality
    config = setup_config(modality)

    # Load the model
    model_path = Path("./trained_models") / model_file
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found at {model_path}")

    if model_name == "ConvNeXtUNet":
        model = ConvNeXtUNet(config)
    elif model_name == "SettleNet":
        model = SettleNet(config)
    else:
        raise ValueError(f"Model name '{model_name}' not recognized.")

    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()

    print(
        f"Successfully loaded {model_name} model ({modality} modality) from {model_file}"
    )
    return model, config


# --- UPLOAD AND INFERENCE ENDPOINT ---
@app.post("/upload")
async def upload_and_analyze(
    file: UploadFile = File(...),
    model_type: str = Form(...),
    modality: str = Form(...),
    threshold: float = Form(0.7),
):
    """
    Handle file upload and run inference with the selected model.
    Expected file: ZIP containing satellite-256, bc-256, bh-256 folders with matching tile names.
    """
    try:
        # Load the appropriate model
        model, config = load_model_by_type(model_type)

        # Create temporary directory for processing
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Save uploaded file
            if not file.filename:
                return JSONResponse(
                    status_code=400, content={"error": "No filename provided"}
                )

            file_path = temp_dir / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Extract ZIP file
            if file.filename.lower().endswith(".zip"):
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir / "extracted")
                data_dir = temp_dir / "extracted"
            else:
                return JSONResponse(
                    status_code=400, content={"error": "Only ZIP files are supported"}
                )

            # Find the tile directories
            tile_dirs = {
                "satellite": data_dir / "satellite-256",
                "bc": data_dir / "bc-256",
                "bh": data_dir / "bh-256",
            }

            # Verify required directories exist based on modality
            required_dirs = []
            if config.MODALITY_TO_RUN in ["satellite", "bc+sat", "all"]:
                required_dirs.append("satellite")
            if config.MODALITY_TO_RUN in ["bc", "bc+sat", "all"]:
                required_dirs.append("bc")
            if config.MODALITY_TO_RUN in ["bh", "all"]:
                required_dirs.append("bh")

            for dir_name in required_dirs:
                if not tile_dirs[dir_name].exists():
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": f"Required directory {dir_name}-256 not found in ZIP"
                        },
                    )

            # Get list of tile files (assuming they all have matching names)
            satellite_files = []
            if tile_dirs["satellite"].exists():
                satellite_files = list(tile_dirs["satellite"].glob("*.tif"))

            if not satellite_files:
                return JSONResponse(
                    status_code=400,
                    content={"error": "No .tif files found in satellite-256 directory"},
                )

            # Extract file IDs (filenames without extension)
            file_ids = [f.stem for f in satellite_files]

            # Temporarily update the config data root to point to our extracted data
            original_data_root = config.DATA_ROOT
            config.DATA_ROOT = data_dir

            # Run inference on all tiles
            prediction_masks = []

            print(
                f"Running inference on {len(file_ids)} tiles with {model_type} model..."
            )

            for file_id in tqdm(file_ids, desc="Processing tiles"):
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

                except Exception as e:
                    print(f"Error processing tile {file_id}: {str(e)}")
                    continue

            if not prediction_masks:
                return JSONResponse(
                    status_code=500,
                    content={"error": "No tiles were successfully processed"},
                )

            # Restore original data root
            config.DATA_ROOT = original_data_root

            # Generate unique filename for this inference
            timestamp = int(time.time())
            output_filename = (
                f"predictions_{model_type}_{len(file_ids)}files_{timestamp}.tif"
            )

            # Combine predictions into web-mapping ready format
            web_metadata = combine_predictions_for_web_mapping(
                prediction_masks=prediction_masks,
                file_ids=file_ids[
                    : len(prediction_masks)
                ],  # Match the successful predictions
                config=config,
                output_dir=str(static_dir),
                filename=output_filename,
            )

            # Create leaflet configuration - use PNG file for web display
            png_filename = output_filename.replace(".tif", ".png")
            png_url = f"/static/{png_filename}"
            leaflet_config = create_leaflet_config(web_metadata, png_url)

            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Successfully processed {len(prediction_masks)} tiles",
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

        finally:
            # Clean up temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        print(f"Error in upload_and_analyze: {str(e)}")
        return JSONResponse(
            status_code=500, content={"error": f"Processing failed: {str(e)}"}
        )


# --- PROTOTYPE FRONTEND ---
@app.get("/prototype", response_class=HTMLResponse)
async def serve_prototype():
    """Serve the prototype frontend."""
    try:
        with open("prototype-v3.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Prototype file not found</h1>", status_code=404
        )


# --- API ENDPOINT ---
@app.get("/", response_class=HTMLResponse)
async def run_inference_and_show_report(request: Request):
    if not test_file_ids:
        return "<h2>Error: No test files found.</h2><p>Please ensure your `data/qc/satellite-256` directory is populated with .tif files.</p>"

    global all_benchmarks
    all_benchmarks.clear()  # Clear previous results
    visual_results = []

    for num_files in APP_CONFIG["BENCHMARKS"]:
        if len(test_file_ids) < num_files:
            print(
                f"Skipping benchmark for {num_files} files as only {len(test_file_ids)} are available."
            )
            continue

        subset_ids = test_file_ids[:num_files]
        prediction_masks = []  # Store all prediction masks for this benchmark

        start_time = time.time()
        print(f"\n🚀 Running inference on {num_files} files...")

        # Progress bar for the current benchmark
        for i, file_id in enumerate(
            tqdm(subset_ids, desc=f"Processing {num_files} files", unit="file")
        ):
            image_tensor, viz_images = load_and_preprocess_image(file_id, config)
            image_tensor = image_tensor.unsqueeze(0).to(device)

            with torch.no_grad():
                logits = model(image_tensor)
                pred_mask_np = (
                    (torch.sigmoid(logits) > 0.5)
                    .squeeze()
                    .cpu()
                    .numpy()
                    .astype(np.uint8)
                )

            # Store prediction mask for combining later
            prediction_masks.append(pred_mask_np)

            # For the first benchmark, save images for visualization
            if num_files == APP_CONFIG["BENCHMARKS"][0]:
                result_paths = {"id": file_id, "inputs": {}}

                # Save input images
                for key, img_pil in viz_images.items():
                    filename = f"input_{file_id}_{key}.png"
                    img_pil.save(static_dir / filename)
                    result_paths["inputs"][key] = filename

                # Load and save ground truth mask
                gt_mask = load_ground_truth_mask(file_id, config)
                gt_filename = f"gt_{file_id}.png"
                gt_mask.save(static_dir / gt_filename)
                result_paths["ground_truth"] = gt_filename

                # Save prediction
                pred_pil = Image.fromarray(pred_mask_np * 255)
                pred_filename = f"pred_{file_id}.png"
                pred_pil.save(static_dir / pred_filename)
                result_paths["prediction"] = pred_filename

                visual_results.append(result_paths)

        # Combine all prediction masks into a web-mapping ready TIFF file
        web_metadata = combine_predictions_for_web_mapping(
            prediction_masks=prediction_masks,
            file_ids=subset_ids,
            config=config,
            output_dir=str(static_dir),
            filename=f"web_predictions_{num_files}_files.tif",
        )
        combined_tiff_path = web_metadata["file_path"]

        end_time = time.time()
        total_time = end_time - start_time

        print(f"✅ Completed {num_files} files in {total_time:.4f} seconds")
        print(f"📊 Average time per file: {total_time/num_files:.4f} seconds")
        print(f"💾 Combined predictions saved to: {combined_tiff_path}")

        all_benchmarks.append(
            {
                "num_files": num_files,
                "total_time": total_time,
                "avg_time": total_time / num_files,
                "combined_tiff": Path(
                    combined_tiff_path
                ).name,  # Store just the filename for the template
                "web_metadata": web_metadata,  # Include full metadata for potential frontend use
            }
        )

    print(
        f"\n🎉 All benchmarks completed! Generated {len(visual_results)} visual results."
    )
    print(f"📁 Results saved to: {static_dir}")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "model_name": APP_CONFIG["MODEL_NAME"],
            "modality": APP_CONFIG["MODALITY_TO_RUN"],
            "benchmarks": all_benchmarks,
            "results": visual_results,
        },
    )


@app.get("/api/predictions/metadata/{num_files}")
async def get_predictions_metadata(num_files: int):
    """
    API endpoint to get metadata for web mapping integration.
    Returns Leaflet-compatible configuration for the predictions.
    """
    if num_files not in APP_CONFIG["BENCHMARKS"]:
        return JSONResponse(
            status_code=404,
            content={"error": f"No benchmark found for {num_files} files"},
        )

    # Find the corresponding benchmark data
    benchmark_data = None
    for benchmark in all_benchmarks:
        if benchmark["num_files"] == num_files:
            benchmark_data = benchmark
            break

    if not benchmark_data or "web_metadata" not in benchmark_data:
        return JSONResponse(
            status_code=404,
            content={"error": f"No web metadata found for {num_files} files"},
        )

    # Create Leaflet configuration
    tiff_filename = benchmark_data["combined_tiff"]
    tiff_url = f"/static/{tiff_filename}"

    leaflet_config = create_leaflet_config(benchmark_data["web_metadata"], tiff_url)

    return JSONResponse(content=leaflet_config)


@app.get("/api/predictions/list")
async def list_available_predictions():
    """
    API endpoint to list all available prediction datasets.
    """
    predictions_list = []

    for benchmark in all_benchmarks:
        if "web_metadata" in benchmark:
            predictions_list.append(
                {
                    "num_files": benchmark["num_files"],
                    "filename": benchmark["combined_tiff"],
                    "processing_time": benchmark["total_time"],
                    "bounds": benchmark["web_metadata"]["bounds"],
                    "tile_count": benchmark["web_metadata"]["num_tiles"],
                }
            )

    return JSONResponse(
        content={
            "available_predictions": predictions_list,
            "model_info": {
                "name": APP_CONFIG["MODEL_NAME"],
                "modality": APP_CONFIG["MODALITY_TO_RUN"],
                "filename": APP_CONFIG["MODEL_FILENAME"],
            },
        }
    )
