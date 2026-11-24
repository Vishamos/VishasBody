"""ONNX 트래커의 좌표 계산 테스트 (모델 없이). 기대값은 MediaPipe 그래프 설정과 모델 출력 크기에서 가져온다."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from onnx_trackers import (HAND_ANCHOR_STRIDES, HAND_DETECT_SIZE, POSE_ANCHOR_STRIDES,  # noqa: E402
                           POSE_DETECT_SIZE, OneEuro, crop, hand_rect_from_landmarks, rect_from_points,
                           rect_iou, roi_points, ssd_anchors, transform_rect, weighted_nms)


class AnchorTest(unittest.TestCase):
    def test_counts_match_model_outputs(self):
        # 검출 모델 출력: 포즈 (1, 2254, 12), 손 (1, 2016, 18)
        self.assertEqual(len(ssd_anchors(POSE_DETECT_SIZE, POSE_ANCHOR_STRIDES)), 2254)
        self.assertEqual(len(ssd_anchors(HAND_DETECT_SIZE, HAND_ANCHOR_STRIDES)), 2016)

    def test_first_anchors(self):
        a = ssd_anchors(POSE_DETECT_SIZE, POSE_ANCHOR_STRIDES)
        np.testing.assert_allclose(a[0], [0.5 / 28, 0.5 / 28])      # 첫 칸, 앵커 2개가 같은 중심
        np.testing.assert_allclose(a[1], a[0])
        np.testing.assert_allclose(a[2], [1.5 / 28, 0.5 / 28])
        np.testing.assert_allclose(a[-1], [6.5 / 7, 6.5 / 7])


class RectTest(unittest.TestCase):
    def test_upright_points_have_no_rotation(self):
        # 크기 기준점이 중심 바로 위면 회전 0, 한 변 = 2 x 거리 x 배율
        cx, cy, w, h, rot = rect_from_points((100, 200), (100, 150), 1.25)
        self.assertEqual((cx, cy), (100, 200))
        self.assertAlmostEqual(w, 125)
        self.assertAlmostEqual(rot, 0)

    def test_right_pointing_is_plus_90(self):
        *_, rot = rect_from_points((0, 0), (10, 0), 1.0)
        self.assertAlmostEqual(rot, math.pi / 2)

    def test_roi_points_corners_and_rotation(self):
        rect = (50, 40, 20, 20, math.pi / 2)
        pts = roi_points(rect, np.array([[0.5, 0.5], [0.5, 0.0]]))
        np.testing.assert_allclose(pts[0], [50, 40])
        np.testing.assert_allclose(pts[1], [60, 40], atol=1e-9)   # 영역의 위쪽이 이미지 오른쪽을 향함

    def test_transform_shift_follows_rotation(self):
        # 회전 0: shift_y는 아래로(음수면 위로) h 비율만큼, 그다음 긴 변 정사각 + 배율
        cx, cy, w, h, _ = transform_rect((100, 100, 20, 10, 0.0), scale=2.0, shift_y=-0.5)
        self.assertAlmostEqual(cy, 95)
        self.assertEqual((w, h), (40, 40))
        cx, cy, *_ = transform_rect((100, 100, 20, 10, math.pi / 2), scale=1.0, shift_y=-0.5)
        self.assertAlmostEqual(cx, 105)   # 90도 회전이면 위쪽 = 이미지 오른쪽
        self.assertAlmostEqual(cy, 100)

    def test_crop_then_project_round_trip(self):
        # 크롭한 패치의 한 픽셀 위치를 roi_points로 되돌리면 원본의 같은 점이 나와야 함
        img = np.zeros((120, 160, 3), np.uint8)
        img[30, 90] = 255
        rect = (80, 40, 64, 64, 0.3)
        patch = crop(img, rect, 64, 0)[0, :, :, 0]
        r, c = np.unravel_index(np.argmax(patch), patch.shape)
        back = roi_points(rect, np.array([[(c + 0.5) / 64, (r + 0.5) / 64]]))[0]
        self.assertLess(np.hypot(back[0] - 90, back[1] - 30), 1.5)

    def test_hand_rect_upright_hand(self):
        # 손목 아래, 손가락 위로 곧게 선 손: 회전 0, 중심은 뿌리점들의 외접 사각형 중심
        pix = np.zeros((21, 2))
        pix[0] = (100, 200)
        for i, x in zip((1, 5, 9, 13, 17), (70, 85, 100, 115, 130)):
            for k in range(4):
                pix[i + k] = (x, 170 - 15 * k)
        cx, cy, w, h, rot = hand_rect_from_landmarks(pix)
        self.assertAlmostEqual(rot, 0, places=6)
        self.assertAlmostEqual(cx, 100)
        self.assertAlmostEqual(w, 60)

    def test_rect_iou(self):
        self.assertAlmostEqual(rect_iou((0, 0, 10, 10, 0), (0, 0, 10, 10, 1.0)), 1.0)   # 회전 무시
        self.assertAlmostEqual(rect_iou((0, 0, 10, 10, 0), (5, 0, 10, 10, 0)), 50 / 150)
        self.assertEqual(rect_iou((0, 0, 10, 10, 0), (20, 0, 10, 10, 0)), 0.0)


class NmsTest(unittest.TestCase):
    def test_weighted_merge_and_separate(self):
        boxes = np.array([[0, 0, 10, 10], [1, 0, 11, 10], [50, 50, 60, 60]], float)
        scores = np.array([0.9, 0.6, 0.8])
        kps = np.array([[[0, 0]], [[10, 0]], [[50, 50]]], float)
        out = weighted_nms(boxes, scores, kps)
        self.assertEqual(len(out), 2)
        score, box, kp = out[0]
        self.assertEqual(score, 0.9)                        # 점수는 가장 높은 것
        self.assertAlmostEqual(box[0], 0.6 / 1.5)           # 좌표는 점수 가중 평균
        self.assertAlmostEqual(kp[0, 0], 6 / 1.5)
        self.assertEqual(out[1][0], 0.8)


class OneEuroTest(unittest.TestCase):
    def test_constant_signal_unchanged_and_step_lags(self):
        f = OneEuro(0.05, 80.0)
        for k in range(5):
            np.testing.assert_allclose(f(k / 30, np.array([1.0])), [1.0])
        y = f(5 / 30, np.array([2.0]))[0]
        self.assertGreater(y, 1.0)      # 따라가되
        self.assertLess(y, 2.0)         # 한 번에 다 가지는 않음


if __name__ == "__main__":
    unittest.main()
