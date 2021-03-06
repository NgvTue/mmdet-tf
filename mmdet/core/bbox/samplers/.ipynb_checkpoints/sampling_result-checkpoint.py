

from mmdet_planing.utils import util_mixins

import tensorflow as tf
class SamplingResult(util_mixins.NiceRepr):
    """Bbox sampling result.
    Example:
        >>> # xdoctest: +IGNORE_WANT
        >>> from mmdet.core.bbox.samplers.sampling_result import *  # NOQA
        >>> self = SamplingResult.random(rng=10)
        >>> print(f'self = {self}')
        self = <SamplingResult({
            'neg_bboxes': torch.Size([12, 4]),
            'neg_inds': tensor([ 0,  1,  2,  4,  5,  6,  7,  8,  9, 10, 11, 12]),
            'num_gts': 4,
            'pos_assigned_gt_inds': tensor([], dtype=torch.int64),
            'pos_bboxes': torch.Size([0, 4]),
            'pos_inds': tensor([], dtype=torch.int64),
            'pos_is_gt': tensor([], dtype=torch.uint8)
        })>
    """

    def __init__(self, pos_inds, neg_inds, bboxes, gt_bboxes, assign_result):
        print("trace sampling")
        self.pos_inds = pos_inds
        self.neg_inds = neg_inds
        
        self.assign_result = assign_result
#         self.pos_bboxes =tf.gather(bboxes, pos_inds)# bboxes[pos_inds]
#         self.neg_bboxes =tf.gather(bboxes, neg_inds) # bboxes[neg_inds]
#         self.pos_is_gt = tf.gather(gt_flags, pos_inds) # gt_flags[pos_inds]
#         print(pos_inds,neg_inds)
#         self.num_gts = gt_bboxes.shape[0]
        
#         self.pos_assigned_gt_inds =tf.gather(assign_result.gt_inds,pos_inds) - 1
#         def f1():
#             return tf.reshape( tf.zeros(gt_bboxes.get_shape()),(-1,4))#  torch.empty_like(gt_bboxes).view(-1, 4)
#         def f2():
#             return tf.gather(gt_bboxes, self.pos_assigned_gt_inds)
#         # if tf.size(gt_bboxes) == 0:
#         #     # hack for index error case
#         #     self.pos_gt_bboxes =tf.reshape( tf.zeros(gt_bboxes.get_shape()),(-1,4))#  torch.empty_like(gt_bboxes).view(-1, 4)
#         # else:
#         #     if len(gt_bboxes.get_shape()) < 2:
#         #         gt_bboxes = tf.reshape(gt_bboxes,(-1, 4))

#         #     self.pos_gt_bboxes =tf.gather(gt_bboxes, self.pos_assigned_gt_inds)
#         self.pos_gt_bboxes = tf.cond(tf.size(gt_bboxes) ==0 , f1, f2)
#         if assign_result.labels is not None:
#             self.pos_gt_labels =tf.gather(assign_result.labels,pos_inds)
#         else:
#             self.pos_gt_labels = None
#         print(self.pos_gt_bboxes, self.pos_gt_labels)
#         print('trace done')
    @property
    def bboxes(self):
        """torch.Tensor: concatenated positive and negative boxes"""
        return tf.concat([self.pos_bboxes, self.neg_bboxes], axis=0)

    def to(self, device):
        """Change the device of the data inplace.
        Example:
            >>> self = SamplingResult.random()
            >>> print(f'self = {self.to(None)}')
            >>> # xdoctest: +REQUIRES(--gpu)
            >>> print(f'self = {self.to(0)}')
        """
        tf.print("to method call line 63/sampling_result.py")
        pass

    def __nice__(self):
        data = self.info.copy()
        data['pos_bboxes'] = data.pop('pos_bboxes').shape
        data['neg_bboxes'] = data.pop('neg_bboxes').shape
        parts = [f"'{k}': {v!r}" for k, v in sorted(data.items())]
        body = '    ' + ',\n    '.join(parts)
        return '{\n' + body + '\n}'

    @property
    def info(self):
        """Returns a dictionary of info about the object."""
        return {
            'pos_inds': self.pos_inds,
            'neg_inds': self.neg_inds,
#             'pos_bboxes': self.pos_bboxes,
#             'neg_bboxes': self.neg_bboxes,
#             'pos_is_gt': self.pos_is_gt,
#             'num_gts': self.num_gts,
#             'pos_assigned_gt_inds': self.pos_assigned_gt_inds,
        }

    @classmethod
    def random(cls, rng=None, **kwargs):
        """
        Args:
            rng (None | int | numpy.random.RandomState): seed or state.
            kwargs (keyword arguments):
                - num_preds: number of predicted boxes
                - num_gts: number of true boxes
                - p_ignore (float): probability of a predicted box assigned to \
                    an ignored truth.
                - p_assigned (float): probability of a predicted box not being \
                    assigned.
                - p_use_label (float | bool): with labels or not.
        Returns:
            :obj:`SamplingResult`: Randomly generated sampling result.
        Example:
            >>> from mmdet.core.bbox.samplers.sampling_result import *  # NOQA
            >>> self = SamplingResult.random()
            >>> print(self.__dict__)
        """
        tf.print("line 110 at sampling_result.py hasn't implemented yet")
        pass
        # from mmdet.core.bbox.samplers.random_sampler import RandomSampler
        # from mmdet.core.bbox.assigners.assign_result import AssignResult
        # from mmdet.core.bbox import demodata
        # rng = demodata.ensure_rng(rng)

        # # make probabalistic?
        # num = 32
        # pos_fraction = 0.5
        # neg_pos_ub = -1

        # assign_result = AssignResult.random(rng=rng, **kwargs)

        # # Note we could just compute an assignment
        # bboxes = demodata.random_boxes(assign_result.num_preds, rng=rng)
        # gt_bboxes = demodata.random_boxes(assign_result.num_gts, rng=rng)

        # if rng.rand() > 0.2:
        #     # sometimes algorithms squeeze their data, be robust to that
        #     gt_bboxes = gt_bboxes.squeeze()
        #     bboxes = bboxes.squeeze()

        # if assign_result.labels is None:
        #     gt_labels = None
        # else:
        #     gt_labels = None  # todo

        # if gt_labels is None:
        #     add_gt_as_proposals = False
        # else:
        #     add_gt_as_proposals = True  # make probabalistic?

        # sampler = RandomSampler(
        #     num,
        #     pos_fraction,
        #     neg_pos_ub=neg_pos_ub,
        #     add_gt_as_proposals=add_gt_as_proposals,
        #     rng=rng)
        # self = sampler.sample(assign_result, bboxes, gt_bboxes, gt_labels)
        # return self