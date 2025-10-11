# app/utils/config.py

from pathlib import Path
from dataclasses import dataclass, field


# Model mapping configuration
MODEL_MAPPING = {
    "convnext_all": {
        "model_name": "ConvNeXtUNet",
        "model_file": "convnext-all-7ir38hd4.pth",
        "modality": "all",
    },
    "convnext_bc": {
        "model_name": "ConvNeXtUNet",
        "model_file": "convnext-bc-g00wx4xl.pth",
        "modality": "bc",
    },
    "convnext_satellite": {
        "model_name": "ConvNeXtUNet",
        "model_file": "convnext-sat-xqkdckas.pth",
        "modality": "satellite",
    },
    "convnext_unet_all": {
        "model_name": "ConvNeXtUNet_PlainDecoder",
        "model_file": "convnext-unet-all.pth",
        "modality": "all",
    },
    "convnext_bh": {
        "model_name": "ConvNeXtUNet",
        "model_file": "convnext-bh.pth",
        "modality": "bh",
    },
    "settlenet": {
        "model_name": "SettleNet",
        "model_file": "settlenet-rxrj9b9b.pth",
        "modality": "all",
    },
}


@dataclass
class Config:
    """
    Central configuration class for the inference application.
    """

    # --- Data Paths (Update these if your structure is different) ---
    DATA_ROOT: Path = Path("./data/qc")

    # --- Model Selection (These will be overridden in main.py) ---
    MODALITY_TO_RUN: str = "bc+sat"

    # --- Normalization Stats (Must match your training setup) ---
    # NOTE: Since all inputs are now .tif, we assume they are in the 0-255 range.
    # The stats below are from your notebook (scaled from 0-1). We'll handle scaling during loading.
    RGB_MEAN: list[float] = field(
        default_factory=lambda: [0.33969313, 0.35239491, 0.28135468]
    )
    RGB_STD: list[float] = field(
        default_factory=lambda: [0.23594516, 0.20353660, 0.20314776]
    )
    BC_MEAN: list[float] = field(default_factory=lambda: [0.0009436231339350343])
    BC_STD: list[float] = field(default_factory=lambda: [0.001719754422083497])
    BH_MEAN: list[float] = field(default_factory=lambda: [3.086625337600708])
    BH_STD: list[float] = field(default_factory=lambda: [5.610204696655273])

    # --- Model Architecture (Must match the loaded model) ---
    ENCODER_CHANNEL_LIST: list[int] = field(default_factory=lambda: [80, 160, 320, 640])
    ENCODER_BLOCKS_PER_STAGE: list[int] = field(default_factory=lambda: [2, 2, 8, 2])
    DECODER_CONVNEXT_BLOCKS: list[int] = field(default_factory=lambda: [2, 2, 2, 2])
    FINAL_UPSAMPLING_CHANNELS: list[int] = field(default_factory=lambda: [80, 40, 20])
    UNET_DECODER_CHANNEL_LIST: list[int] = field(
        default_factory=lambda: [512, 256, 128, 64]
    )
    ENCODER_DROP_PATH_RATE: float = 0.0
    ENCODER_LAYER_SCALE_INIT_VALUE: float = 1e-6

    # --- Dynamic Properties (set by setup_config) ---
    INPUT_CHANNELS: int = 0
    CURRENT_MEAN: list[float] = field(default_factory=list)
    CURRENT_STD: list[float] = field(default_factory=list)


def get_model_config(model_type: str) -> dict:
    """Get model configuration based on frontend model selection."""
    if model_type not in MODEL_MAPPING:
        raise ValueError(
            f"Unknown model type: {model_type}. Available types: {list(MODEL_MAPPING.keys())}"
        )

    return MODEL_MAPPING[model_type]


def setup_config(modality: str) -> Config:
    """Initializes and dynamically updates the configuration based on the chosen modality."""
    config = Config()
    config.MODALITY_TO_RUN = modality

    if config.MODALITY_TO_RUN == "satellite":
        config.INPUT_CHANNELS = 3
        config.CURRENT_MEAN = config.RGB_MEAN
        config.CURRENT_STD = config.RGB_STD
    elif config.MODALITY_TO_RUN == "bc":
        config.INPUT_CHANNELS = 1
        config.CURRENT_MEAN = config.BC_MEAN
        config.CURRENT_STD = config.BC_STD
    elif config.MODALITY_TO_RUN == "bh":
        config.INPUT_CHANNELS = 1
        config.CURRENT_MEAN = config.BH_MEAN
        config.CURRENT_STD = config.BH_STD
    elif config.MODALITY_TO_RUN == "bc+sat":
        config.INPUT_CHANNELS = 4
        config.CURRENT_MEAN = config.RGB_MEAN + config.BC_MEAN
        config.CURRENT_STD = config.RGB_STD + config.BC_STD
    elif config.MODALITY_TO_RUN == "all":
        config.INPUT_CHANNELS = 5
        config.CURRENT_MEAN = config.RGB_MEAN + config.BC_MEAN + config.BH_MEAN
        config.CURRENT_STD = config.RGB_STD + config.BC_STD + config.BH_STD
    else:
        raise ValueError(
            f"MODALITY_TO_RUN must be one of 'satellite', 'bc', 'bh', 'bc+sat', or 'all'."
        )

    print(
        f"Configuration setup for MODALITY: {config.MODALITY_TO_RUN} ({config.INPUT_CHANNELS} channels)"
    )
    return config
