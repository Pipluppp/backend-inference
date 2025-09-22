# app/models/architectures.py

import torch
import torch.nn as nn
from app.utils.config import Config
from app.models.components import LayerNorm, ConvNeXtBlock, FusionBlock


class ConvNeXtEncoder(nn.Module):
    """A standalone ConvNeXt encoder that returns features from each stage."""

    def __init__(self, config: Config, in_chans: int):
        super().__init__()
        self.dims = config.ENCODER_CHANNEL_LIST
        self.depths = config.ENCODER_BLOCKS_PER_STAGE

        total_blocks = sum(self.depths)
        dp_rates = [
            x.item()
            for x in torch.linspace(0, config.ENCODER_DROP_PATH_RATE, total_blocks)
        ]

        self.stem = nn.Sequential(
            nn.Conv2d(in_chans, self.dims[0], kernel_size=4, stride=4),
            LayerNorm(self.dims[0], eps=1e-6, data_format="channels_first"),
        )

        self.stages = nn.ModuleList()
        self.downsamplers = nn.ModuleList()

        cursor = 0
        for i in range(4):
            if i > 0:
                downsampler = nn.Sequential(
                    LayerNorm(self.dims[i - 1], eps=1e-6, data_format="channels_first"),
                    nn.Conv2d(self.dims[i - 1], self.dims[i], kernel_size=2, stride=2),
                )
                self.downsamplers.append(downsampler)

            stage_dp_rates = dp_rates[cursor : cursor + self.depths[i]]
            stage = nn.Sequential(
                *[
                    ConvNeXtBlock(
                        self.dims[i],
                        stage_dp_rates[j],
                        config.ENCODER_LAYER_SCALE_INIT_VALUE,
                    )
                    for j in range(self.depths[i])
                ]
            )
            self.stages.append(stage)
            cursor += self.depths[i]

        self.output_channels = self.dims

    def forward(self, x):
        features = {}
        x = self.stem(x)
        x = self.stages[0](x)
        features["s1"] = x

        x = self.downsamplers[0](x)
        x = self.stages[1](x)
        features["s2"] = x

        x = self.downsamplers[1](x)
        x = self.stages[2](x)
        features["s3"] = x

        x = self.downsamplers[2](x)
        x = self.stages[3](x)
        features["s4"] = x

        return features


class ConvNeXtDecoder(nn.Module):
    def __init__(self, config: Config, encoder_channels: list[int]):
        super().__init__()
        s1_ch, s2_ch, s3_ch, s4_ch = encoder_channels

        self.bottleneck = nn.Sequential(
            *[
                ConvNeXtBlock(
                    s4_ch,
                    config.ENCODER_DROP_PATH_RATE,
                    config.ENCODER_LAYER_SCALE_INIT_VALUE,
                )
                for _ in range(config.DECODER_CONVNEXT_BLOCKS[0])
            ]
        )

        self.up1 = nn.ConvTranspose2d(s4_ch, s3_ch, kernel_size=2, stride=2)
        self.dec_block1 = nn.Sequential(
            nn.Conv2d(s3_ch * 2, s3_ch, kernel_size=1),
            *[
                ConvNeXtBlock(
                    s3_ch,
                    config.ENCODER_DROP_PATH_RATE,
                    config.ENCODER_LAYER_SCALE_INIT_VALUE,
                )
                for _ in range(config.DECODER_CONVNEXT_BLOCKS[1])
            ]
        )

        self.up2 = nn.ConvTranspose2d(s3_ch, s2_ch, kernel_size=2, stride=2)
        self.dec_block2 = nn.Sequential(
            nn.Conv2d(s2_ch * 2, s2_ch, kernel_size=1),
            *[
                ConvNeXtBlock(
                    s2_ch,
                    config.ENCODER_DROP_PATH_RATE,
                    config.ENCODER_LAYER_SCALE_INIT_VALUE,
                )
                for _ in range(config.DECODER_CONVNEXT_BLOCKS[2])
            ]
        )

        self.up3 = nn.ConvTranspose2d(s2_ch, s1_ch, kernel_size=2, stride=2)
        self.dec_block3 = nn.Sequential(
            nn.Conv2d(s1_ch * 2, s1_ch, kernel_size=1),
            *[
                ConvNeXtBlock(
                    s1_ch,
                    config.ENCODER_DROP_PATH_RATE,
                    config.ENCODER_LAYER_SCALE_INIT_VALUE,
                )
                for _ in range(config.DECODER_CONVNEXT_BLOCKS[3])
            ]
        )

        final_ch1, final_ch2 = (
            config.FINAL_UPSAMPLING_CHANNELS[1],
            config.FINAL_UPSAMPLING_CHANNELS[2],
        )
        self.final_up1 = nn.ConvTranspose2d(s1_ch, final_ch1, kernel_size=2, stride=2)
        self.final_conv1 = nn.Sequential(
            nn.Conv2d(final_ch1, final_ch1, 3, 1, 1),
            LayerNorm(final_ch1, data_format="channels_first"),
            nn.GELU(),
        )
        self.final_up2 = nn.ConvTranspose2d(
            final_ch1, final_ch2, kernel_size=2, stride=2
        )
        self.final_conv_out = nn.Conv2d(final_ch2, 1, kernel_size=1)

    def forward(self, features: dict):
        s1, s2, s3, s4 = features["s1"], features["s2"], features["s3"], features["s4"]
        x = self.bottleneck(s4)
        x = self.up1(x)
        x = torch.cat([x, s3], dim=1)
        x = self.dec_block1(x)
        x = self.up2(x)
        x = torch.cat([x, s2], dim=1)
        x = self.dec_block2(x)
        x = self.up3(x)
        x = torch.cat([x, s1], dim=1)
        x = self.dec_block3(x)
        x = self.final_up1(x)
        x = self.final_conv1(x)
        x = self.final_up2(x)
        return self.final_conv_out(x)


class ConvNeXtUNet(nn.Module):
    def __init__(self, config: Config):
        super().__init__()
        self.encoder = ConvNeXtEncoder(config, in_chans=config.INPUT_CHANNELS)
        self.decoder = ConvNeXtDecoder(
            config, encoder_channels=self.encoder.output_channels
        )
        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, (nn.Conv2d, nn.Linear)):
            nn.init.trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        features = self.encoder(x)
        return self.decoder(features)


# Add SettleNet and its specific 3-stage encoder here if you plan to test it
# For brevity, this example focuses on ConvNeXtUNet.
