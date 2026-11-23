"""루트 위치 추정 테스트. 기대값은 명세 01 §5에서 가져온다.

알려진 위치 t에 가상 몸(월드 좌표)을 두고 카메라로 투영한 화면 좌표를 넣었을 때 t가 다시 나오는지 본다.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from root_position import estimate_root, focal_px  # noqa: E402

W, H = 640, 480
F = 500.0


def make_world():
    # 골반 원점, 미터, MediaPipe 축(x 오른쪽, y 아래, z 카메라에서 멀어짐). 몸을 약간 비튼 상반신 33점
    pts = []
    for i in range(33):
        x = ((i % 5) - 2) * 0.1
        y = -0.5 + (i % 7) * 0.08
        z = ((i % 3) - 1) * 0.05
        pts.append(SimpleNamespace(x=x, y=y, z=z))
    return pts


def project(world, t, visible=range(33), width=W, height=H, focal=F):
    # 핀홀 카메라: u = f·(X+tx)/(Z+tz) + cx (명세 01 §5.1)
    pts = []
    for i, w in enumerate(world):
        depth = w.z + t[2]
        u = focal * (w.x + t[0]) / depth + width / 2
        v = focal * (w.y + t[1]) / depth + height / 2
        pts.append(SimpleNamespace(x=u / width, y=v / height, visibility=1.0 if i in visible else 0.0))
    return pts


class EstimateRootTest(unittest.TestCase):
    def assertVecAlmostEqual(self, a, b, places=6):
        self.assertIsNotNone(a)
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=places)

    def test_recovers_known_position(self):
        world = make_world()
        for t in ((0.0, 0.0, 1.5), (0.1, -0.2, 1.5), (-0.3, 0.15, 0.8), (0.2, 0.1, 3.0)):
            self.assertVecAlmostEqual(estimate_root(project(world, t), world, W, H, F), t)

    def test_moving_closer_reduces_z(self):
        world = make_world()
        far = estimate_root(project(world, (0, 0, 2.0)), world, W, H, F)
        near = estimate_root(project(world, (0, 0, 1.0)), world, W, H, F)
        self.assertLess(near[2], far[2])

    def test_arms_and_legs_are_ignored(self):
        # 팔(13~22)·다리(25~32)는 보이는 것으로 나와도 쓰지 않는다 (§5.1)
        world = make_world()
        t = (0.1, -0.2, 1.5)
        pts = project(world, t)
        for i in (*range(13, 23), *range(25, 33)):
            pts[i].x, pts[i].y = 0.0, 0.0      # 엉뚱한 위치
        self.assertVecAlmostEqual(estimate_root(pts, world, W, H, F), t)

    def test_wrong_arm_depth_does_not_move_root(self):
        # 카메라 쪽으로 뻗은 팔의 월드 깊이가 틀려도 루트는 그대로 (실측 문제, §5.1)
        world = make_world()
        t = (0.1, -0.2, 1.5)
        pts = project(world, t)
        for i in range(13, 23):
            world[i].z -= 0.3
        self.assertVecAlmostEqual(estimate_root(pts, world, W, H, F), t)

    def test_low_visibility_points_are_ignored(self):
        world = make_world()
        t = (0.1, -0.2, 1.5)
        pts = project(world, t, visible=range(0, 10))
        for i in (10, 11, 12, 23, 24):
            pts[i].x, pts[i].y = 0.0, 0.0      # 가려진 점은 값이 틀려도 무관
            pts[i].visibility = 0.49
        self.assertVecAlmostEqual(estimate_root(pts, world, W, H, F), t)

    def test_four_points_is_enough(self):
        world = make_world()
        t = (0.1, -0.2, 1.5)
        self.assertVecAlmostEqual(estimate_root(project(world, t, visible=range(4)), world, W, H, F), t)

    def test_three_points_is_invalid(self):
        world = make_world()
        self.assertIsNone(estimate_root(project(world, (0, 0, 1.5), visible=range(3)), world, W, H, F))

    def test_no_pose_is_invalid(self):
        self.assertIsNone(estimate_root(None, None, W, H, F))

    def test_behind_camera_is_invalid(self):
        # tz <= 0 이면 유효하지 않음 (§5.2)
        world = make_world()
        self.assertIsNone(estimate_root(project(world, (0, 0, -1.5)), world, W, H, F))


class FocalTest(unittest.TestCase):
    def test_diagonal_fov(self):
        # 대각선 5픽셀, 화각 90° -> f = 2.5 / tan(45°) = 2.5 (§5.3)
        self.assertAlmostEqual(focal_px(3, 4, 90), 2.5)

    def test_wider_fov_gives_shorter_focal(self):
        self.assertLess(focal_px(640, 480, 80), focal_px(640, 480, 60))


if __name__ == "__main__":
    unittest.main()
