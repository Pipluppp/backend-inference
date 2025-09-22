# app/utils/data_processing.py

import os
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image
import albumentations as A
from albumentations.pytorch import ToTensorV2
from typing import List, Dict
import torch

from app.utils.config import Config


def get_test_file_ids(config: Config) -> List[str]:
    """Scans the satellite directory to get a list of all tile IDs."""
    image_dir = config.DATA_ROOT / "satellite-256"
    if not image_dir.exists():
        return []
    return sorted([f.stem for f in image_dir.iterdir() if f.suffix == ".tif"])


def load_ground_truth_mask(file_id: str, config: Config) -> Image.Image:
    """
    Loads the ground truth mask for visualization.
    """
    mask_path = config.DATA_ROOT / "mask-256" / f"{file_id}.tif"
    if not mask_path.exists():
        # Return a placeholder if mask doesn't exist
        return Image.new("L", (256, 256), 128)  # Gray placeholder

    with rasterio.open(mask_path) as src:
        mask = src.read(1).astype(np.uint8)
        return Image.fromarray(mask * 255)  # Convert to 0-255 range


def load_and_preprocess_image(
    file_id: str, config: Config
) -> (torch.Tensor, Dict[str, Image.Image]):
    """
    Loads the necessary TIFF files for a given ID based on the modality,
    preprocesses them, and returns the tensor and a dict of PIL images for visualization.
    """
    inputs_to_stack = []
    viz_images = {}  # To store images for the frontend

    # --- Load Satellite Image (if needed) ---
    if config.MODALITY_TO_RUN in ["satellite", "bc+sat", "all"]:
        path = config.DATA_ROOT / "satellite-256" / f"{file_id}.tif"
        with rasterio.open(path) as src:
            # Reads into (bands, height, width), so we transpose to (h, w, b)
            img_rgb = src.read().transpose(1, 2, 0).astype(np.float32)
            # Normalize from 0-255 range to 0-1 for the model
            img_rgb /= 255.0
            inputs_to_stack.append(img_rgb)
            # For visualization, convert to a PIL Image
            viz_images["satellite"] = Image.fromarray((img_rgb * 255).astype(np.uint8))

    # --- Load Building Count Image (if needed) ---
    if config.MODALITY_TO_RUN in ["bc", "bc+sat", "all"]:
        path = config.DATA_ROOT / "bc-256" / f"{file_id}.tif"
        with rasterio.open(path) as src:
            img_bc = src.read(1).astype(np.float32)
            inputs_to_stack.append(np.expand_dims(img_bc, axis=-1))
            # For visualization, we need to scale the data to a visible 0-255 range
            # This is a simple min-max scaling; you might need a more robust method
            bc_viz = (img_bc - img_bc.min()) / (img_bc.max() - img_bc.min() + 1e-6)
            viz_images["bc"] = Image.fromarray((bc_viz * 255).astype(np.uint8))

    # --- Load Building Height Image (if needed) ---
    if config.MODALITY_TO_RUN in ["bh", "all"]:
        path = config.DATA_ROOT / "bh-256" / f"{file_id}.tif"
        with rasterio.open(path) as src:
            img_bh = src.read(1).astype(np.float32)
            inputs_to_stack.append(np.expand_dims(img_bh, axis=-1))
            # Similar visualization scaling for BH
            bh_viz = (img_bh - img_bh.min()) / (img_bh.max() - img_bh.min() + 1e-6)
            viz_images["bh"] = Image.fromarray((bh_viz * 255).astype(np.uint8))

    # --- Combine and Transform ---
    if not inputs_to_stack:
        raise ValueError(f"No data loaded for modality {config.MODALITY_TO_RUN}")

    combined_np = np.concatenate(inputs_to_stack, axis=-1)

    transform = A.Compose(
        [
            A.Normalize(
                mean=config.CURRENT_MEAN, std=config.CURRENT_STD, max_pixel_value=1.0
            ),
            ToTensorV2(),
        ]
    )

    transformed = transform(image=combined_np)
    image_tensor = transformed["image"]

    return image_tensor, viz_images
