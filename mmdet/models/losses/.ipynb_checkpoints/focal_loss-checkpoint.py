import tensorflow as tf
from tensorflow.python.keras.losses import Loss
import tensorflow_addons as tfa
from ..builder import LOSSES,build_loss
from .utils import reduce_loss, weight_reduce_loss
@tf.function(experimental_relax_shapes=True)
def focal_loss_funtion(pred, target, alpha = 0.25, gamma = 2., label_smoothing = 0.):
    """y_true: shape = (batch, n_anchors, 1)
       y_pred : shape = (batch, n_anchors, num_class)
    """ 
    pred_prob = tf.nn.sigmoid(pred)
    p_t = ((1-target )* pred_prob) + (target * (1 - pred_prob))
    alpha_factor = target * alpha + (1 - target) * (1 - alpha)
    modulating_factor =  tf.pow(p_t,gamma)
    ce = tf.nn.sigmoid_cross_entropy_with_logits(labels=target, logits=pred)
    loss_without_weights= alpha_factor * modulating_factor * ce
    return tf.math.reduce_sum(loss_without_weights,axis=-1)

@LOSSES.register_module()
class FocalLoss(tf.keras.layers.Layer):

    def __init__(self,
                 use_sigmoid=True,
                 gamma=2.0,
                 alpha=0.25,
                 reduction='mean',
                 loss_weight=1.0):
        """`Focal Loss <https://arxiv.org/abs/1708.02002>`_
        Args:
            use_sigmoid (bool, optional): Whether to the prediction is
                used for sigmoid or softmax. Defaults to True.
            gamma (float, optional): The gamma for calculating the modulating
                factor. Defaults to 2.0.
            alpha (float, optional): A balanced form for Focal Loss.
                Defaults to 0.25.
            reduction (str, optional): The method used to reduce the loss into
                a scalar. Defaults to 'mean'. Options are "none", "mean" and
                "sum".
            loss_weight (float, optional): Weight of loss. Defaults to 1.0.
        """
        super(FocalLoss, self).__init__()
        assert use_sigmoid is True, 'Only sigmoid focal loss supported now.'
        self.use_sigmoid = use_sigmoid
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction
        self.loss_weight = loss_weight

    def call(self,
                pred,
                target,
                weight=None,
                avg_factor=None,
                reduction_override=None):
        """Forward function.
        Args:
            pred (torch.Tensor): The prediction.
            target (torch.Tensor): The learning label of the prediction.
            weight (torch.Tensor, optional): The weight of loss for each
                prediction. Defaults to None.
            avg_factor (int, optional): Average factor that is used to average
                the loss. Defaults to None.
            reduction_override (str, optional): The reduction method used to
                override the original reduction method of the loss.
                Options are "none", "mean" and "sum".
        Returns:
            torch.Tensor: The calculated loss
        """
        # print(pred.shape, target.shape, weight.shape,avg_factor,reduction_override)
        assert reduction_override in (None, 'none', 'mean', 'sum')
#         print(pred.shape,target.shape,"focal")
        reduction = (
            reduction_override if reduction_override else self.reduction)
        if self.use_sigmoid:
            num_classes = pred.shape[1]
            target = tf.one_hot(target,  depth=num_classes)
            # loss_v = tfa.losses.SigmoidFocalCrossEntropy(from_logits=True,reduction = tf.keras.losses.Reduction.NONE,)
            loss_cls =focal_loss_funtion(pred, target) 
            # loss_cls=loss_v(target, pred)
            if weight is not None:
                if weight.shape != loss_cls.shape:
                    weight = tf.reshape(weight,(-1,))
            loss = weight_reduce_loss(loss_cls, weight, reduction, avg_factor)
        else:
            raise NotImplementedError
        return loss

@LOSSES.register_module()
class FocalLossKeras():
  """Compute the focal loss between `logits` and the golden `target` values.
  Focal loss = -(1-pt)^gamma * log(pt)
  where pt is the probability of being classified to the true class.
  """

  def __init__(self, alpha=0.25, gamma=2., label_smoothing=0.0,use_sigmoid=True, **kwargs):
    """Initialize focal loss.
    Args:
      alpha: A float32 scalar multiplying alpha to the loss from positive
        examples and (1-alpha) to the loss from negative examples.
      gamma: A float32 scalar modulating loss from hard and easy examples.
      label_smoothing: Float in [0, 1]. If > `0` then smooth the labels.
      **kwargs: other params.
    """
    super().__init__(**kwargs)
    self.alpha = alpha
    self.gamma = gamma
    self.use_sigmoid=use_sigmoid
    self.label_smoothing = label_smoothing

  @tf.autograph.experimental.do_not_convert
  def __call__(self, 
                y_pred,
                y_true,
                weight=None,
                avg_factor=None,
                reduction_override=None):
    """Compute focal loss for y and y_pred.
    Args:
      y: A tuple of (normalizer, y_true), where y_true is the target class.
      y_pred: A float32 tensor [batch, height_in, width_in, num_predictions].
    Returns:
      the focal loss.
    """
    alpha = tf.convert_to_tensor(self.alpha, dtype=y_pred.dtype)
    gamma = tf.convert_to_tensor(self.gamma, dtype=y_pred.dtype)
    y_true = tf.one_hot(y_true, y_pred.shape[1])
    # compute focal loss multipliers before label smoothing, such that it will
    # not blow up the loss.
    pred_prob = tf.sigmoid(y_pred)
    p_t = (y_true * pred_prob) + ((1 - y_true) * (1 - pred_prob))
    alpha_factor = y_true * alpha + (1 - y_true) * (1 - alpha)
    modulating_factor = (1.0 - p_t)**gamma

    # apply label smoothing for cross_entropy for each entry.
    y_true = y_true * (1.0 - self.label_smoothing) + 0.5 * self.label_smoothing
    ce = tf.nn.sigmoid_cross_entropy_with_logits(labels=y_true, logits=y_pred)

    # compute the final loss and return
    loss= alpha_factor * modulating_factor * ce 
    loss= tf.math.reduce_sum(loss,axis=-1)
   
    weight = tf.reshape(weight,(-1,))
    loss = loss * tf.cast(weight, loss.dtype)
    return tf.math.reduce_sum(loss) / tf.cast(avg_factor,loss.dtype)