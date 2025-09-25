# start_inference.py
"""
Simple startup script for SettleNet inference with clear options.
"""

import sys
from pathlib import Path


def main():
    print("🌍 SettleNet Inference Options")
    print("=" * 40)
    print()
    print("Choose how you want to run inference:")
    print()
    print("1. 🌐 Web Interface (recommended for visualization)")
    print("   - Runs FastAPI server with web interface")
    print("   - Shows visual results and performance benchmarks")
    print("   - Creates multiple TIFF files for different file counts")
    print("   - Includes API endpoints for frontend integration")
    print()
    print("2. 🖥️  Command Line (recommended for single inference)")
    print("   - Runs inference directly without web server")
    print("   - Creates a single web-ready TIFF file")
    print("   - Faster for single runs")
    print("   - Better for automation/scripting")
    print()

    while True:
        choice = input("Enter your choice (1 or 2): ").strip()

        if choice == "1":
            print()
            print("🌐 Starting web interface...")
            print("📋 Instructions:")
            print("   1. Server will start on http://localhost:8000")
            print("   2. Open that URL in your browser")
            print("   3. Inference will run automatically")
            print("   4. Results will be saved to app/static/")
            print("   5. Use Ctrl+C to stop the server")
            print()

            try:
                import uvicorn

                print("Starting server...")
                uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
            except ImportError:
                print("❌ uvicorn not found. Install with: pip install uvicorn")
                print("Or run manually: uvicorn app.main:app --reload")
            except KeyboardInterrupt:
                print("\n👋 Server stopped.")
            break

        elif choice == "2":
            print()
            print("🖥️  Command line inference")
            print("📋 Basic usage examples:")
            print()
            print("• Process all files:")
            print("  python run_inference.py")
            print()
            print("• Process 10 files with specific modality:")
            print("  python run_inference.py --num-files 10 --modality bc+sat")
            print()
            print("• Custom output:")
            print(
                "  python run_inference.py --num-files 50 --output-dir results --output-filename my_predictions.tif"
            )
            print()
            print("• See all options:")
            print("  python run_inference.py --help")
            print()

            while True:
                run_choice = (
                    input("Do you want to run with default settings now? (y/n): ")
                    .strip()
                    .lower()
                )

                if run_choice in ["y", "yes"]:
                    print("\n🚀 Running inference with default settings...")
                    try:
                        from run_inference import run_inference

                        result = run_inference()
                        if result:
                            print("\n✅ Inference completed successfully!")
                    except Exception as e:
                        print(f"\n❌ Error: {e}")
                        print("You can also run manually: python run_inference.py")
                    break
                elif run_choice in ["n", "no"]:
                    print("\n📋 Run manually with: python run_inference.py [options]")
                    break
                else:
                    print("Please enter 'y' or 'n'")
            break

        else:
            print("Please enter '1' or '2'")


if __name__ == "__main__":
    main()
