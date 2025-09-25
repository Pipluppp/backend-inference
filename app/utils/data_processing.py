# app/utils/data_processing.py

import os
from pathlib import Path
import numpy as np
import rasterio
import rasterio.transform
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


def combine_prediction_masks_to_tiff(
    prediction_masks: List[np.ndarray],
    file_ids: List[str],
    output_path: str,
    tile_size: int = 256,
    overlap: int = 0,
    grid_cols: int = None,
    reference_tiff_path: str = None,
) -> None:
    """
    Combines multiple prediction masks into a single TIFF file.

    Args:
        prediction_masks: List of 2D numpy arrays containing prediction masks (0s and 1s)
        file_ids: List of file IDs corresponding to each prediction mask
        output_path: Path where the combined TIFF file will be saved
        tile_size: Size of each individual tile (default: 256)
        overlap: Overlap between tiles in pixels (default: 0)
        grid_cols: Number of columns in the output grid. If None, creates a square grid
        reference_tiff_path: Path to a reference TIFF file to copy geospatial metadata from
    """
    if len(prediction_masks) != len(file_ids):
        raise ValueError("Number of prediction masks must match number of file IDs")

    if len(prediction_masks) == 0:
        raise ValueError("At least one prediction mask is required")

    # Determine grid dimensions
    num_tiles = len(prediction_masks)
    if grid_cols is None:
        grid_cols = int(np.ceil(np.sqrt(num_tiles)))
    grid_rows = int(np.ceil(num_tiles / grid_cols))

    # Calculate output image dimensions
    effective_tile_size = tile_size - overlap
    output_width = grid_cols * effective_tile_size + overlap
    output_height = grid_rows * effective_tile_size + overlap

    # Initialize the combined mask
    combined_mask = np.zeros((output_height, output_width), dtype=np.uint8)

    # Place each mask in the grid
    for i, (mask, file_id) in enumerate(zip(prediction_masks, file_ids)):
        row = i // grid_cols
        col = i % grid_cols

        # Calculate position in the combined image
        start_y = row * effective_tile_size
        start_x = col * effective_tile_size
        end_y = start_y + tile_size
        end_x = start_x + tile_size

        # Ensure mask is the right size and type
        if mask.shape != (tile_size, tile_size):
            raise ValueError(
                f"Mask for {file_id} has shape {mask.shape}, expected ({tile_size}, {tile_size})"
            )

        # Convert to uint8 if necessary
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)

        # Place the mask in the combined image
        combined_mask[start_y:end_y, start_x:end_x] = mask

    # Set up rasterio profile
    profile = {
        "driver": "GTiff",
        "height": output_height,
        "width": output_width,
        "count": 1,
        "dtype": "uint8",
        "compress": "lzw",
    }

    # If reference TIFF is provided, copy geospatial metadata
    if reference_tiff_path and Path(reference_tiff_path).exists():
        try:
            with rasterio.open(reference_tiff_path) as ref:
                # Scale the transform based on the new dimensions
                ref_transform = ref.transform
                scale_x = ref.width / output_width
                scale_y = ref.height / output_height

                # Create new transform with scaled pixel sizes
                new_transform = rasterio.Affine(
                    ref_transform.a * scale_x,  # pixel width
                    ref_transform.b,  # rotation
                    ref_transform.c,  # top-left x
                    ref_transform.d,  # rotation
                    ref_transform.e * scale_y,  # pixel height (negative)
                    ref_transform.f,  # top-left y
                )

                profile.update({"crs": ref.crs, "transform": new_transform})
        except Exception as e:
            print(
                f"Warning: Could not copy geospatial metadata from {reference_tiff_path}: {e}"
            )

    # Write the combined mask to TIFF
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(combined_mask, 1)

    print(f"Combined {num_tiles} prediction masks into {output_path}")
    print(f"Output dimensions: {output_width} x {output_height}")


def parse_tile_coordinates(file_id: str) -> tuple[int, int]:
    """
    Parse tile coordinates from file ID.

    Args:
        file_id: File ID in format 'qc_x_y' or similar

    Returns:
        tuple: (x, y) tile coordinates
    """
    parts = file_id.split("_")
    if len(parts) >= 3:
        try:
            x = int(parts[1])
            y = int(parts[2])
            return x, y
        except ValueError:
            pass
    raise ValueError(f"Cannot parse tile coordinates from file_id: {file_id}")


def combine_prediction_masks_geospatially(
    prediction_masks: List[np.ndarray],
    file_ids: List[str],
    output_path: str,
    config: Config,
    target_crs: str = "EPSG:3857",  # Web Mercator to match Google Maps
    create_cog: bool = True,
) -> dict:
    """
    Combines prediction masks based on their actual geographic positions for web mapping.

    Args:
        prediction_masks: List of 2D numpy arrays containing prediction masks
        file_ids: List of file IDs in format 'qc_x_y'
        output_path: Path where the combined TIFF will be saved
        config: Configuration object with data paths
        target_crs: Target CRS for web mapping (default: Web Mercator)
        create_cog: Whether to create Cloud Optimized GeoTIFF

    Returns:
        dict: Metadata including bounds, CRS, and file info for frontend
    """
    if len(prediction_masks) != len(file_ids):
        raise ValueError("Number of prediction masks must match number of file IDs")

    if len(prediction_masks) == 0:
        raise ValueError("At least one prediction mask is required")

    # Parse tile coordinates and get reference geospatial info
    tile_coords = []
    tile_transforms = []
    tile_bounds = []

    for file_id in file_ids:
        try:
            x, y = parse_tile_coordinates(file_id)
            tile_coords.append((x, y))

            # Get transform and actual geographic bounds from corresponding satellite image
            satellite_path = config.DATA_ROOT / "satellite-256" / f"{file_id}.tif"
            with rasterio.open(satellite_path) as src:
                tile_transforms.append((src.transform, src.crs))
                tile_bounds.append(src.bounds)  # Get actual geographic bounds
                
                # Debug: Print the original CRS for the first tile
                if len(tile_transforms) == 1:
                    print(f"DEBUG: Original tile CRS: {src.crs}")
                    print(f"DEBUG: Original tile transform: {src.transform}")
                    print(f"DEBUG: Original tile bounds: {src.bounds}")
                    print(f"DEBUG: Tile size: {src.width}x{src.height}")
        except (ValueError, FileNotFoundError) as e:
            print(f"Warning: Could not process {file_id}: {e}")
            continue

    if not tile_coords:
        raise ValueError("No valid tile coordinates found")

    # Calculate the overall geographic bounds from all tiles
    if tile_bounds:
        # Get the overall bounding box from actual geographic bounds
        all_lefts = [bounds.left for bounds in tile_bounds]
        all_bottoms = [bounds.bottom for bounds in tile_bounds]
        all_rights = [bounds.right for bounds in tile_bounds]
        all_tops = [bounds.top for bounds in tile_bounds]
        
        overall_left = min(all_lefts)
        overall_bottom = min(all_bottoms)
        overall_right = max(all_rights)
        overall_top = max(all_tops)
        
        print(f"DEBUG: Overall geographic bounds: left={overall_left}, bottom={overall_bottom}, right={overall_right}, top={overall_top}")
    else:
        raise ValueError("No tile bounds found")

    # Calculate tile grid extent for raster positioning
    min_x = min(coord[0] for coord in tile_coords)
    max_x = max(coord[0] for coord in tile_coords)
    min_y = min(coord[1] for coord in tile_coords)
    max_y = max(coord[1] for coord in tile_coords)

    # Calculate output dimensions based on tile grid
    grid_width = max_x - min_x + 1
    grid_height = max_y - min_y + 1
    tile_size = prediction_masks[0].shape[0]  # Assuming square tiles

    output_width = grid_width * tile_size
    output_height = grid_height * tile_size

    # Initialize combined mask
    combined_mask = np.zeros((output_height, output_width), dtype=np.uint8)

    # Get reference CRS from first tile
    ref_transform, ref_crs = tile_transforms[0]
    
    # Create a transform for the combined image using actual geographic bounds
    # Calculate pixel size based on the overall bounds and output dimensions
    pixel_width = (overall_right - overall_left) / output_width
    pixel_height = (overall_top - overall_bottom) / output_height  # Positive value
    
    print(f"DEBUG: Calculated pixel size: width={pixel_width}, height={pixel_height}")

    # Create transform: top-left corner at overall_left, overall_top
    combined_transform = rasterio.Affine(
        pixel_width,      # pixel width
        0.0,              # rotation
        overall_left,     # geographic X origin (left edge)
        0.0,              # rotation  
        -pixel_height,    # pixel height (negative for north-up orientation)
        overall_top       # geographic Y origin (top edge)
    )
    
    print(f"DEBUG: Combined transform: {combined_transform}")

    # Place each mask at its correct position using geographic coordinates
    for i, (mask, file_id, (tile_x, tile_y)) in enumerate(zip(prediction_masks, file_ids, tile_coords)):
        # Get the geographic bounds for this specific tile
        tile_bound = tile_bounds[i]
        
        # Calculate the raster position based on geographic coordinates
        # Convert geographic position to pixel position in the combined raster
        raster_x = int((tile_bound.left - overall_left) / pixel_width)
        raster_y = int((overall_top - tile_bound.top) / pixel_height)  # Y is flipped in raster space
        
        print(f"DEBUG: Tile {file_id}: geographic bounds {tile_bound}, raster position ({raster_x}, {raster_y})")

        # Ensure we don't go out of bounds
        raster_x = max(0, min(raster_x, output_width - tile_size))
        raster_y = max(0, min(raster_y, output_height - tile_size))

        # Ensure mask is the right type
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)

        # Place the mask
        combined_mask[
            raster_y : raster_y + tile_size, raster_x : raster_x + tile_size
        ] = mask
        
    print(f"DEBUG: Placed {len(prediction_masks)} masks in combined raster")

    # Set up rasterio profile
    profile = {
        "driver": "GTiff",
        "height": output_height,
        "width": output_width,
        "count": 1,
        "dtype": "uint8",
        "crs": ref_crs,
        "transform": combined_transform,
        "compress": "lzw",
    }

    # Add COG-specific options if requested
    if create_cog:
        profile.update(
            {
                "tiled": True,
                "blockxsize": 512,
                "blockysize": 512,
                "COMPRESS": "LZW",
                "BIGTIFF": "IF_SAFER",
            }
        )

    # Reproject to target CRS if different from source
    if target_crs != str(ref_crs):
        try:
            from rasterio.warp import calculate_default_transform, reproject, Resampling
            from pyproj import Transformer

            # Get the bounds of the combined mask in the original CRS
            left, bottom, right, top = rasterio.transform.array_bounds(
                output_height, output_width, combined_transform
            )
            
            print(f"DEBUG: Original bounds in {ref_crs}: left={left}, bottom={bottom}, right={right}, top={top}")

            # Calculate transform for target CRS using proper bounds
            dst_transform, dst_width, dst_height = calculate_default_transform(
                ref_crs,
                target_crs,
                output_width,
                output_height,
                left, bottom, right, top
            )
            
            print(f"DEBUG: Target CRS: {target_crs}")
            print(f"DEBUG: Destination transform: {dst_transform}")
            print(f"DEBUG: Destination dimensions: {dst_width}x{dst_height}")

            # Validate dimensions
            if dst_width is None or dst_height is None or dst_width <= 0 or dst_height <= 0:
                print(f"WARNING: Invalid destination dimensions: {dst_width}x{dst_height}, skipping reprojection")
                # Use original data without reprojection
                dst_array = combined_mask
                dst_transform = combined_transform
                dst_width = output_width
                dst_height = output_height
            else:
                # Create reprojected array
                dst_array = np.zeros((int(dst_height), int(dst_width)), dtype=np.uint8)

                reproject(
                    source=combined_mask,
                    destination=dst_array,
                    src_transform=combined_transform,
                    src_crs=ref_crs,
                    dst_transform=dst_transform,
                    dst_crs=target_crs,
                    resampling=Resampling.nearest,
                )

            # Update profile for reprojected data
            profile.update(
                {
                    "crs": target_crs,
                    "transform": dst_transform,
                    "width": int(dst_width),
                    "height": int(dst_height),
                }
            )

            combined_mask = dst_array

        except ImportError:
            print("Warning: Could not reproject to target CRS. Keeping original CRS.")
            target_crs = str(ref_crs)

    # Write the combined mask
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(combined_mask, 1)

    # Also create a PNG version for web display (Leaflet imageOverlay doesn't support TIFF)
    png_path = output_path.replace(".tif", ".png")
    # Convert to PIL Image and save as PNG
    combined_mask_viz = (combined_mask * 255).astype(np.uint8)  # Convert to 0-255 range
    from PIL import Image

    png_image = Image.fromarray(combined_mask_viz, mode="L")  # 'L' for grayscale
    png_image.save(png_path)

    # Calculate geographic bounds for frontend
    bounds = rasterio.transform.array_bounds(
        profile["height"], profile["width"], profile["transform"]
    )

    # Convert bounds to WGS84 (lat/lng) for Leaflet if they're in Web Mercator
    leaflet_bounds = bounds
    if target_crs == "EPSG:3857":
        try:
            from pyproj import Transformer

            # Create transformer from Web Mercator to WGS84
            transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
            # Transform bounds (west, south, east, north)
            west_lng, south_lat = transformer.transform(bounds[0], bounds[1])
            east_lng, north_lat = transformer.transform(bounds[2], bounds[3])
            leaflet_bounds = (west_lng, south_lat, east_lng, north_lat)
        except ImportError:
            print("Warning: pyproj not available, using original bounds")

    # Return metadata for frontend integration
    metadata = {
        "file_path": output_path,
        "png_path": png_path,  # Add PNG path for web display
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

    print(
        f"Combined {len(prediction_masks)} prediction masks geospatially into {output_path}"
    )
    print(f"Geographic bounds: {metadata['bounds']}")
    print(f"CRS: {target_crs}")

    return metadata


def combine_predictions_from_inference(
    prediction_masks: List[np.ndarray],
    file_ids: List[str],
    output_dir: str = "predictions",
    filename: str = "combined_predictions.tif",
) -> str:
    """
    Convenience function to combine prediction masks from model inference.

    Args:
        prediction_masks: List of prediction masks from model inference
        file_ids: List of file IDs corresponding to predictions
        output_dir: Directory to save the combined TIFF (default: "predictions")
        filename: Name of the output file (default: "combined_predictions.tif")

    Returns:
        str: Path to the saved combined TIFF file
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Full path to output file
    full_output_path = output_path / filename

    # Combine the masks
    combine_prediction_masks_to_tiff(
        prediction_masks=prediction_masks,
        file_ids=file_ids,
        output_path=str(full_output_path),
    )

    return str(full_output_path)


def combine_predictions_for_web_mapping(
    prediction_masks: List[np.ndarray],
    file_ids: List[str],
    config: Config,
    output_dir: str = "web_predictions",
    filename: str = "predictions_web.tif",
) -> dict:
    """
    Web-mapping optimized function to combine prediction masks with proper georeferencing.

    Args:
        prediction_masks: List of prediction masks from model inference
        file_ids: List of file IDs in format 'qc_x_y'
        config: Configuration object
        output_dir: Directory to save the web-optimized TIFF
        filename: Name of the output file

    Returns:
        dict: Complete metadata for frontend Leaflet integration
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Full path to output file
    full_output_path = output_path / filename

    # Use the geospatially-aware combination function
    metadata = combine_prediction_masks_geospatially(
        prediction_masks=prediction_masks,
        file_ids=file_ids,
        output_path=str(full_output_path),
        config=config,
        target_crs="EPSG:3857",  # Web Mercator to match Google Maps
        create_cog=True,
    )

    return metadata


def get_leaflet_bounds_from_metadata(metadata: dict) -> list:
    """
    Convert metadata bounds to Leaflet-compatible format.

    Args:
        metadata: Metadata dict from combine_predictions_for_web_mapping

    Returns:
        list: [[south, west], [north, east]] bounds for Leaflet
    """
    bounds = metadata["bounds"]
    return [
        [bounds["south"], bounds["west"]],  # Southwest corner
        [bounds["north"], bounds["east"]],  # Northeast corner
    ]


def create_leaflet_config(metadata: dict, tiff_url: str) -> dict:
    """
    Create a complete configuration object for Leaflet frontend integration.

    Args:
        metadata: Metadata from web mapping function
        tiff_url: URL where the TIFF file will be accessible

    Returns:
        dict: Complete Leaflet configuration
    """
    return {
        "tiff_url": tiff_url,
        "bounds": metadata[
            "bounds"
        ],  # Use the original bounds format {north, south, east, west}
        "center": [
            (metadata["bounds"]["south"] + metadata["bounds"]["north"]) / 2,
            (metadata["bounds"]["west"] + metadata["bounds"]["east"]) / 2,
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


def validate_for_web_mapping(file_ids: List[str], config: Config) -> dict:
    """
    Validate that the data is suitable for web mapping and return diagnostics.

    Args:
        file_ids: List of file IDs to validate
        config: Configuration object

    Returns:
        dict: Validation results and recommendations
    """
    validation_results = {
        "is_valid": True,
        "warnings": [],
        "errors": [],
        "tile_info": {},
        "recommendations": [],
    }

    # Check if file IDs can be parsed as coordinates
    valid_coords = []
    for file_id in file_ids:
        try:
            x, y = parse_tile_coordinates(file_id)
            valid_coords.append((x, y))
        except ValueError:
            validation_results["errors"].append(
                f"Cannot parse coordinates from {file_id}"
            )
            validation_results["is_valid"] = False

    if valid_coords:
        # Check for spatial coverage
        min_x, max_x = min(c[0] for c in valid_coords), max(c[0] for c in valid_coords)
        min_y, max_y = min(c[1] for c in valid_coords), max(c[1] for c in valid_coords)

        expected_tiles = (max_x - min_x + 1) * (max_y - min_y + 1)
        actual_tiles = len(valid_coords)

        validation_results["tile_info"] = {
            "extent": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
            "expected_tiles": expected_tiles,
            "actual_tiles": actual_tiles,
            "coverage": actual_tiles / expected_tiles * 100,
        }

        if actual_tiles < expected_tiles:
            validation_results["warnings"].append(
                f"Missing {expected_tiles - actual_tiles} tiles from complete grid"
            )

        # Check geospatial metadata
        try:
            sample_path = config.DATA_ROOT / "satellite-256" / f"{file_ids[0]}.tif"
            with rasterio.open(sample_path) as src:
                if src.crs is None:
                    validation_results["errors"].append(
                        "No CRS information in source files"
                    )
                    validation_results["is_valid"] = False
                elif str(src.crs) == "EPSG:4326":
                    validation_results["recommendations"].append(
                        "Data is in WGS84 - will be reprojected to Web Mercator for web mapping"
                    )
        except Exception as e:
            validation_results["errors"].append(f"Cannot read geospatial metadata: {e}")
            validation_results["is_valid"] = False

    return validation_results
