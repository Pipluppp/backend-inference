# SettleNet Local Inference Application

A FastAPI-based web application for running inference on your trained SettleNet models with performance benchmarking and visual results display.

## Project Structure

```
settlenet/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application and inference pipeline
│   ├── static/                 # Generated static files (images)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── components.py       # Neural network components (LayerNorm, ConvNeXt blocks, etc.)
│   │   └── architectures.py    # Model architectures (ConvNeXtUNet)
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration management
│   │   └── data_processing.py # Data loading and preprocessing
│   └── templates/
│       └── index.html         # Web interface template
├── data/
│   └── qc/
│       ├── satellite-256/     # RGB satellite images (.tif)
│       ├── bc-256/           # Building count images (.tif)
│       ├── bh-256/           # Building height images (.tif)
│       └── mask-256/         # Ground truth masks (.tif) 🆕
├── trained_models/           # Place your .pth model files here
├── requirements.txt
├── check_setup.py           # Setup verification script 🆕
└── README.md
```

## Setup Instructions

### 0. Verify Setup (Recommended)

Run the setup verification script to check your installation:

```bash
python check_setup.py
```

### 1. Install Dependencies

Navigate to the `settlenet` directory and install the required packages:

```bash
cd settlenet
pip install -r requirements.txt
```

### 2. Prepare Your Data

1. Place your `.tif` image tiles in the appropriate directories:
   - RGB satellite images → `data/qc/satellite-256/`
   - Building count images → `data/qc/bc-256/`
   - Building height images → `data/qc/bh-256/`
   - Ground truth masks → `data/qc/mask-256/` 🆕

2. Ensure that for any given tile ID (e.g., `tile_123`), the file `tile_123.tif` exists in all required modality folders based on your model configuration.

### 3. Add Your Trained Model

1. Place your trained model file (e.g., `convnext_bc_sat.pth`) in the `trained_models/` directory.

2. Update the configuration in `app/main.py`:

```python
APP_CONFIG = {
    "MODALITY_TO_RUN": "bc+sat",  # one of: "satellite", "bc", "bh", "bc+sat", "all"
    "MODEL_NAME": "ConvNeXtUNet", # one of: "ConvNeXtUNet", "SettleNet"
    "MODEL_FILENAME": "your_model.pth", # Your model filename
    "BENCHMARKS": [1, 10, 100] # Number of files to test for each benchmark
}
```

### 4. Run the Application

Start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

You should see output like:
```
INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
Configuration setup for MODALITY: bc+sat (4 channels)
Successfully loaded model 'ConvNeXtUNet' from 'trained_models/your_model.pth' onto CPU.
```

### 5. View Results

Open your web browser and navigate to `http://127.0.0.1:8000`

The application will:
- Run inference on your test data
- Display performance benchmarks for different batch sizes
- Show side-by-side visual comparisons of inputs and predictions

## Configuration Options

### Modalities
- `"satellite"`: RGB satellite imagery only (3 channels)
- `"bc"`: Building count only (1 channel)
- `"bh"`: Building height only (1 channel)
- `"bc+sat"`: Building count + RGB satellite (4 channels)
- `"all"`: All modalities (5 channels)

### Model Architectures
- `"ConvNeXtUNet"`: ConvNeXt-based U-Net architecture
- Additional architectures can be added to `app/models/architectures.py`

### Normalization Statistics
The application uses the normalization statistics from your training setup. Update these in `app/utils/config.py` if needed:

```python
RGB_MEAN: [0.33969313, 0.35239491, 0.28135468]
RGB_STD: [0.23594516, 0.20353660, 0.20314776]
BC_MEAN: [0.0009436231339350343]
BC_STD: [0.001719754422083497]
BH_MEAN: [3.086625337600708]
BH_STD: [5.610204696655273]
```

## Troubleshooting

1. **No test files found**: Ensure your data is in the correct directories with `.tif` extensions.

2. **Model loading errors**: Verify the model file exists and the architecture matches your trained model.

3. **Import errors**: Install all dependencies with `pip install -r requirements.txt`.

4. **Performance issues**: The application runs on CPU by default. For GPU inference, modify the device setting in `app/main.py`.

## Features

### 🆕 New Features (Latest Update)
- **Ground Truth Comparison**: Three-panel view showing Inputs | Ground Truth | Prediction
- **Progress Tracking**: Real-time progress bars during inference with emojis
- **Enhanced Console Output**: Detailed timing information and status updates
- **Mask Directory Support**: Automatic loading of ground truth masks from `mask-256/`

### Core Features
- **Performance Benchmarking**: Tests inference speed with different numbers of files
- **Visual Results**: Side-by-side-by-side comparison of inputs, ground truth, and predictions
- **Multi-modal Support**: Supports different combinations of input modalities
- **Web Interface**: Clean, responsive HTML interface for easy result viewing
- **Flexible Configuration**: Easy to modify for different models and data setups

### Application Workflow
1. **Data Loading**: Automatically scans for `.tif` files in each modality directory
2. **Model Loading**: Loads your trained PyTorch model with proper device mapping
3. **Inference Pipeline**: Runs inference with progress tracking and timing
4. **Visualization**: Generates comparative views saved as static images
5. **Web Display**: Serves results through a clean, responsive interface