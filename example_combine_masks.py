# example_combine_masks.py
"""
Example script demonstrating how to use the combine_prediction_masks_to_tiff function.
This script creates sample prediction masks and combines them into a single TIFF file.
"""

import numpy as np
from pathlib import Path
import sys

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.utils.data_processing import (
    combine_prediction_masks_to_tiff,
    combine_predictions_from_inference,
)


def create_sample_masks(num_masks: int = 4, size: int = 256) -> tuple:
    """Create sample prediction masks for demonstration."""
    masks = []
    file_ids = []

    for i in range(num_masks):
        # Create a simple pattern for each mask
        mask = np.zeros((size, size), dtype=np.uint8)

        # Create different patterns for each mask
        if i == 0:
            # Diagonal line
            np.fill_diagonal(mask, 1)
        elif i == 1:
            # Circle in center
            center = size // 2
            radius = size // 4
            y, x = np.ogrid[:size, :size]
            mask_circle = (x - center) ** 2 + (y - center) ** 2 <= radius**2
            mask[mask_circle] = 1
        elif i == 2:
            # Checkerboard pattern
            mask[::20, ::20] = 1
        else:
            # Random noise pattern
            np.random.seed(42)
            mask = (np.random.random((size, size)) > 0.8).astype(np.uint8)

        masks.append(mask)
        file_ids.append(f"sample_{i:03d}")

    return masks, file_ids


def main():
    """Main function to demonstrate mask combination."""
    print("🔧 Creating sample prediction masks...")

    # Create sample masks
    sample_masks, sample_ids = create_sample_masks(num_masks=6)

    print(
        f"📊 Created {len(sample_masks)} sample masks of size {sample_masks[0].shape}"
    )

    # Method 1: Using the detailed function
    print("\n🔀 Method 1: Using combine_prediction_masks_to_tiff directly...")

    output_path_1 = "sample_combined_detailed.tif"
    combine_prediction_masks_to_tiff(
        prediction_masks=sample_masks,
        file_ids=sample_ids,
        output_path=output_path_1,
        tile_size=256,
        grid_cols=3,  # 3 columns, 2 rows for 6 masks
    )

    # Method 2: Using the convenience function
    print("\n🔀 Method 2: Using combine_predictions_from_inference...")

    output_path_2 = combine_predictions_from_inference(
        prediction_masks=sample_masks,
        file_ids=sample_ids,
        output_dir="sample_predictions",
        filename="combined_sample_predictions.tif",
    )

    print(f"\n✅ Successfully created combined TIFF files:")
    print(f"   - {output_path_1}")
    print(f"   - {output_path_2}")

    print("\n💡 You can now open these TIFF files in any GIS software or image viewer")
    print(
        "   to see how the individual prediction masks have been combined into a single file."
    )


if __name__ == "__main__":
    main()
