from pathlib import Path
from typing import Any, Dict, List, Tuple

import albumentations as A
from albumentations.pytorch import ToTensorV2
import numpy as np
import rasterio
from rasterio.coords import BoundingBox
from rasterio.enums import Resampling
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject
import torch
from PIL import Image

from app.utils.config import Config


def load_and_preprocess_image(
    file_id: str, config: Config
) -> Tuple[torch.Tensor, Dict[str, Image.Image]]:
    inputs: List[np.ndarray] = []
    viz_images: Dict[str, Image.Image] = {}

    if config.MODALITY_TO_RUN in {"satellite", "bc+sat", "all"}:
        path = config.DATA_ROOT / "satellite-256" / f"{file_id}.tif"
        with rasterio.open(path) as src:
            rgb = src.read().transpose(1, 2, 0).astype(np.float32) / 255.0
        inputs.append(rgb)
        viz_images["satellite"] = Image.fromarray((rgb * 255).astype(np.uint8))

    if config.MODALITY_TO_RUN in {"bc", "bc+sat", "all"}:
        path = config.DATA_ROOT / "bc-256" / f"{file_id}.tif"
        with rasterio.open(path) as src:
            bc = src.read(1).astype(np.float32)
        inputs.append(bc[..., None])
        scaled = (bc - bc.min()) / (bc.max() - bc.min() + 1e-6)
        viz_images["bc"] = Image.fromarray((scaled * 255).astype(np.uint8))

    if config.MODALITY_TO_RUN in {"bh", "all"}:
        path = config.DATA_ROOT / "bh-256" / f"{file_id}.tif"
        with rasterio.open(path) as src:
            bh = src.read(1).astype(np.float32)
        inputs.append(bh[..., None])
        scaled = (bh - bh.min()) / (bh.max() - bh.min() + 1e-6)
        viz_images["bh"] = Image.fromarray((scaled * 255).astype(np.uint8))

    if not inputs:
        raise ValueError(f"No data loaded for modality {config.MODALITY_TO_RUN}")

    combined = np.concatenate(inputs, axis=-1)
    transform = A.Compose(
        transforms=[
            A.Normalize(
                mean=tuple(config.CURRENT_MEAN),
                std=tuple(config.CURRENT_STD),
                max_pixel_value=1.0,
            ),
            ToTensorV2(),
        ]
    )

    tensor = transform(image=combined)["image"]
    return tensor, viz_images


def parse_tile_coordinates(file_id: str) -> Tuple[int, int]:
    parts = file_id.split("_")
    if len(parts) < 3:
        raise ValueError(f"Cannot parse tile coordinates from file_id: {file_id}")
    try:
        return int(parts[1]), int(parts[2])
    except ValueError as exc:  # noqa: BLE001
        raise ValueError(
            f"Cannot parse tile coordinates from file_id: {file_id}"
        ) from exc


def combine_prediction_masks_geospatially(
    prediction_masks: List[np.ndarray],
    file_ids: List[str],
    output_path: str,
    config: Config,
    target_crs: str = "EPSG:3857",
) -> Dict[str, Any]:
    if not prediction_masks:
        raise ValueError("At least one prediction mask is required")
    if len(prediction_masks) != len(file_ids):
        raise ValueError("Number of masks must match number of file IDs")

    tile_bounds: List[BoundingBox] = []
    coords: List[Tuple[int, int]] = []
    transforms: List[Tuple[rasterio.Affine, object]] = []

    for file_id in file_ids:
        coord = parse_tile_coordinates(file_id)
        coords.append(coord)
        satellite_path = config.DATA_ROOT / "satellite-256" / f"{file_id}.tif"
        with rasterio.open(satellite_path) as src:
            transforms.append((src.transform, src.crs))
            tile_bounds.append(src.bounds)

    min_x = min(c[0] for c in coords)
    max_x = max(c[0] for c in coords)
    min_y = min(c[1] for c in coords)
    max_y = max(c[1] for c in coords)

    grid_width = max_x - min_x + 1
    grid_height = max_y - min_y + 1
    tile_size = prediction_masks[0].shape[0]

    output_width = grid_width * tile_size
    output_height = grid_height * tile_size
    combined = np.zeros((output_height, output_width), dtype=np.uint8)

    overall_left = min(b.left for b in tile_bounds)
    overall_bottom = min(b.bottom for b in tile_bounds)
    overall_right = max(b.right for b in tile_bounds)
    overall_top = max(b.top for b in tile_bounds)

    pixel_width = (overall_right - overall_left) / output_width
    pixel_height = (overall_top - overall_bottom) / output_height

    transform = rasterio.Affine(
        pixel_width,
        0.0,
        overall_left,
        0.0,
        -pixel_height,
        overall_top,
    )

    for mask, bounds in zip(prediction_masks, tile_bounds):
        raster_x = int(round((bounds.left - overall_left) / pixel_width))
        raster_y = int(round((overall_top - bounds.top) / pixel_height))

        raster_x = max(0, min(raster_x, output_width - tile_size))
        raster_y = max(0, min(raster_y, output_height - tile_size))

        combined[raster_y : raster_y + tile_size, raster_x : raster_x + tile_size] = (
            mask.astype(np.uint8)
        )

    ref_crs = transforms[0][1]
    profile = {
        "driver": "GTiff",
        "height": output_height,
        "width": output_width,
        "count": 1,
        "dtype": "uint8",
        "crs": ref_crs,
        "transform": transform,
        "compress": "lzw",
    }

    if str(ref_crs) != target_crs:
        try:
            left, bottom, right, top = array_bounds(
                output_height, output_width, transform
            )
            dst_transform, dst_width, dst_height = calculate_default_transform(
                ref_crs,
                target_crs,
                output_width,
                output_height,
                left,
                bottom,
                right,
                top,
            )
            if not dst_width or not dst_height:
                raise ValueError("Invalid destination dimensions")
            dst_array = np.zeros((int(dst_height), int(dst_width)), dtype=np.uint8)
            reproject(
                source=combined,
                destination=dst_array,
                src_transform=transform,
                src_crs=ref_crs,
                dst_transform=dst_transform,
                dst_crs=target_crs,
                resampling=Resampling.nearest,
            )
            combined = dst_array
            profile.update(
                {
                    "crs": target_crs,
                    "transform": dst_transform,
                    "width": int(dst_width),
                    "height": int(dst_height),
                }
            )
        except Exception:  # noqa: BLE001
            target_crs = str(ref_crs)

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(combined, 1)

    png_path = output_path.replace(".tif", ".png")
    Image.fromarray((combined * 255).astype(np.uint8), mode="L").save(png_path)

    bounds = array_bounds(profile["height"], profile["width"], profile["transform"])
    leaflet_bounds = bounds
    if target_crs == "EPSG:3857":
        try:
            from pyproj import Transformer

            transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
            west_lng, south_lat = transformer.transform(bounds[0], bounds[1])
            east_lng, north_lat = transformer.transform(bounds[2], bounds[3])
            leaflet_bounds = (west_lng, south_lat, east_lng, north_lat)
        except Exception:  # noqa: BLE001
            leaflet_bounds = bounds

    return {
        "file_path": output_path,
        "png_path": png_path,
        "crs": target_crs,
        "bounds": {
            "west": leaflet_bounds[0],
            "south": leaflet_bounds[1],
            "east": leaflet_bounds[2],
            "north": leaflet_bounds[3],
        },
        "tile_grid": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "width": grid_width,
            "height": grid_height,
        },
        "dimensions": {"width": profile["width"], "height": profile["height"]},
        "num_tiles": len(prediction_masks),
    }


def combine_predictions_for_web_mapping(
    prediction_masks: List[np.ndarray],
    file_ids: List[str],
    config: Config,
    output_dir: str,
    filename: str,
) -> Dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    full_path = output_path / filename
    return combine_prediction_masks_geospatially(
        prediction_masks=prediction_masks,
        file_ids=file_ids,
        output_path=str(full_path),
        config=config,
    )


def create_leaflet_config(metadata: Dict[str, Any], tiff_url: str) -> Dict[str, Any]:
    bounds = metadata["bounds"]
    return {
        "tiff_url": tiff_url,
        "bounds": bounds,
        "center": [
            (bounds["south"] + bounds["north"]) / 2,
            (bounds["west"] + bounds["east"]) / 2,
        ],
        "zoom_levels": {"min": 10, "max": 18, "initial": 13},
        "tile_info": {
            "total_tiles": metadata["num_tiles"],
            "grid_size": f"{metadata['tile_grid']['width']}x{metadata['tile_grid']['height']}",
            "dimensions": f"{metadata['dimensions']['width']}x{metadata['dimensions']['height']}",
        },
        "crs": metadata["crs"],
        "format": "image/tiff",
    }
