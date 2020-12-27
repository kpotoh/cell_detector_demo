import os
import sys
import tempfile

import cv2
import numpy as np
import matplotlib.pyplot as plt

from utils.tracker_with_masks import centroid_multi_tracker
from utils import visualisation_utils as vis_util

DEFAULT_VIDEO_FILEPATH = './data/Well_A2_25_48.avi'
DEFAULT_VIDEO_LABELS_PATH = './data/labels48.npy'


class CellDetector:
    def __init__(self):
        self.tracker = centroid_multi_tracker
        self.category_index = {'name': 'cell', 'id': 0}
        self.prelabeled = np.load(DEFAULT_VIDEO_LABELS_PATH,
                                  allow_pickle=True)

    def predict_image(self, image, default_idx=None):
        """
        pass image in the ... format and return prediction\t
        @param image - np.array \t
        @param default_index - [0, 47], if default_index specified, \
        labels will be collected from file

        return pred_image, boxes, scores, masks
        """
        if default_idx is None:
            return image, [], [], []

        image = image.copy()
        boxes = self.prelabeled[0][0][default_idx]
        scores = self.prelabeled[0][1][default_idx]
        masks = self.prelabeled[0][2][default_idx]
        classes = [0 for _ in range(len(boxes))]
        track_ids = list(range(len(boxes)))

        # normalisation, because vizualisator works with such data
        size = image.shape[1::-1]
        if len(boxes) > 0:
            boxes = boxes / [size[1], size[0], size[1], size[0]]

        vis_util.visualize_boxes_and_labels_on_image_array(
            image,
            boxes,
            classes,
            scores,
            self.category_index,
            track_ids=track_ids,
            instance_masks=masks,
            use_normalized_coordinates=True,
            line_thickness=1,
            min_score_thresh=.5,
            max_boxes_to_draw=100,
            skip_labels=True,
        )
        return image, boxes, scores, masks

    def predict_video(self, video_path=DEFAULT_VIDEO_FILEPATH):
        video = cv2.VideoCapture(video_path)
        size = (int(video.get(3)), int(video.get(4)))
        mot_tracker = self.tracker(maxLost=4, max_jump=150, size=size)
        predictions = []
        ok = True
        i = 0
        while ok:
            ok, frame = video.read()
            if not ok:
                break
            _, boxes, scores, masks = self.predict_image(frame, i)

            tracked_objects = mot_tracker.update(boxes, masks, scores)

            track_ids = np.array(list(tracked_objects.keys()))
            boxes = np.array([obj['box'] for obj in tracked_objects.values()])
            masks = np.array([obj['mask'] for obj in tracked_objects.values()])
            classes = [0 for _ in range(len(boxes))]
            scores = np.array(
                [obj['score'] for obj in tracked_objects.values()]
            )

            vis_util.visualize_boxes_and_labels_on_image_array(
                frame,
                boxes,
                classes,
                scores,
                self.category_index,
                track_ids=track_ids,
                instance_masks=masks,
                use_normalized_coordinates=True,
                line_thickness=1,
                min_score_thresh=.5,
                max_boxes_to_draw=100,
                skip_labels=True,
            )
            predictions.append([
                frame,
                boxes,
                scores,
                masks,
                track_ids,
            ])
            i += 1
        video.release()
        return predictions


def bbox_center(box):
    """@param box - array[4], dtype=float"""
    y = (box[0] + box[2]) / 2
    x = (box[1] + box[3]) / 2
    return x, (1 - y)


def get_track(video_prediction):
    ncell_max = 500
    tracks = [[] for _ in range(ncell_max)]
    for _, boxes, _, _, track_ids in video_prediction:
        centres = list(map(bbox_center, boxes))
        for i in range(len(boxes)):
            if track_ids[i] < 500:
                tracks[track_ids[i]].append(centres[i])

    tracks = [x for x in tracks if len(x) > 1]
    return tracks


def write_video(video_prediction, filepath=None):
    if filepath is None:
        file = tempfile.NamedTemporaryFile(
            suffix='.webm',
            delete=False
        )
        filepath = file.name
        file.close()
    if not filepath.endswith('.webm'):
        filepath = filepath + '.webm'
    size = video_prediction[0][0].shape[1::-1]
    fourcc = cv2.VideoWriter_fourcc(*'vp80')
    out = cv2.VideoWriter(filepath, fourcc, 3, size)
    for pred in video_prediction:
        frame = pred[0]
        out.write(frame)
    out.release()
    return filepath


def plot_trajectories_plot(tracks):
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    for i, cur_track in enumerate(tracks):
        start_x, start_y = cur_track[0]
        X = [x[0] - start_x for x in cur_track]
        Y = [y[1] - start_y for y in cur_track]
        X, Y = np.array(X), np.array(Y)
        ax.plot(X, Y, label=f'cell_{i}',)
    ax.plot([0], [0], 'ok')

    ax.set_title('Centered cell trajectory plot')
    ax.set_xlabel('x coordinate')
    ax.set_ylabel('y coordinate')
    return fig
