# run_inference.py
"""
Command-line interface for running model inference and creating web-ready prediction TIFFs.
This script allows you to run inference without starting the web server.
"""

import os
import time
import argparse
from pathlib import Path
from typing import Optional
import torch
from PIL import Image
import numpy as np
from tqdm import tqdm

# Local module imports
from app.utils.config import setup_config
from app.utils.data_processing import (
    get_test_file_ids,
    load_and_preprocess_image,
    combine_predictions_for_web_mapping,
    create_leaflet_config,
    validate_for_web_mapping,
)
from app.models.architectures import ConvNeXtUNet


def load_model(model_name: str, model_filename: str, config, device):
    """Load the trained model."""
    model_path = Path("./trained_models") / model_filename
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file not found at {model_path}. Please place it in the 'trained_models' directory."
        )

    if model_name == "ConvNeXtUNet":
        model = ConvNeXtUNet(config)
    else:
        raise ValueError(f"Model name '{model_name}' not recognized.")

    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    print(f"✅ Loaded model '{model_name}' from '{model_path}'")
    return model


def run_inference(
    modality: str = "bc+sat",
    model_name: str = "ConvNeXtUNet",
    model_filename: str = "bc+sat-5z2uadhtpth.pth",
    num_files: Optional[int] = None,
    output_dir: str = "predictions",
    output_filename: Optional[str] = None,
    validate_data: bool = True,
):
    """
    Run model inference and create web-ready merged prediction TIFF.

    Args:
        modality: Data modality to use ("satellite", "bc", "bh", "bc+sat", "all")
        model_name: Model architecture name
        model_filename: Model file in trained_models directory
        num_files: Number of files to process (None = all available)
        output_dir: Output directory for results
        output_filename: Output filename (auto-generated if None)
        validate_data: Whether to validate data for web mapping

    Returns:
        dict: Metadata about the created prediction TIFF
    """

    print("🚀 SettleNet Inference Pipeline")
    print("=" * 50)

    # Setup
    config = setup_config(modality)
    device = torch.device("cpu")

    # Load model
    model = load_model(model_name, model_filename, config, device)

    # Get test files
    test_file_ids = get_test_file_ids(config)
    if not test_file_ids:
        raise ValueError("No test files found. Check your data directory.")

    # Determine how many files to process
    if num_files is None:
        num_files = len(test_file_ids)
    else:
        num_files = min(num_files, len(test_file_ids))

    subset_ids = test_file_ids[:num_files]

    print(f"📊 Processing {num_files} files with modality: {modality}")
    print(f"🧠 Using model: {model_name}")

    # Validate data if requested
    if validate_data:
        print(f"\n🔍 Validating data for web mapping...")
        validation = validate_for_web_mapping(subset_ids, config)

        if not validation["is_valid"]:
            print("❌ Validation failed:")
            for error in validation["errors"]:
                print(f"   - {error}")
            return None

        if validation["warnings"]:
            print("⚠️  Warnings:")
            for warning in validation["warnings"]:
                print(f"   - {warning}")

        print("✅ Data validation passed")

    # Run inference
    prediction_masks = []
    start_time = time.time()

    print(f"\n🔮 Running inference...")
    for file_id in tqdm(subset_ids, desc="Processing files", unit="file"):
        # Load and preprocess image
        image_tensor, _ = load_and_preprocess_image(file_id, config)
        image_tensor = image_tensor.unsqueeze(0).to(device)

        # Run inference
        with torch.no_grad():
            logits = model(image_tensor)
            pred_mask_np = (
                (torch.sigmoid(logits) > 0.5).squeeze().cpu().numpy().astype(np.uint8)
            )

        prediction_masks.append(pred_mask_np)

    inference_time = time.time() - start_time

    print(f"✅ Inference completed in {inference_time:.2f} seconds")
    print(f"📊 Average time per file: {inference_time/num_files:.3f} seconds")

    # Create output filename if not provided
    if output_filename is None:
        output_filename = (
            f"predictions_{modality}_{num_files}files_{int(time.time())}.tif"
        )

    # Combine into web-ready TIFF
    print(f"\n🗺️  Creating web-ready TIFF...")

    start_combine = time.time()
    web_metadata = combine_predictions_for_web_mapping(
        prediction_masks=prediction_masks,
        file_ids=subset_ids,
        config=config,
        output_dir=output_dir,
        filename=output_filename,
    )
    combine_time = time.time() - start_combine

    print(f"✅ TIFF creation completed in {combine_time:.2f} seconds")

    # Create Leaflet configuration
    tiff_url = f"/{output_dir}/{output_filename}"
    leaflet_config = create_leaflet_config(web_metadata, tiff_url)

    # Save Leaflet config
    config_path = Path(output_dir) / f"{Path(output_filename).stem}_leaflet_config.json"
    import json

    with open(config_path, "w") as f:
        json.dump(leaflet_config, f, indent=2)

    # Print summary
    print(f"\n🎉 Pipeline completed successfully!")
    print(f"📁 Output files:")
    print(f"   - TIFF: {web_metadata['file_path']}")
    print(f"   - Config: {config_path}")
    print(f"\n🗺️  Geographic info:")
    print(f"   - Bounds: {web_metadata['bounds']}")
    print(f"   - CRS: {web_metadata['crs']}")
    print(
        f"   - Grid: {web_metadata['tile_grid']['width']}x{web_metadata['tile_grid']['height']}"
    )
    print(
        f"   - Dimensions: {web_metadata['dimensions']['width']}x{web_metadata['dimensions']['height']}"
    )

    print(f"\n💡 Next steps:")
    print(f"   1. Serve the TIFF file through a web server")
    print(f"   2. Use the Leaflet config in your frontend")
    print(f"   3. Add the overlay to your map with proper bounds")

    return {
        "web_metadata": web_metadata,
        "leaflet_config": leaflet_config,
        "processing_stats": {
            "inference_time": inference_time,
            "combine_time": combine_time,
            "total_time": inference_time + combine_time,
            "files_processed": num_files,
            "avg_time_per_file": inference_time / num_files,
        },
    }


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Run SettleNet inference and create web-ready prediction TIFF"
    )

    parser.add_argument(
        "--modality",
        choices=["satellite", "bc", "bh", "bc+sat", "all"],
        default="bc+sat",
        help="Data modality to use (default: bc+sat)",
    )

    parser.add_argument(
        "--model-name",
        default="ConvNeXtUNet",
        help="Model architecture name (default: ConvNeXtUNet)",
    )

    parser.add_argument(
        "--model-file",
        default="bc+sat-5z2uadhtpth.pth",
        help="Model filename in trained_models directory (default: bc+sat-5z2uadhtpth.pth)",
    )

    parser.add_argument(
        "--num-files",
        type=int,
        help="Number of files to process (default: all available)",
    )

    parser.add_argument(
        "--output-dir",
        default="predictions",
        help="Output directory (default: predictions)",
    )

    parser.add_argument(
        "--output-filename", help="Output filename (auto-generated if not specified)"
    )

    parser.add_argument(
        "--no-validate", action="store_true", help="Skip data validation step"
    )

    args = parser.parse_args()

    try:
        result = run_inference(
            modality=args.modality,
            model_name=args.model_name,
            model_filename=args.model_file,
            num_files=args.num_files,
            output_dir=args.output_dir,
            output_filename=args.output_filename,
            validate_data=not args.no_validate,
        )

        if result:
            print(f"\n✨ Success! Ready for Leaflet integration.")
        else:
            print(f"\n❌ Pipeline failed. Check the errors above.")

    except Exception as e:
        print(f"\n💥 Error: {e}")
        raise


if __name__ == "__main__":
    main()
