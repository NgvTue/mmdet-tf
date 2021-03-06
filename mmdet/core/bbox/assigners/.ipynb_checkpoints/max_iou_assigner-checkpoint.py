from token import RPAR
import tensorflow as tf

from ..builder import BBOX_ASSIGNERS
from ..iou_calculators import build_iou_calculator
from .base_assigner import BaseAssigner
from .assign_result import AssignResult

def _set_values_using_indicator( x, indicator, val):
        """Set the indicated fields of x to val.
        Args:
        x: tensor.
        indicator: boolean with same shape as x.
        val: scalar with value to set.
        Returns:
        modified tensor.
        """
        indicator = tf.cast(indicator, x.dtype)
        return x * (1 - indicator) + val * indicator
@BBOX_ASSIGNERS.register_module()
class MaxIoUAssigner(BaseAssigner):
    """Assign a corresponding gt bbox or background to each bbox.
    Each proposals will be assigned with `-1`, or a semi-positive integer
    indicating the ground truth index.
    - -1: negative sample, no assigned gt
    - semi-positive integer: positive sample, index (0-based) of assigned gt
    Args:
        pos_iou_thr (float): IoU threshold for positive bboxes.
        neg_iou_thr (float or tuple): IoU threshold for negative bboxes.
        min_pos_iou (float): Minimum iou for a bbox to be considered as a
            positive bbox. Positive samples can have smaller IoU than
            pos_iou_thr due to the 4th step (assign max IoU sample to each gt).
        gt_max_assign_all (bool): Whether to assign all bboxes with the same
            highest overlap with some gt to that gt.
        ignore_iof_thr (float): IoF threshold for ignoring bboxes (if
            `gt_bboxes_ignore` is specified). Negative values mean not
            ignoring any bboxes.
        ignore_wrt_candidates (bool): Whether to compute the iof between
            `bboxes` and `gt_bboxes_ignore`, or the contrary.
        match_low_quality (bool): Whether to allow low quality matches. This is
            usually allowed for RPN and single stage detectors, but not allowed
            in the second stage. Details are demonstrated in Step 4.
        gpu_assign_thr (int): The upper bound of the number of GT for GPU
            assign. When the number of gt is above this threshold, will assign
            on CPU device. Negative values mean not assign on CPU.
    """
    def __init__(self,
                 pos_iou_thr,
                 neg_iou_thr,
                 min_pos_iou=.0,
                 gt_max_assign_all=True,
                 ignore_iof_thr=-1,
                 ignore_wrt_candidates=True,
                 match_low_quality=True,
                 gpu_assign_thr=-1,
                 iou_calculator=dict(type='BboxOverlaps2D')):
        self.pos_iou_thr = pos_iou_thr
        self.neg_iou_thr = neg_iou_thr
        self.min_pos_iou = min_pos_iou
        self.gt_max_assign_all = gt_max_assign_all
        self.ignore_iof_thr = ignore_iof_thr
        self.ignore_wrt_candidates = ignore_wrt_candidates
        self.gpu_assign_thr = gpu_assign_thr
        self.match_low_quality = match_low_quality
        self.iou_calculator = build_iou_calculator(iou_calculator)
    
    def assign(self, bboxes, gt_bboxes, gt_labels=None):
        """Assign gt to bboxes.
        This method assign a gt bbox to every bbox (proposal/anchor), each bbox
        will be assigned with -1, or a semi-positive number. -1 means negative
        sample, semi-positive number is the index (0-based) of assigned gt.
        The assignment is done in following steps, the order matters.
        1. assign every bbox to the background
        2. assign proposals whose iou with all gts < neg_iou_thr to 0
        3. for each bbox, if the iou with its nearest gt >= pos_iou_thr,
           assign it to that bbox
        4. for each gt bbox, assign its nearest proposals (may be more than
           one) to itself
        Args:
            bboxes (Tensor): Bounding boxes to be assigned, shape(n, 4).
            gt_bboxes (Tensor): Groundtruth boxes, shape (k, 4).
            gt_bboxes_ignore (Tensor, optional): Ground truth bboxes that are
                labelled as `ignored`, e.g., crowd boxes in COCO.
            gt_labels (Tensor, optional): Label of gt_bboxes, shape (k, ).
        Returns:
            :obj:`AssignResult`: The assign result.
        Example:
            >>> self = MaxIoUAssigner(0.5, 0.5)
            >>> bboxes = torch.Tensor([[0, 0, 10, 10], [10, 10, 20, 20]])
            >>> gt_bboxes = torch.Tensor([[0, 0, 10, 9]])
            >>> assign_result = self.assign(bboxes, gt_bboxes)
            >>> expected_gt_inds = torch.LongTensor([1, 0])
            >>> assert torch.all(assign_result.gt_inds == expected_gt_inds)
        """
        assign_on_cpu = True if (self.gpu_assign_thr > 0) and (
            gt_bboxes.shape[0] > self.gpu_assign_thr) else False
        # compute overlap and assign gt on CPU when number of GT is large
        if assign_on_cpu:
            tf.print("control cpu compute not implement at line 89 max_iou_assigner.py")

        mask_ignore_bboxex =tf.reshape(tf.math.reduce_sum(gt_bboxes,axis=-1),(-1,))
        mask_ignore_bboxex = tf.where(mask_ignore_bboxex > 2.,1,0)
       
        overlaps = self.iou_calculator(gt_bboxes, bboxes)
        assign_result = self.assign_wrt_overlaps(overlaps, gt_labels,mask_ignore_bboxex)
        return assign_result
    
    def assign_wrt_overlaps(self, overlaps, gt_labels=None,valid_rows=None):
        """Assign w.r.t. the overlaps of bboxes with gts.
        Args:
            overlaps (Tensor): Overlaps between k gt_bboxes and n bboxes,
                shape(k, n).
            gt_labels (Tensor, optional): Labels of k gt_bboxes, shape (k, ).
        Returns:
            :obj:`AssignResult`: The assign result.
        """
        matcher = self._match(overlaps, valid_rows)
        assigned_gt_inds = matcher + 1
        if gt_labels is not None:
            fake_gt_labels = tf.concat([tf.convert_to_tensor([-1], dtype = gt_labels.dtype),gt_labels], axis=0)
            pos_inds = tf.where(tf.not_equal(assigned_gt_inds, -1),1, 0)
            assigned_labels=tf.gather(fake_gt_labels, pos_inds * assigned_gt_inds)
        else:
            assigned_labels = None
        return assigned_gt_inds,overlaps, assigned_labels
        # max_overlaps =tf.math.reduce_max(overlaps,axis=0)
        # argmax_overlaps = tf.math.argmax(overlaps, axis=0,output_type=tf.dtypes.int32)
        # gt_argmax_overlaps=tf.math.argmax(overlaps, axis=1,output_type=tf.dtypes.int32)
        # if isinstance(self.neg_iou_thr, float):
        #     assigned_gt_inds =tf.where(tf.logical_and(max_overlaps >=0., max_overlaps < self.neg_iou_thr),0,-1)
        # else:
        #     assigned_gt_inds = tf.where(tf.logical_and(max_overlaps >=self.neg_iou_thr[0], max_overlaps < self.neg_iou_thr[1]),0,-1)
    
        #     assigned_gt_inds = tf.where(tf.logical_and(max_overlaps >=self.neg_iou_thr[0], max_overlaps < self.neg_iou_thr[1]),0,-1)


        # # 3. assign positive: above positive IoU threshold
        # pos_inds =tf.where( max_overlaps >= self.pos_iou_thr, 1,0)
        # value = pos_inds*(argmax_overlaps + 1) 

        # assigned_gt_inds =   value + (1-pos_inds)*assigned_gt_inds
        # if self.match_low_quality:
        #     gt_argmax_overlaps= tf.where(valid_rows == 1,gt_argmax_overlaps,-1)

        #     force_match_column_indicators = tf.one_hot(
        #         gt_argmax_overlaps, depth=tf.shape(overlaps)[1])
        #     force_match_row_ids = tf.argmax(force_match_column_indicators, 0,
        #                                 output_type=tf.int32) 
        #     force_match_column_mask = tf.cast(
        #         tf.reduce_max(force_match_column_indicators, 0), tf.bool)


        #     assigned_gt_inds = tf.where(force_match_column_mask,
        #                             force_match_row_ids + 1, assigned_gt_inds)
        #     # pass
 
        # if gt_labels is not None:
        #     fake_gt_labels = tf.concat([tf.convert_to_tensor([-1], dtype = gt_labels.dtype),gt_labels], axis=0)
        #     pos_inds = tf.where(tf.not_equal(assigned_gt_inds, -1),1, 0)
        #     assigned_labels=tf.gather(fake_gt_labels, pos_inds * assigned_gt_inds)
        # else:
        #     assigned_labels = None
       
        # return assigned_gt_inds, max_overlaps, assigned_labels

    def _match(self, similarity_matrix, valid_rows):
        """Tries to match each column of the similarity matrix to a row.
        Args:
        similarity_matrix: tensor of shape [N, M] representing any similarity
            metric.
        valid_rows: a boolean tensor of shape [N] indicating valid rows.
        Returns:
        Match object with corresponding matches for each of M columns.
        """
        matches = tf.argmax(similarity_matrix, 0, output_type=tf.int32)


        # Get logical indices of ignored and unmatched columns as tf.int64
        matched_vals = tf.reduce_max(similarity_matrix, 0)
        valid =tf.gather(valid_rows,matches)
        valid =tf.cast(valid,tf.float32)
        below_unmatched_threshold = tf.greater(self.neg_iou_thr,
                                            matched_vals)
        below_unmatched_threshold=tf.cast(below_unmatched_threshold, valid.dtype)
        below_unmatched_threshold = below_unmatched_threshold * valid + (1-valid) * 0
            
        between_thresholds = tf.logical_and(
            tf.greater_equal(matched_vals, self.neg_iou_thr),
            tf.greater(self.pos_iou_thr, matched_vals))
        
        matches = self._set_values_using_indicator(matches,
                                                    below_unmatched_threshold,
                                                    -1)
        matches = self._set_values_using_indicator(matches,
                                                    between_thresholds,
                                                    -2)


        if self.match_low_quality:
            similarity_matrix_shape = similarity_matrix.shape
            force_match_column_ids = tf.argmax(similarity_matrix, 1,
                                            output_type=tf.int32)
            force_match_column_indicators = (
                tf.one_hot(
                    force_match_column_ids, depth=similarity_matrix_shape[1]) *
                tf.cast(tf.expand_dims(valid_rows, axis=-1), dtype=tf.float32))
            force_match_row_ids = tf.argmax(force_match_column_indicators, 0,
                                            output_type=tf.int32)
            force_match_column_mask = tf.cast(
                tf.reduce_max(force_match_column_indicators, 0), tf.bool)
            final_matches = tf.where(force_match_column_mask,
                                    force_match_row_ids, matches)
            return final_matches
        else:
            return matches
    def _set_values_using_indicator(self, x, indicator, val):
        """Set the indicated fields of x to val.
        Args:
        x: tensor.
        indicator: boolean with same shape as x.
        val: scalar with value to set.
        Returns:
        modified tensor.
        """
        indicator = tf.cast(indicator, x.dtype)
        return tf.add(tf.multiply(x, 1 - indicator), val * indicator)