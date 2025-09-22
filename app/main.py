# app/main.py

import os
import time
from pathlib import Path
import torch
from PIL import Image
import numpy as np
from tqdm import tqdm

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Local module imports
from app.utils.config import setup_config
from app.utils.data_processing import (
    get_test_file_ids,
    load_and_preprocess_image,
    load_ground_truth_mask,
)
from app.models.architectures import ConvNeXtUNet  # , SettleNet

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
    # elif APP_CONFIG["MODEL_NAME"] == "SettleNet":
    #     model = SettleNet(config)
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


# --- API ENDPOINT ---
@app.get("/", response_class=HTMLResponse)
async def run_inference_and_show_report(request: Request):
    if not test_file_ids:
        return "<h2>Error: No test files found.</h2><p>Please ensure your `data/qc/satellite-256` directory is populated with .tif files.</p>"

    all_benchmarks = []
    visual_results = []

    for num_files in APP_CONFIG["BENCHMARKS"]:
        if len(test_file_ids) < num_files:
            print(
                f"Skipping benchmark for {num_files} files as only {len(test_file_ids)} are available."
            )
            continue

        subset_ids = test_file_ids[:num_files]

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

        end_time = time.time()
        total_time = end_time - start_time

        print(f"✅ Completed {num_files} files in {total_time:.4f} seconds")
        print(f"📊 Average time per file: {total_time/num_files:.4f} seconds")

        all_benchmarks.append(
            {
                "num_files": num_files,
                "total_time": total_time,
                "avg_time": total_time / num_files,
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
