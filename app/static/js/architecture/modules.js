const DEFAULT_SCALE = {
  base: 0.65,
  medium: 0.55,
  small: 0.45,
};

function cloneModules(definitions) {
  return definitions.map((definition) => ({
    ...definition,
    targetIds: definition.targetIds ? [...definition.targetIds] : [],
    stats: definition.stats ? definition.stats.map((stat) => ({ ...stat })) : [],
    details: definition.details ? [...definition.details] : [],
  }));
}

const convNeXtModuleBlueprint = [
  {
    id: "inputs",
    targetIds: ["text1-9-3-1-7-7-4-3-2-4-1"],
    title: "Inputs · Remote sensing stack",
    summary: "Batch 64 tiles, 5 channels, 256×256.",
    stats: [
      { label: "Tensor", value: "[5, 256, 256]" },
      { label: "Role", value: "Data ingestion" },
    ],
    details: [],
    margin: 3,
  },
  {
    id: "stem",
    targetIds: ["text1-9-3-3-0"],
    title: "Stem · Patchify convolution",
    summary: "Conv2d 4×4 stride4 projects tiles to 80-channel tokens.",
    image: "media/architecture/convolution.gif",
    imageAlt: "Animated convolution showing the patchify projection",
    stats: [
      { label: "Output", value: "[80, 64, 64]" },
      { label: "Components", value: "Conv2d + LayerNorm" },
    ],
    details: [],
  },
  {
    id: "enc_stage1",
    targetIds: ["text1-9-3"],
    title: "Encoder stage 1 · 64×64×80",
    summary: "2 ConvNeXt blocks keep the 64×64×80 skip tensor.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[80, 64, 64]" },
      { label: "Blocks", value: "2 × ConvNeXtBlock" },
    ],
    details: [],
  },
  {
    id: "down1",
    targetIds: ["text1-9-3-3-3"],
    title: "Downsampling 1 · 2×2 conv",
    summary: "Stride-2 Conv2d -> 32×32 spatial, 160 channels.",
    image: "media/architecture/convolution.gif",
    imageAlt: "Animated convolution illustrating stride-2 downsampling",
    stats: [
      { label: "Output", value: "[160, 32, 32]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
  },
  {
    id: "enc_stage2",
    targetIds: ["text1-9-3-3"],
    title: "Encoder stage 2 · 32×32×160",
    summary: "2 ConvNeXt blocks on 32×32×160 skip.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[160, 32, 32]" },
      { label: "Blocks", value: "2 × ConvNeXtBlock" },
    ],
    details: [],
  },
  {
    id: "down2",
    targetIds: ["text1-9-3-3-3-5"],
    title: "Downsampling 2 · 2×2 conv",
    summary: "Stride-2 Conv2d -> 16×16 map, 320 channels.",
    image: "media/architecture/convolution.gif",
    imageAlt: "Animated convolution illustrating stride-2 downsampling",
    stats: [
      { label: "Output", value: "[320, 16, 16]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
  },
  {
    id: "enc_stage3",
    targetIds: ["text1-9-3-1"],
    title: "Encoder stage 3 · 16×16×320",
    summary: "8 ConvNeXt blocks process 16×16×320 features.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[320, 16, 16]" },
      { label: "Blocks", value: "8 × ConvNeXtBlock" },
    ],
    details: [],
  },
  {
    id: "down3",
    targetIds: ["text1-9-3-3-3-0"],
    title: "Downsampling 3 · 2×2 conv",
    summary: "Stride-2 Conv2d builds the 8×8×640 latent grid.",
    image: "media/architecture/convolution.gif",
    imageAlt: "Animated convolution illustrating stride-2 downsampling",
    stats: [
      { label: "Output", value: "[640, 8, 8]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
  },
  {
    id: "enc_stage4",
    targetIds: ["text1-9-3-1-7"],
    title: "Encoder stage 4 · 8×8×640",
    summary: "2 ConvNeXt blocks on the 8×8×640 latent grid.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[640, 8, 8]" },
      { label: "Blocks", value: "2 × ConvNeXtBlock" },
    ],
    details: [],
  },
  {
    id: "bottleneck",
    targetIds: ["text1-9-3-1-7-9"],
    title: "Bottleneck · ConvNeXt blocks",
    summary: "2 ConvNeXt blocks sit at the decoder bottleneck.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[640, 8, 8]" },
      { label: "Blocks", value: "2 × ConvNeXtBlock" },
    ],
    details: [],
  },
  {
    id: "dec_up1",
    targetIds: ["text1-9-3-3-3-7", "group-28-0-0", "group-28-0-8"],
    title: "Decoder upsample 1 · 3×3 TConv 16×16×320",
    summary: "ConvTranspose2d doubles 8×8 latent to 16×16×320.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[320, 16, 16]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
    margin: 2.2,
  },
  {
    id: "dec_stage1",
    targetIds: [
      "text1-9-3-1-7-7",
      "group-26-2-5-28",
      "group-26-2-8",
      "group-26-2-5",
    ],
    title: "Decoder stage 1 · ConvNeXt blocks 16×16×320",
    summary: "2 ConvNeXt blocks on the 16×16×320 fused tensor.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[320, 16, 16]" },
      { label: "Blocks", value: "2 × ConvNeXtBlock" },
    ],
    details: [],
    margin: 2,
  },
  {
    id: "dec_up2",
    targetIds: ["text1-9-3-3-3-7-3", "group-28-0-8-4"],
    title: "Decoder upsample 2 · 3×3 TConv 32×32×160",
    summary: "ConvTranspose2d lifts 16×16×320 to 32×32×160.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[160, 32, 32]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
    margin: 2,
  },
  {
    id: "dec_stage2",
    targetIds: [
      "text1-9-3-1-7-7-4-7",
      "group-23-6-4-8",
      "group-23-6-5",
      "group-23-6-4",
    ],
    title: "Decoder stage 2 · ConvNeXt blocks 32×32×160",
    summary: "2 ConvNeXt blocks handle the 32×32×160 merge.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[160, 32, 32]" },
      { label: "Blocks", value: "2 × ConvNeXtBlock" },
    ],
    details: [],
    margin: 2,
  },
  {
    id: "dec_up3",
    targetIds: ["text1-9-3-3-3-7-2", "group-28-0-8-2"],
    title: "Decoder upsample 3 · 3×3 TConv 64×64×80",
    summary: "ConvTranspose2d restores the 64×64×80 grid.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[80, 64, 64]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
    margin: 2,
  },
  {
    id: "dec_stage3",
    targetIds: [
      "text1-9-3-1-7-7-4",
      "group-26-2-5-7",
      "group-23-6-4-1",
    ],
    title: "Decoder stage 3 · ConvNeXt blocks 64×64×80",
    summary: "2 ConvNeXt blocks tune the 64×64×80 tensor.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[80, 64, 64]" },
      { label: "Blocks", value: "2 × ConvNeXtBlock" },
    ],
    details: [],
    margin: 2,
  },
  {
    id: "dec_stage4",
    targetIds: [
      "text1-9-3-3-3-7-2-8",
      "text1-9-3-1-7-7-4-3-2-7",
    ],
    title: "Decoder stage 4 · Upsample 128×128×40",
    summary: "Transpose conv + smoothing build the 128×128×40 map.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[40, 128, 128]" },
      { label: "Layers", value: "ConvTranspose2d + Conv2d + LayerNorm" },
    ],
    details: [],
    margin: 2,
  },
  {
    id: "dec_stage5",
    targetIds: ["text1-9-3-3-3-7-2-8-0"],
    title: "Decoder stage 5 · Prediction head",
    summary: "Final transpose conv returns 256×256 before 1×1 head.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[1, 256, 256]" },
      { label: "Layers", value: "ConvTranspose2d + Conv2d" },
    ],
    details: [],
    margin: 2.2,
  },
  {
    id: "outputs",
    targetIds: ["text1-9-3-1-7-7-4-3-2-4"],
    title: "Outputs · Binary segmentation mask",
    summary: "Logits keep the 256×256 grid for pixel alignment.",
    stats: [
      { label: "Tensor", value: "[1, 256, 256]" },
      { label: "Activation", value: "Apply sigmoid outside the model" },
      { label: "Task", value: "Binary mask" },
    ],
    details: [],
    margin: 3,
  },
];

function buildConvNeXtModules() {
  return cloneModules(convNeXtModuleBlueprint);
}

function buildConvNeXtUNetModules() {
  const modules = cloneModules(convNeXtModuleBlueprint);
  const byId = new Map(modules.map((module) => [module.id, module]));

  const updateModule = (id, updater) => {
    const module = byId.get(id);
    if (module) {
      updater(module);
    }
  };

  updateModule("bottleneck", (module) => {
    module.title = "Bottleneck · U-Net double conv";
    module.summary = "Double 3×3 Conv+BN+ReLU keeps the 8×8×640 latent.";
    module.image = "media/architecture/unet-block.png";
    module.imageAlt = "U-Net double convolution schematic";
    module.stats = [
      { label: "Output", value: "[640, 8, 8]" },
      { label: "Layers", value: "2 × (Conv2d + BatchNorm2d + ReLU)" },
    ];
    module.details = [];
  });

  updateModule("dec_up1", (module) => {
    module.title = "Decoder upsample 1 · 2×2 TConv 16×16×512";
    module.summary = "ConvTranspose2d makes a 16×16×512 decoder map.";
    module.stats = [
      { label: "Output", value: "[512, 16, 16]" },
      { label: "Stride", value: "2 × 2" },
    ];
    module.details = [];
  });

  updateModule("dec_stage1", (module) => {
    module.title = "Decoder stage 1 · U-Net block 16×16×512";
    module.summary = "Double 3×3 Conv+BN refines the 16×16×512 concat.";
    module.image = "media/architecture/unet-block.png";
    module.imageAlt = "U-Net double convolution schematic";
    module.stats = [
      { label: "Output", value: "[512, 16, 16]" },
      { label: "Layers", value: "2 × (Conv2d + BatchNorm2d + ReLU)" },
    ];
    module.details = [];
  });

  updateModule("dec_up2", (module) => {
    module.title = "Decoder upsample 2 · 2×2 TConv 32×32×256";
    module.summary = "ConvTranspose2d outputs 32×32×256 decoder features.";
    module.stats = [
      { label: "Output", value: "[256, 32, 32]" },
      { label: "Stride", value: "2 × 2" },
    ];
    module.details = [];
  });

  updateModule("dec_stage2", (module) => {
    module.title = "Decoder stage 2 · U-Net block 32×32×256";
    module.summary = "Double 3×3 Conv+BN blends the 32×32×256 concat.";
    module.image = "media/architecture/unet-block.png";
    module.imageAlt = "U-Net double convolution schematic";
    module.stats = [
      { label: "Output", value: "[256, 32, 32]" },
      { label: "Layers", value: "2 × (Conv2d + BatchNorm2d + ReLU)" },
    ];
    module.details = [];
  });

  updateModule("dec_up3", (module) => {
    module.title = "Decoder upsample 3 · 2×2 TConv 64×64×128";
    module.summary = "ConvTranspose2d lifts to 64×64×128 before shallow skip.";
    module.stats = [
      { label: "Output", value: "[128, 64, 64]" },
      { label: "Stride", value: "2 × 2" },
    ];
    module.details = [];
  });

  updateModule("dec_stage3", (module) => {
    module.title = "Decoder stage 3 · U-Net block 64×64×128";
    module.summary = "Double 3×3 Conv+BN cleans the 64×64×128 concat.";
    module.image = "media/architecture/unet-block.png";
    module.imageAlt = "U-Net double convolution schematic";
    module.stats = [
      { label: "Output", value: "[128, 64, 64]" },
      { label: "Layers", value: "2 × (Conv2d + BatchNorm2d + ReLU)" },
    ];
    module.details = [];
  });

  updateModule("dec_stage4", (module) => {
    module.title = "Decoder stage 4 · U-Net block 128×128×64";
    module.summary = "ConvTranspose2d + double 3×3 conv build 128×128×64 map.";
    module.image = "media/architecture/unet-block.png";
    module.imageAlt = "U-Net double convolution schematic";
    module.stats = [
      { label: "Output", value: "[128, 128]" },
      { label: "Layers", value: "ConvTranspose2d + 2 × (Conv2d + BatchNorm2d + ReLU)" },
    ];
    module.details = [];
  });

  updateModule("dec_stage5", (module) => {
    module.title = "Decoder stage 5 · Prediction head";
    module.summary = "Final transpose conv + 1×1 head emit 256×256 logits.";
    module.stats = [
      { label: "Output", value: "[1, 256, 256]" },
      { label: "Layers", value: "ConvTranspose2d + Conv2d" },
    ];
    module.details = [];
  });

  updateModule("outputs", (module) => {
    module.details = [];
  });

  return modules;
}

const settleNetModuleBlueprint = [
  {
    id: "input_rgb",
    targetIds: ["text1-9-3-3-3-7-2-8-0-3-7-9"],
    title: "RGB stream · Satellite tiles",
    summary: "RGB stream uses 64×3×256×256 tiles.",
    stats: [
      { label: "Tensor", value: "[3, 256, 256]" },
      { label: "Role", value: "Vision backbone input" },
      { label: "Augmentation", value: "RGB only" },
    ],
    details: [],
    margin: 5,
  },
  {
    id: "input_height",
    targetIds: ["text1-9-3-3-3-7-2-8-0-3-7"],
    title: "Building height raster",
    summary: "Height stream uses 64×1×256×256 raster.",
    stats: [
      { label: "Tensor", value: "[1, 256, 256]" },
      { label: "Role", value: "Auxiliary encoder input" },
      { label: "Acquisition", value: "DSM derived" },
    ],
    details: [],
    margin: 5,
  },
  {
    id: "input_count",
    targetIds: ["text1-9-3-3-3-7-2-8-0-3-7-3"],
    title: "Building count density",
    summary: "Density stream uses 64×1×256×256 raster.",
    stats: [
      { label: "Tensor", value: "[1, 256, 256]" },
      { label: "Role", value: "Context encoder input" },
      { label: "Scaling", value: "Min–max normalised" },
    ],
    details: [],
    margin: 5,
  },
  {
    id: "tri_patchify",
    targetIds: ["text1-9-3-3-0"],
    title: "Encoder stems · Patchify projections",
    summary: "Each stream uses Conv2d stride4 → 80 tokens at 64×64.",
    image: "media/architecture/convolution.gif",
    imageAlt: "Animated convolution showing the patchify projection",
    stats: [
      { label: "Output", value: "3 × [80, 64, 64]" },
      { label: "Components", value: "Three stride-4 Conv2d + LayerNorm pairs" },
    ],
    details: [],
  },
  {
    id: "tri_stage0",
    targetIds: ["text1-9-3"],
    title: "Encoder stage 0 · 64×64×80",
    summary: "Each stream runs 2 ConvNeXt blocks at 64×64×80.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "3 × [80, 64, 64]" },
      { label: "Blocks", value: "3 × 2 ConvNeXt blocks" },
    ],
    details: [],
  },
  {
    id: "tri_downsample1",
    targetIds: ["text1-9-3-3-3"],
    title: "Downsampling 1 · 2×2 conv",
    summary: "Each stream uses Conv2d stride2 → 32×32×160.",
    image: "media/architecture/convolution.gif",
    imageAlt: "Animated convolution illustrating stride-2 downsampling",
    stats: [
      { label: "Output", value: "3 × [160, 32, 32]" },
      { label: "Stride", value: "Three 2×2 Conv2d" },
    ],
    details: [],
  },
  {
    id: "tri_stage1",
    targetIds: ["text1-9-3-3"],
    title: "Encoder stage 1 · 32×32×160",
    summary: "Each stream runs 2 ConvNeXt blocks at 32×32×160.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "3 × [160, 32, 32]" },
      { label: "Blocks", value: "3 × 2 ConvNeXt blocks" },
    ],
    details: [],
  },
  {
    id: "tri_downsample2",
    targetIds: ["text1-9-3-3-3-5"],
    title: "Downsampling 2 · 2×2 conv",
    summary: "Each stream uses Conv2d stride2 → 16×16×320.",
    image: "media/architecture/convolution.gif",
    imageAlt: "Animated convolution illustrating stride-2 downsampling",
    stats: [
      { label: "Output", value: "3 × [320, 16, 16]" },
      { label: "Stride", value: "Three 2×2 Conv2d" },
    ],
    details: [],
  },
  {
    id: "tri_stage2",
    targetIds: ["text1-9-3-1"],
    title: "Encoder stage 2 · 16×16×320",
    summary: "Each stream runs 8 ConvNeXt blocks at 16×16×320.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "3 × [320, 16, 16]" },
      { label: "Blocks", value: "3 × 8 ConvNeXt blocks" },
    ],
    details: [],
  },
  {
    id: "fusion_low",
    targetIds: ["path-21-9-4"],
    title: "Fusion block · 64×64 CBAM",
    summary: "CBAM fuses 240 channels (3×80) down to 80 at 64×64.",
    image: "media/architecture/cbam.png",
    imageAlt: "CBAM module with channel and spatial attention",
    stats: [
      { label: "Input", value: "[240, 64, 64]" },
      { label: "Output", value: "[80, 64, 64]" },
      { label: "Mechanism", value: "Channel + spatial attention" },
    ],
    details: [],
    margin: 6,
  },
  {
    id: "fusion_mid",
    targetIds: ["path-111-1-9"],
    title: "Fusion block · 32×32 CBAM",
    summary: "CBAM fuses 480 channels down to 160 at 32×32.",
    image: "media/architecture/cbam.png",
    imageAlt: "CBAM module schematic",
    stats: [
      { label: "Input", value: "[480, 32, 32]" },
      { label: "Output", value: "[160, 32, 32]" },
      { label: "Mechanism", value: "Channel + spatial attention" },
    ],
    details: [],
    margin: 6,
  },
  {
    id: "fusion_high",
    targetIds: ["path-123-0-0"],
    title: "Fusion block · 16×16 CBAM",
    summary: "CBAM fuses 960 channels down to 320 at 16×16.",
    image: "media/architecture/cbam.png",
    imageAlt: "CBAM attention block",
    stats: [
      { label: "Input", value: "[960, 16, 16]" },
      { label: "Output", value: "[320, 16, 16]" },
      { label: "Mechanism", value: "Channel + spatial attention" },
    ],
    details: [],
    margin: 6,
  },
  {
    id: "bottleneck_bridge",
    targetIds: ["text1-9-3-3-3-0"],
    title: "Bottleneck bridge · 2×2 conv",
    summary: "LayerNorm + Conv2d stride2 → 8×8×640 latent grid.",
    image: "media/architecture/convolution.gif",
    imageAlt: "Animated convolution illustrating stride-2 downsampling",
    stats: [
      { label: "Output", value: "[640, 8, 8]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
  },
  {
    id: "decoder_bottleneck",
    targetIds: ["text1-9-3-1-7", "text1-9-3-1-7-9"],
    title: "Decoder bottleneck · ConvNeXt blocks",
    summary: "2 ConvNeXt blocks run on the 8×8×640 latent tensor.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[640, 8, 8]" },
      { label: "Blocks", value: "2 × ConvNeXt" },
    ],
    details: [],
    margin: 3,
  },
  {
    id: "decoder_up1",
    targetIds: ["text1-9-3-3-3-7"],
    title: "Decoder upsample 1 · 3×3 TConv",
    summary: "ConvTranspose2d doubles 8×8 latent to 16×16×320.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[320, 16, 16]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
    margin: 3,
  },
  {
    id: "decoder_stage1",
    targetIds: ["text1-9-3-1-7-7-4-7"],
    title: "Decoder stage 1 · ConvNeXt blocks 16×16×320",
    summary: "2 ConvNeXt blocks on the 16×16×320 fused tensor.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[320, 16, 16]" },
      { label: "Blocks", value: "2 × ConvNeXt" },
    ],
    details: [],
  },
  {
    id: "decoder_up2",
    targetIds: ["text1-9-3-3-3-7-3"],
    title: "Decoder upsample 2 · 3×3 TConv",
    summary: "ConvTranspose2d lifts 16×16×320 to 32×32×160.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[160, 32, 32]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
    margin: 3,
  },
  {
    id: "decoder_stage2",
    targetIds: ["text1-9-3-1-7-7-4"],
    title: "Decoder stage 2 · ConvNeXt blocks 32×32×160",
    summary: "2 ConvNeXt blocks handle the 32×32×160 merge.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[160, 32, 32]" },
      { label: "Blocks", value: "2 × ConvNeXt" },
    ],
    details: [],
  },
  {
    id: "decoder_up3",
    targetIds: ["text1-9-3-3-3-7-2"],
    title: "Decoder upsample 3 · 3×3 TConv",
    summary: "ConvTranspose2d outputs the 64×64×80 decoder map.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[80, 64, 64]" },
      { label: "Stride", value: "2 × 2" },
    ],
    details: [],
    margin: 3,
  },
  {
    id: "decoder_stage3",
    targetIds: ["text1-9-3-1-6"],
    title: "Decoder stage 3 · ConvNeXt blocks 64×64×80",
    summary: "2 ConvNeXt blocks tune the 64×64×80 tensor.",
    image: "media/architecture/convnext-block.png",
    imageAlt: "ConvNeXt block schematic",
    stats: [
      { label: "Output", value: "[80, 64, 64]" },
      { label: "Blocks", value: "2 × ConvNeXt" },
    ],
    details: [],
  },
  {
    id: "decoder_stage4",
    targetIds: ["text1-9-3-3-3-7-2-8", "text1-9-3-1-7-7-4-3-2-7"],
    title: "Decoder stage 4 · Upsample 128×128×40",
    summary: "Transpose conv + smoothing build the 128×128×40 map.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[40, 128, 128]" },
      { label: "Layers", value: "ConvTranspose2d + Conv2d + LayerNorm" },
    ],
    details: [],
  },
  {
    id: "decoder_stage5",
    targetIds: ["text1-9-3-3-3-7-2-8-0"],
    title: "Decoder stage 5 · Prediction head",
    summary: "Final transpose conv returns 256×256 before 1×1 head.",
    image: "media/architecture/transposed_convolution.gif",
    imageAlt: "Animated transpose convolution illustrating learned upsampling",
    stats: [
      { label: "Output", value: "[1, 256, 256]" },
      { label: "Layers", value: "ConvTranspose2d + Conv2d" },
    ],
    details: [],
  },
  {
    id: "skip_routing",
    targetIds: ["text1-9-3-1-6-1-4", "text1-9-3-1-6-1-4-8", "text1-9-3-1-6-1-4-80"],
    title: "Skip routing · CBAM-conditioned",
    summary: "CBAM skips feed the decoder at 64×64, 32×32, and 16×16.",
    stats: [
      { label: "Scales", value: "64×64 · 32×32 · 16×16" },
      { label: "Channels", value: "80 / 160 / 320" },
      { label: "Fusion", value: "Concatenate + 1×1 projection" },
    ],
    details: [],
    margin: 4,
  },
  {
    id: "outputs",
    targetIds: ["text1-9-3-3-3-7-2-8-0-3"],
    title: "Outputs · Settlement mask",
    summary: "Logits keep 256×256 alignment for settlement mask.",
    stats: [
      { label: "Tensor", value: "[1, 256, 256]" },
      { label: "Activation", value: "Apply sigmoid downstream" },
      { label: "Task", value: "Binary segmentation" },
    ],
    details: [],
    margin: 3,
  },
];

function buildSettleNetModules() {
  return cloneModules(settleNetModuleBlueprint);
}

export const MODEL_REGISTRY = {
  convnext: {
    id: "convnext",
    label: "ConvNeXt encoder-decoder",
    svgPath: "media/architecture/architecture-convnext-single-proper.svg",
    panelTitle: "ConvNeXt U-Net Explorer",
    ariaLabel: "ConvNeXt decoder architecture diagram",
    buildModules: buildConvNeXtModules,
    scale: DEFAULT_SCALE,
  },
  "convnext-unet": {
    id: "convnext-unet",
    label: "ConvNeXt + U-Net decoder",
    svgPath: "media/architecture/architecture-convnext-unet.svg",
    panelTitle: "ConvNeXt · U-Net Decoder Explorer",
    ariaLabel: "ConvNeXt U-Net decoder architecture diagram",
    buildModules: buildConvNeXtUNetModules,
    scale: DEFAULT_SCALE,
  },
  settlenet: {
    id: "settlenet",
    label: "SettleNet triple encoder",
    svgPath: "media/architecture/architecture-convnext.svg",
    panelTitle: "SettleNet Triple Encoder Explorer",
    ariaLabel: "SettleNet architecture diagram",
    buildModules: buildSettleNetModules,
    scale: {
      base: 0.525,
      medium: 0.45,
      small: 0.375,
    },
  },
};

export { DEFAULT_SCALE };