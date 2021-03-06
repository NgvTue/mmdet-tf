from re import I
import warnings

import tensorflow as tf
from tensorflow import keras
from tensorflow.python import tf2
from tensorflow.python.keras.applications import resnet
from tensorflow.python.keras.engine.input_layer import Input
from tensorflow.python.ops.gen_array_ops import diag, shape
from tensorflow_addons import layers
from ..builder import BACKBONES
from .res_layer import ResLayer
from tensorflow.keras import applications
class BasicBlock(tf.keras.layers.Layer):
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
                 init_cfg=None):
        super(BasicBlock, self).__init__()
        assert dcn is None, 'Not implemented yet.'
        assert plugins is None, 'Not implemented yet.'

        self.convs1 = tf.keras.Sequential(
            [
            tf.keras.Input(shape=(None,None,inplanes)),
            tf.keras.layers.Conv2D(planes,3, strides=stride, padding='same', dilation_rate =dilation,use_bias=False  ),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.ReLU(),
            ]
        )
        self.convs2 = tf.keras.Sequential(
            [
            tf.keras.Input(shape=(None,None,planes)),
            tf.keras.layers.Conv2D(planes,3, strides=stride, padding='same', dilation_rate=dilation,use_bias=False  ),
            tf.keras.layers.BatchNormalization(),]
        )
        self.relu = tf.keras.layers.ReLU()
        self.downsample = downsample
        self.stride = stride
        self.dilation = dilation
        self.with_cp = with_cp
    def call(self, x,training=False):
        """Forward function."""

        def _inner_forward(x,training=False):
            identity = x

            out =self.convs1(x,training=training)
            # out = self.conv1(x,training=training)
            # out = self.norm1(out,training=training)
            # out = self.relu(out,training=training)
            out =self.convs2(out,training=training)
            # out = self.conv2(out,training=training)
            # out = self.norm2(out,training=training)

            if self.downsample is not None:
                identity = self.downsample(x,training=training)

            out = out +  identity
            return out
        out = _inner_forward(x,training=training)
        out = self.relu(out,training=training)
        return out

    def call_function(self, inputs):
        def _inner_forward(x):
            identity = x

            out =self.convs1(x)
            # out = self.conv1(x,training=training)
            # out = self.norm1(out,training=training)
            # out = self.relu(out,training=training)
            out =self.convs2(out)
            # out = self.conv2(out,training=training)
            # out = self.norm2(out,training=training)

            if self.downsample is not None:
                identity = self.downsample(x)

            out = out +  identity
            return out
        out = _inner_forward(inputs)
        out = self.relu(out)
        return out



class Bottleneck(tf.keras.layers.Layer):
    expansion = 4

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
                 init_cfg=None):
        """Bottleneck block for ResNet.
        If style is "pytorch", the stride-two layer is the 3x3 conv layer, if
        it is "caffe", the stride-two layer is the first 1x1 conv layer.
        """
        super(Bottleneck, self).__init__()
        assert style in ['pytorch', 'caffe']
        assert dcn is None or isinstance(dcn, dict)
        assert plugins is None or isinstance(plugins, list)
        if plugins is not None:
            allowed_position = ['after_conv1', 'after_conv2', 'after_conv3']
            assert all(p['position'] in allowed_position for p in plugins)
        self.not_base = True
        self.inplanes = inplanes
        self.planes = planes
        self.stride = stride
        self.dilation = dilation
        self.style = style
        self.with_cp = with_cp
        self.conv_cfg = conv_cfg
        self.norm_cfg = norm_cfg
        self.dcn = dcn
        self.with_dcn = dcn is not None
        self.plugins = plugins
        self.with_plugins = plugins is not None

        if self.with_plugins:
            # collect plugins for conv1/conv2/conv3
            self.after_conv1_plugins = [
                plugin['cfg'] for plugin in plugins
                if plugin['position'] == 'after_conv1'
            ]
            self.after_conv2_plugins = [
                plugin['cfg'] for plugin in plugins
                if plugin['position'] == 'after_conv2'
            ]
            self.after_conv3_plugins = [
                plugin['cfg'] for plugin in plugins
                if plugin['position'] == 'after_conv3'
            ]

        if self.style == 'pytorch':
            self.conv1_stride = 1
            self.conv2_stride = stride
        else:
            self.conv1_stride = stride
            self.conv2_stride = 1

        # self.norm1_name, norm1 = build_norm_layer(norm_cfg, planes, postfix=1)
        # self.norm2_name, norm2 = build_norm_layer(norm_cfg, planes, postfix=2)
        # self.norm3_name, norm3 = build_norm_layer(
            # norm_cfg, planes * self.expansion, postfix=3)
        self.conv1 = tf.keras.Sequential(
            [
            tf.keras.layers.Input(shape=(None,None,inplanes)),
            tf.keras.layers.Conv2D(planes,1,strides=self.conv1_stride,use_bias=False,padding='valid'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.ReLU()]
        )
        self.conv2 = tf.keras.Sequential(
            [
            tf.keras.layers.Input(shape=(None,None,planes)),
            tf.keras.layers.Conv2D(planes,3,strides=self.conv2_stride,padding='same', dilation_rate=dilation,use_bias=False),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.ReLU()
            ]
        )
        self.conv3 = tf.keras.Sequential(
            [
            tf.keras.layers.Input(shape=(None,None,planes)),
            tf.keras.layers.Conv2D(planes * self.expansion, 1, use_bias=False),
            tf.keras.layers.BatchNormalization(),
            ]
            # tf.keras.layers.ReLU()
        )
 
       
    
        self.relu = tf.keras.layers.ReLU()
        self.downsample = downsample
 

    def make_block_plugins(self, in_channels, plugins):
        """make plugins for block.
        Args:
            in_channels (int): Input channels of plugin.
            plugins (list[dict]): List of plugins cfg to build.
        Returns:
            list[str]: List of the names of plugin.
        """
        assert isinstance(plugins, list)
        plugin_names = []
        raise Exception("not implement plugin")
        for plugin in plugins:
            plugin = plugin.copy()
            name, layer = build_plugin_layer(
                plugin,
                in_channels=in_channels,
                postfix=plugin.pop('postfix', ''))
            assert not hasattr(self, name), f'duplicate plugin {name}'
            self.add_module(name, layer)
            plugin_names.append(name)
        return plugin_names

    def forward_plugin(self, x, plugin_names):
        raise Exception("forward_plugin not implement")
        out = x
        for name in plugin_names:
            out = getattr(self, name)(x)
        return out




    def call(self, x,training=False):
        """Forward function."""

        def _inner_forward(x,training=False):
            identity = x
            out  = self.conv1(x, training=training)
            out = self.conv2(out, training=training)

            out = self.conv3(out, training=training)

            if self.downsample is not None:
                identity = self.downsample(x,training=training)

            out = out + identity

            return out

        # if self.with_cp and x.requires_grad:
            # out = cp.checkpoint(_inner_forward, x)
        # else:
        out = _inner_forward(x,training=training)

        out = self.relu(out,training=training)

        return out
    def call_function(self, x):
        """Forward function."""

        def _inner_forward(x):
            identity = x
            out  = self.conv1(x)
            out = self.conv2(out)

            out = self.conv3(out)

            if self.downsample is not None:
                identity = self.downsample(x)

            out = out + identity

            return out

        # if self.with_cp and x.requires_grad:
            # out = cp.checkpoint(_inner_forward, x)
        # else:
        out = _inner_forward(x)

        out = self.relu(out)

        return out


@BACKBONES.register_module()
class ResNet(tf.keras.layers.Layer):
    """ResNet backbone.
    Args:
        depth (int): Depth of resnet, from {18, 34, 50, 101, 152}.
        stem_channels (int | None): Number of stem channels. If not specified,
            it will be the same as `base_channels`. Default: None.
        base_channels (int): Number of base channels of res layer. Default: 64.
        in_channels (int): Number of input image channels. Default: 3.
        num_stages (int): Resnet stages. Default: 4.
        strides (Sequence[int]): Strides of the first block of each stage.
        dilations (Sequence[int]): Dilation of each stage.
        out_indices (Sequence[int]): Output from which stages.
        style (str): `pytorch` or `caffe`. If set to "pytorch", the stride-two
            layer is the 3x3 conv layer, otherwise the stride-two layer is
            the first 1x1 conv layer.
        deep_stem (bool): Replace 7x7 conv in input stem with 3 3x3 conv
        avg_down (bool): Use AvgPool instead of stride conv when
            downsampling in the bottleneck.
        frozen_stages (int): Stages to be frozen (stop grad and set eval mode).
            -1 means not freezing any parameters.
        norm_cfg (dict): Dictionary to construct and config norm layer.
        norm_eval (bool): Whether to set norm layers to eval mode, namely,
            freeze running stats (mean and var). Note: Effect on Batch Norm
            and its variants only.
        plugins (list[dict]): List of plugins for stages, each dict contains:
            - cfg (dict, required): Cfg dict to build plugin.
            - position (str, required): Position inside block to insert
              plugin, options are 'after_conv1', 'after_conv2', 'after_conv3'.
            - stages (tuple[bool], optional): Stages to apply plugin, length
              should be same as 'num_stages'.
        with_cp (bool): Use checkpoint or not. Using checkpoint will save some
            memory while slowing down the training speed.
        zero_init_residual (bool): Whether to use zero init for last norm layer
            in resblocks to let them behave as identity.
        pretrained (str, optional): model pretrained path. Default: None
        init_cfg (dict or list[dict], optional): Initialization config dict.
            Default: None
    Example:
        >>> from mmdet.models import ResNet
        >>> import torch
        >>> self = ResNet(depth=18)
        >>> self.eval()
        >>> inputs = torch.rand(1, 3, 32, 32)
        >>> level_outputs = self.forward(inputs)
        >>> for level_out in level_outputs:
        ...     print(tuple(level_out.shape))
        (1, 64, 8, 8)
        (1, 128, 4, 4)
        (1, 256, 2, 2)
        (1, 512, 1, 1)
    """

    arch_settings = {
        18: (BasicBlock, (2, 2, 2, 2)),
        34: (BasicBlock, (3, 4, 6, 3)),
        50: (Bottleneck, (3, 4, 6, 3)),
        101: (Bottleneck, (3, 4, 23, 3)),
        152: (Bottleneck, (3, 8, 36, 3))
    }

    def __init__(self,
                 depth,
                 in_channels=3,
                 stem_channels=None,
                 base_channels=64,
                 num_stages=4,
                 strides=(1, 2, 2, 2),
                 dilations=(1, 1, 1, 1),
                 out_indices=(0, 1, 2, 3),
                 style='pytorch',
                 deep_stem=False,
                 avg_down=False,
                 frozen_stages=-1,
                 conv_cfg=None,
                 norm_cfg=dict(type='BN', requires_grad=True),
                 norm_eval=True,
                 dcn=None,
                 stage_with_dcn=(False, False, False, False),
                 plugins=None,
                 with_cp=False,
                 zero_init_residual=True,
                 pretrained=None,
                 init_cfg=None):
        super(ResNet, self).__init__()
        self.zero_init_residual = zero_init_residual
        if depth not in self.arch_settings:
            raise KeyError(f'invalid depth {depth} for resnet')

        block_init_cfg = None
        assert not (init_cfg and pretrained), \
            'init_cfg and pretrained cannot be setting at the same time'
        if isinstance(pretrained, str):
            warnings.warn('DeprecationWarning: pretrained is deprecated, '
                          'please use "init_cfg" instead')
            self.init_cfg = dict(type='Pretrained', checkpoint=pretrained)
        elif pretrained is None:
            if init_cfg is None:
                self.init_cfg = [
                    dict(type='Kaiming', layer='Conv2d'),
                    dict(
                        type='Constant',
                        val=1,
                        layer=['_BatchNorm', 'GroupNorm'])
                ]
                block = self.arch_settings[depth][0]
                if self.zero_init_residual:
                    if block is BasicBlock:
                        block_init_cfg = dict(
                            type='Constant',
                            val=0,
                            override=dict(name='norm2'))
                    elif block is Bottleneck:
                        block_init_cfg = dict(
                            type='Constant',
                            val=0,
                            override=dict(name='norm3'))
        else:
            raise TypeError('pretrained must be a str or None')

        self.depth = depth
        if stem_channels is None:
            stem_channels = base_channels
        self.stem_channels = stem_channels
        self.base_channels = base_channels
        self.num_stages = num_stages
        assert num_stages >= 1 and num_stages <= 4
        self.strides = strides
        self.dilations = dilations
        assert len(strides) == len(dilations) == num_stages
        self.out_indices = out_indices
        assert max(out_indices) < num_stages
        self.style = style
        self.deep_stem = deep_stem
        self.avg_down = avg_down
        self.frozen_stages = frozen_stages
        self.conv_cfg = conv_cfg
        self.norm_cfg = norm_cfg
        self.with_cp = with_cp
        self.norm_eval = norm_eval
        self.dcn = dcn
        self.stage_with_dcn = stage_with_dcn
        if dcn is not None:
            assert len(stage_with_dcn) == num_stages
        self.plugins = plugins
        self.block, stage_blocks = self.arch_settings[depth]
        self.stage_blocks = stage_blocks[:num_stages]
        self.inplanes = stem_channels

        self._make_stem_layer(in_channels, stem_channels)

        self.res_layers = []
        for i, num_blocks in enumerate(self.stage_blocks):
            stride = strides[i]
            dilation = dilations[i]
            dcn = self.dcn if self.stage_with_dcn[i] else None
            if plugins is not None:
                stage_plugins = self.make_stage_plugins(plugins, i)
            else:
                stage_plugins = None
            
            planes = base_channels * 2**i
            
            res_layer = self.make_res_layer(
                block=self.block,
                inplanes=self.inplanes,
                planes=planes,
                num_blocks=num_blocks,
                stride=stride,
                dilation=dilation,
                style=self.style,
                avg_down=self.avg_down,
                with_cp=with_cp,
                conv_cfg=conv_cfg,
                norm_cfg=norm_cfg,
                dcn=dcn,
                plugins=stage_plugins,
                init_cfg=block_init_cfg)
            self.inplanes = planes * self.block.expansion
            layer_name = f'layer{i + 1}'
            super(ResNet,self).__setattr__(layer_name, res_layer)
            # self.add_module(layer_name, res_layer)
            self.res_layers.append(layer_name)

        self._freeze_stages()

        self.feat_dim = self.block.expansion * base_channels * 2**(
            len(self.stage_blocks) - 1)

    def make_stage_plugins(self, plugins, stage_idx):
        """Make plugins for ResNet ``stage_idx`` th stage.
        Currently we support to insert ``context_block``,
        ``empirical_attention_block``, ``nonlocal_block`` into the backbone
        like ResNet/ResNeXt. They could be inserted after conv1/conv2/conv3 of
        Bottleneck.
        An example of plugins format could be:
        Examples:
            >>> plugins=[
            ...     dict(cfg=dict(type='xxx', arg1='xxx'),
            ...          stages=(False, True, True, True),
            ...          position='after_conv2'),
            ...     dict(cfg=dict(type='yyy'),
            ...          stages=(True, True, True, True),
            ...          position='after_conv3'),
            ...     dict(cfg=dict(type='zzz', postfix='1'),
            ...          stages=(True, True, True, True),
            ...          position='after_conv3'),
            ...     dict(cfg=dict(type='zzz', postfix='2'),
            ...          stages=(True, True, True, True),
            ...          position='after_conv3')
            ... ]
            >>> self = ResNet(depth=18)
            >>> stage_plugins = self.make_stage_plugins(plugins, 0)
            >>> assert len(stage_plugins) == 3
        Suppose ``stage_idx=0``, the structure of blocks in the stage would be:
        .. code-block:: none
            conv1-> conv2->conv3->yyy->zzz1->zzz2
        Suppose 'stage_idx=1', the structure of blocks in the stage would be:
        .. code-block:: none
            conv1-> conv2->xxx->conv3->yyy->zzz1->zzz2
        If stages is missing, the plugin would be applied to all stages.
        Args:
            plugins (list[dict]): List of plugins cfg to build. The postfix is
                required if multiple same type plugins are inserted.
            stage_idx (int): Index of stage to build
        Returns:
            list[dict]: Plugins for current stage
        """
        stage_plugins = []
        for plugin in plugins:
            plugin = plugin.copy()
            stages = plugin.pop('stages', None)
            assert stages is None or len(stages) == self.num_stages
            # whether to insert plugin into current stage
            if stages is None or stages[stage_idx]:
                stage_plugins.append(plugin)

        return stage_plugins

    def make_res_layer(self, **kwargs):
        """Pack all blocks in a stage into a ``ResLayer``."""
        return ResLayer(**kwargs)


    def _make_stem_layer(self, in_channels, stem_channels):
        if self.deep_stem:
            self.stem = tf.keras.Sequential(
                [
                    tf.keras.layers.Input(shape=(None,None,in_channels)),
                    tf.keras.layers.Conv2D(stem_channels // 2, 3, strides=2, padding='same',use_bias=False),
                    tf.keras.layers.BatchNormalization(),
                    tf.keras.layers.ReLU(),

                    tf.keras.layers.Conv2D(stem_channels, 3, strides=1,padding='same', use_bias=False),
                    tf.keras.layers.BatchNormalization(),
                    tf.keras.layers.ReLU(),
                ]

            )
        else:
            self.conv1 = tf.keras.layers.Conv2D(stem_channels, 7, strides=2, padding='same',use_bias=False)
            self.norm1 = tf.keras.layers.BatchNormalization()
            self.relu = tf.keras.layers.ReLU()
           
        self.maxpool = tf.keras.layers.MaxPool2D(pool_size=3, strides=2,padding='SAME')
        #self.maxpool.add(tf.keras.layers.ZeroPadding2D(padding=(1,1)))
       # self.maxpool.add(tf.keras.layers.MaxPool2D(pool_size=3, strides=2)) #nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        
    def _freeze_stages(self):
        tf.print("implement freeze_stage")
    
    @staticmethod
    def make_funtion_model( depth,
                 in_channels=3,
                 stem_channels=None,
                 base_channels=64,
                 num_stages=4,
                 strides=(1, 2, 2, 2),
                 dilations=(1, 1, 1, 1),
                 out_indices=(0, 1, 2, 3),
                 style='pytorch',
                 deep_stem=False,
                 avg_down=False,
                 frozen_stages=-1,
                 conv_cfg=None,
                 norm_cfg=dict(type='BN', requires_grad=True),
                 norm_eval=True,
                 dcn=None,
                 stage_with_dcn=(False, False, False, False),
                 plugins=None,
                 with_cp=False,
                 zero_init_residual=True,
                 pretrained=None,
                 init_cfg=None):

        instance = ResNet(
                 depth,
                 in_channels=in_channels,
                 stem_channels=stem_channels,
                 base_channels=base_channels,
                 num_stages=num_stages,
                 strides=strides,
                 dilations=dilations,
                 out_indices=out_indices,
                 style=style,
                 deep_stem=deep_stem,
                 avg_down=avg_down,
                 frozen_stages=frozen_stages,
                 conv_cfg=conv_cfg,
                 norm_cfg=norm_cfg,
                 norm_eval=norm_eval,
                 dcn=dcn,
                 stage_with_dcn=stage_with_dcn,
                 plugins=plugins,
                 with_cp=with_cp,
                 zero_init_residual=zero_init_residual,
                 pretrained=pretrained,
                 init_cfg=init_cfg)

        inputs = tf.keras.layers.Input(shape=(None,None,in_channels))
        outputs = instance.call_function(inputs)
        return tf.keras.Model(inputs=inputs,outputs=outputs)


    def call_function(self, x):
        if self.deep_stem:
            
            x=self.stem(x)
        else:
            x = self.conv1(x)
            x = self.norm1(x)
            x = self.relu(x)
        x = self.maxpool(x)
        outs = []
        for i, layer_name in enumerate(self.res_layers):
            res_layer = getattr(self, layer_name)
            x = res_layer.call_function(x)
            if i in self.out_indices:
                outs.append(x)
        return tuple(outs)

        
    @tf.function(experimental_relax_shapes=True)
    def call(self, x,training=False):
        """Forward function."""

        if self.deep_stem:
            x = self.stem(x,training=training)
        else:
            x = self.conv1(x,training=training)
            x = self.norm1(x,training=training)
            x = self.relu(x,training=training)
        x = self.maxpool(x)
        outs = []
        for i, layer_name in enumerate(self.res_layers):
            res_layer = getattr(self, layer_name)
            x = res_layer(x,training=training)
            if i in self.out_indices:
                outs.append(x)
        return tuple(outs)

    def m_train(self, mode=True):
        """Convert the model into training mode while keep normalization layer
        freezed."""
        # super(ResNet, self).train(mode)
        self._freeze_stages()
        if mode and self.norm_eval:
            tf.print("implement at m_train line 638 resne.py")


@BACKBONES.register_module()
class ResNetV1d(ResNet):
    r"""ResNetV1d variant described in `Bag of Tricks
    <https://arxiv.org/pdf/1812.01187.pdf>`_.
    Compared with default ResNet(ResNetV1b), ResNetV1d replaces the 7x7 conv in
    the input stem with three 3x3 convs. And in the downsampling block, a 2x2
    avg_pool with stride 2 is added before conv, whose stride is changed to 1.
    """
    def __init__(self, **kwargs):
        super(ResNetV1d, self).__init__(
            deep_stem=True, avg_down=True, **kwargs)
        

@BACKBONES.register_module()
class ResNet50V1(tf.keras.Model):
    def __init__(self,**kwargs):
        base = tf.keras.applications.resnet50.ResNet50(include_top=False,weights='imagenet')
        layer_outputs=['conv2_block3_out','conv3_block4_out','conv4_block6_out','conv5_block3_out']
        outputs = [
        base.get_layer(layer_name).output
        for layer_name in layer_outputs
        ]
        super().__init__(inputs=base.inputs, outputs=outputs)
        