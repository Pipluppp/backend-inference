# example_web_mapping.py
"""
Example script demonstrating web-mapping ready TIFF combination for Leaflet integration.
This script shows how to create geographically-correct combined prediction masks.
"""

import numpy as np
from pathlib import Path
import sys
import json

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.utils.config import setup_config
from app.utils.data_processing import (
    combine_predictions_for_web_mapping,
    create_leaflet_config,
    validate_for_web_mapping,
    get_test_file_ids,
)


def create_mock_predictions(file_ids: list, size: int = 256) -> list:
    """Create mock prediction masks for demonstration."""
    masks = []

    for i, file_id in enumerate(file_ids):
        # Create different patterns based on tile position
        mask = np.zeros((size, size), dtype=np.uint8)

        # Extract coordinates for position-based patterns
        try:
            parts = file_id.split("_")
            x, y = int(parts[1]), int(parts[2])

            # Create pattern based on tile coordinates
            if (x + y) % 2 == 0:
                # Checkerboard pattern
                mask[::16, ::16] = 1
            else:
                # Border pattern
                mask[0:10, :] = 1  # Top border
                mask[-10:, :] = 1  # Bottom border
                mask[:, 0:10] = 1  # Left border
                mask[:, -10:] = 1  # Right border

        except (ValueError, IndexError):
            # Fallback pattern
            mask[50:200, 50:200] = 1

        masks.append(mask)

    return masks


def main():
    """Demonstrate web-mapping ready TIFF combination."""
    print("🌍 Web-Mapping TIFF Combination Demo")
    print("=" * 50)

    # Setup configuration
    config = setup_config("bc+sat")

    # Get real file IDs from the dataset
    all_file_ids = get_test_file_ids(config)

    if not all_file_ids:
        print(
            "❌ No test files found. Please ensure your data directory is set up correctly."
        )
        return

    # Use a subset for demonstration (first 9 tiles for a 3x3 grid)
    demo_file_ids = all_file_ids[:9]
    print(f"📊 Using {len(demo_file_ids)} tiles for demonstration:")
    for fid in demo_file_ids:
        print(f"   - {fid}")

    # Validate data for web mapping
    print(f"\n🔍 Validating data for web mapping...")
    validation = validate_for_web_mapping(demo_file_ids, config)

    print(f"✅ Validation: {'PASSED' if validation['is_valid'] else 'FAILED'}")

    if validation["warnings"]:
        print("⚠️  Warnings:")
        for warning in validation["warnings"]:
            print(f"   - {warning}")

    if validation["errors"]:
        print("❌ Errors:")
        for error in validation["errors"]:
            print(f"   - {error}")
        return

    if validation["recommendations"]:
        print("💡 Recommendations:")
        for rec in validation["recommendations"]:
            print(f"   - {rec}")

    # Create mock prediction masks
    print(f"\n🔧 Creating mock prediction masks...")
    mock_predictions = create_mock_predictions(demo_file_ids)

    # Combine using web-mapping function
    print(f"\n🌐 Combining masks for web mapping...")

    metadata = combine_predictions_for_web_mapping(
        prediction_masks=mock_predictions,
        file_ids=demo_file_ids,
        config=config,
        output_dir="web_demo",
        filename="demo_web_predictions.tif",
    )

    # Create Leaflet configuration
    tiff_url = "/static/demo_web_predictions.tif"  # Example URL
    leaflet_config = create_leaflet_config(metadata, tiff_url)

    # Save configuration as JSON for frontend
    config_path = Path("web_demo") / "leaflet_config.json"
    with open(config_path, "w") as f:
        json.dump(leaflet_config, f, indent=2)

    print(f"\n✅ Web-mapping files created successfully!")
    print(f"📁 TIFF file: {metadata['file_path']}")
    print(f"📁 Leaflet config: {config_path}")

    print(f"\n🗺️  Geographic Information:")
    print(f"   CRS: {metadata['crs']}")
    print(f"   Bounds: {metadata['bounds']}")
    print(f"   Center: {leaflet_config['center']}")
    print(
        f"   Tile grid: {metadata['tile_grid']['width']}x{metadata['tile_grid']['height']}"
    )

    print(f"\n📋 Frontend Integration Code:")
    print("=" * 30)
    print("// JavaScript code for Leaflet integration")
    print(f"const bounds = {leaflet_config['bounds']};")
    print(f"const center = {leaflet_config['center']};")
    print(f"const tiffUrl = '{leaflet_config['tiff_url']}';")
    print("")
    print("// Add to your Leaflet map:")
    print("const imageOverlay = L.imageOverlay(tiffUrl, bounds);")
    print("map.fitBounds(bounds);")
    print("imageOverlay.addTo(map);")

    print(f"\n💡 Next Steps for Frontend:")
    print("   1. Serve the TIFF file through your web server")
    print("   2. Use the Leaflet config JSON in your frontend")
    print("   3. Consider using georaster-layer-for-leaflet for better TIFF support")
    print("   4. Add interactivity and styling as needed")


if __name__ == "__main__":
    main()
