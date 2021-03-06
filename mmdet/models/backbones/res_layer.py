import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import applications
from tensorflow.python.keras.engine.input_layer import Input
from tensorflow.python.keras.engine.sequential import Sequential
from tensorflow.python.keras.layers.convolutional import Conv2D
from tensorflow.python.ops.gen_array_ops import expand_dims
from ..common.conv import build_conv_layer
from ..common.norm import build_norm_layer
from ..common.mix_layers import SequentialLayer
class ResLayer(tf.keras.Sequential):
    """ResLayer to build ResNet style backbone.
    Args:
        block (nn.Module): block used to build ResLayer.
        inplanes (int): inplanes of block.
        planes (int): planes of block.
        num_blocks (int): number of blocks.
        stride (int): stride of the first block. Default: 1
        avg_down (bool): Use AvgPool instead of stride conv when
            downsampling in the bottleneck. Default: False
        conv_cfg (dict): dictionary to construct and config conv layer.
            Default: None
        norm_cfg (dict): dictionary to construct and config norm layer.
            Default: dict(type='BN')
        downsample_first (bool): Downsample at the first block or last block.
            False for Hourglass, True for ResNet. Default: True
    """

    def __init__(self,
                 block,
                 inplanes,
                 planes,
                 num_blocks,
                 stride=1,
                 avg_down=False,
                 conv_cfg=None,
                 norm_cfg=dict(type='BN'),
                 downsample_first=True,
                 **kwargs):
        self.block = block
        downsample = None
        if stride != 1 or inplanes != planes * block.expansion:
            downsample = []
            conv_stride = stride
            if avg_down:
                conv_stride = 1
                downsample.append(
                    keras.layers.AveragePooling2D(pool_size=(stride, stride), stride=stride)
                )
            downsample.extend([
                [
                    tf.keras.layers.Conv2D(planes*block.expansion, 1, strides=conv_stride,use_bias=False),
                    tf.keras.layers.BatchNormalization()
                ]
                
            ]
            )
            downsample =tf.keras.Sequential(*downsample)

        layers = []
        if downsample_first:
            layers.append(
                block(
                    inplanes=inplanes,
                    planes=planes,
                    stride=stride,
                    downsample=downsample,
                    conv_cfg=conv_cfg,
                    norm_cfg=norm_cfg,
                    **kwargs))
            inplanes = planes * block.expansion
            for _ in range(1, num_blocks):
                layers.append(
                    block(
                        inplanes=inplanes,
                        planes=planes,
                        stride=1,
                        conv_cfg=conv_cfg,
                        norm_cfg=norm_cfg,
                        **kwargs))

        else:  # downsample_first=False is for HourglassModule
            for _ in range(num_blocks - 1):
                layers.append(
                    block(
                        inplanes=inplanes,
                        planes=inplanes,
                        stride=1,
                        conv_cfg=conv_cfg,
                        norm_cfg=norm_cfg,
                        **kwargs))
            layers.append(
                block(
                    inplanes=inplanes,
                    planes=planes,
                    stride=stride,
                    downsample=downsample,
                    conv_cfg=conv_cfg,
                    norm_cfg=norm_cfg,
                    **kwargs))
        super(ResLayer, self).__init__(layers)

    def call_function(self, inputs):
        for i in self._layers:inputs = i(inputs)
        return inputs
class SimplifiedBasicBlock(tf.keras.layers.Layer):
    """Simplified version of original basic residual block. This is used in
    `SCNet <https://arxiv.org/abs/2012.10150>`_.
    - Norm layer is now optional
    - Last ReLU in forward function is removed
    """
    expansion = 1

    def __init__(self,
                 inplanes,
                 planes,
                 stride=1,
                 dilation=1,
                 downsample=None,
                 style='pytorch',
                 with_cp=False,
                 conv_cfg=None,
                 norm_cfg=dict(type='BN'),
                 dcn=None,
                 plugins=None,
                 init_fg=None):
        super(SimplifiedBasicBlock, self).__init__()
        assert dcn is None, 'Not implemented yet.'
        assert plugins is None, 'Not implemented yet.'
        assert not with_cp, 'Not implemented yet.'
        self.with_norm = norm_cfg is not None
        with_bias = True if norm_cfg is None else False
        self.conv1 = build_conv_layer(
            conv_cfg,
            planes,
            3,
            stride=stride,
            padding=dilation,
            dilation=dilation,
            bias=with_bias)
        if self.with_norm:
            self.norm1_name, norm1 = build_norm_layer(
                norm_cfg, planes, postfix=1)
            super(SimplifiedBasicBlock,self).__setattr__(self.norm1_name, norm1)
            

        self.conv2 = build_conv_layer(
            conv_cfg, planes, 3, padding=1, bias=with_bias)
        if self.with_norm:
            self.norm2_name, norm2 = build_norm_layer(
                norm_cfg, planes, postfix=2)
            super(SimplifiedBasicBlock,self).__setattr__(self.norm2_name, norm2)
            

        self.relu =tf.keras.layers.ReLU()
        self.downsample = downsample
        self.stride = stride
        self.dilation = dilation
        self.with_cp = with_cp

    @property
    def norm1(self):
        """nn.Module: normalization layer after the first convolution layer"""
        return getattr(self, self.norm1_name) if self.with_norm else None

    @property
    def norm2(self):
        """nn.Module: normalization layer after the second convolution layer"""
        return getattr(self, self.norm2_name) if self.with_norm else None
    
    def call_funtion(self, x):

        identity = x
        if hasattr(self.conv1,'not_base') and self.conv1.not_base:
            out = self.conv1.call_funtion(x)
        else:
            out = self.conv1(x)
        if self.with_norm:
            if hasattr(self.norm1,'not_base') and self.norm1.not_base:
                out = self.norm1.call_funtion(out)
            else:
                out = self.norm1(out)

        out = self.relu(out)

        if hasattr(self.conv2,'not_base') and self.conv2.not_base:
            out = self.conv2.call_funtion(out)
        else:
            out = self.conv2(x)
        if self.with_norm:
            if hasattr(self.norm2,'not_base') and self.norm2.not_base:
                out = self.norm2.call_funtion(out)
            else:
                out = self.norm2(out)

        if self.downsample is not None:
            if hasattr(self.downsample,'not_base') and self.downsample.not_base:
                identity = self.downsample.call_funtion(x)
            else:
                identity = self.downsample(x)

        out = out +  identity

        return out

    def call(self, x,training=False):
        """Forward function."""

        identity = x

        out = self.conv1(x,training=training)
        if self.with_norm:
            out = self.norm1(out,training=training)
        out = self.relu(out,training=training)

        out = self.conv2(out,training=training)
        if self.with_norm:
            out = self.norm2(out,training=training)

        if self.downsample is not None:
            identity = self.downsample(x,training=training)

        out = out +  identity

        return out