import warnings


from mmdet.utils.registry import Registry,build_from_cfg

MODELS = Registry('models')
BACKBONES = MODELS
NECKS = MODELS
ROI_EXTRACTORS = MODELS
SHARED_HEADS = MODELS
HEADS = MODELS
LOSSES = MODELS
DETECTORS = MODELS

def build_backbone(cfg):
    """Build backbone."""
    if 'return_funtion' in cfg:
        cfg.pop("return_funtion")
        converter_cls = NECKS.get(cfg['type'])
        cfg.pop("type")
        return converter_cls.make_funtion_model(
            **cfg
        )
    return BACKBONES.build(cfg)


def build_neck(cfg):
    """Build neck."""
    if 'return_funtion' in cfg:
        cfg.pop("return_funtion")
        converter_cls = NECKS.get(cfg['type'])
        cfg.pop("type")
        return converter_cls.make_funtion_model(
            **cfg
        )
    return NECKS.build(cfg)


def build_roi_extractor(cfg):
    """Build roi extractor."""
    return ROI_EXTRACTORS.build(cfg)


def build_shared_head(cfg):
    """Build shared head."""
    return SHARED_HEADS.build(cfg)


def build_head(cfg):
    """Build head."""
    return HEADS.build(cfg)

def build_loss(cfg):
    """Build loss."""
    if 'return_funtion' in cfg:
        cfg.pop("return_funtion")
        converter_cls = LOSSES.get(cfg['type'])
        return converter_cls.make_funtion_model(
            **cfg
        )
    return LOSSES.build(cfg)


def build_detector(cfg, train_cfg=None, test_cfg=None):
    """Build detector."""
    if train_cfg is not None or test_cfg is not None:
        warnings.warn(
            'train_cfg and test_cfg is deprecated, '
            'please specify them in model', UserWarning)
    assert cfg.get('train_cfg') is None or train_cfg is None, \
        'train_cfg specified in both outer field and model field '
    assert cfg.get('test_cfg') is None or test_cfg is None, \
        'test_cfg specified in both outer field and model field '
    return DETECTORS.build(
        cfg, default_args=dict(train_cfg=train_cfg, test_cfg=test_cfg))
