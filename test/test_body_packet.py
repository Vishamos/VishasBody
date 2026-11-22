"""Body 패킷 인코딩 테스트. 기대값은 명세 01 §4와 docs/protocol/README.md §2∼4에서 가져온다."""
import math
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body_packet import encode_frame  # noqa: E402

# 프로토콜 §2 배치
SIZE = 1080
POSE_OFS, LEFT_OFS, RIGHT_OFS = 16, 544, 812


def floats(data, offset, count):
    return struct.unpack_from(f"<{count}f", data, offset)


def lm(x, y, z, visibility=None):
    return SimpleNamespace(x=x, y=y, z=z, visibility=visibility)


def make_pose():
    # i번 점 = (i, i+0.25, i+0.5), visibility 0.5 (float32로 정확히 표현되는 값)
    return [lm(i, i + 0.25, i + 0.5, 0.5) for i in range(33)]


def make_hand(is_left, wrist=(0.5, 0.25, -0.125), axes=None):
    # j번 점 = 손목 + (j, 2j, 3j) / 64
    pts = [lm(wrist[0] + j / 64, wrist[1] + 2 * j / 64, wrist[2] + 3 * j / 64) for j in range(21)]
    return SimpleNamespace(is_left=is_left, world_landmarks=pts, axes=axes)


def rotate(q, v):
    # 쿼터니언 q = (x, y, z, w)로 v 회전 (Unity의 q * v와 같은 계산)
    qv = q[:3]
    w = q[3]

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    t = [2 * c for c in cross(qv, v)]
    c2 = cross(qv, t)
    return tuple(v[i] + w * t[i] + c2[i] for i in range(3))


class HeaderTest(unittest.TestCase):
    def test_size_is_fixed(self):
        cases = [(None, []), (make_pose(), []), (None, [make_hand(True)]),
                 (make_pose(), [make_hand(True), make_hand(False)])]
        for pose, hands in cases:
            self.assertEqual(len(encode_frame(1, 0, pose, hands)), SIZE)

    def test_header_bytes(self):
        data = encode_frame(7, 123456, None, [])
        self.assertEqual(data[0], 11)       # to Vishamos
        self.assertEqual(data[1], 31)       # from Body
        self.assertEqual(data[2], 31)       # kind
        self.assertEqual(data[3], 1)        # version
        self.assertEqual(data[5:8], b"\x00\x00\x00")
        self.assertEqual(struct.unpack_from("<II", data, 8), (7, 123456))

    def test_seq_little_endian(self):
        data = encode_frame(0x01020304, 0, None, [])
        self.assertEqual(data[8:12], b"\x04\x03\x02\x01")


class FlagsTest(unittest.TestCase):
    def test_nothing_detected_is_all_zero(self):
        data = encode_frame(1, 0, None, [])
        self.assertEqual(data[4], 0)
        self.assertEqual(data[16:], bytes(SIZE - 16))

    def test_flag_bits(self):
        self.assertEqual(encode_frame(1, 0, make_pose(), [])[4], 0b001)
        self.assertEqual(encode_frame(1, 0, None, [make_hand(True)])[4], 0b010)
        self.assertEqual(encode_frame(1, 0, None, [make_hand(False)])[4], 0b100)
        self.assertEqual(encode_frame(1, 0, make_pose(), [make_hand(False), make_hand(True)])[4], 0b111)

    def test_only_left_hand_leaves_others_zero(self):
        data = encode_frame(1, 0, None, [make_hand(True)])
        self.assertEqual(data[POSE_OFS:LEFT_OFS], bytes(LEFT_OFS - POSE_OFS))
        self.assertEqual(data[RIGHT_OFS:], bytes(SIZE - RIGHT_OFS))
        self.assertNotEqual(data[LEFT_OFS:RIGHT_OFS], bytes(RIGHT_OFS - LEFT_OFS))

    def test_duplicate_side_uses_first_hand(self):
        first = make_hand(True, wrist=(0, 0, 0))
        second = make_hand(True, wrist=(1, 1, 1))
        second.world_landmarks[1].x += 1     # 손목 기준 상대 위치가 첫 손과 다르게
        data = encode_frame(1, 0, None, [first, second])
        self.assertEqual(data[4], 0b010)
        self.assertEqual(data[LEFT_OFS:RIGHT_OFS], encode_frame(1, 0, None, [first])[LEFT_OFS:RIGHT_OFS])


class CoordinateTest(unittest.TestCase):
    def test_pose_converted_to_unity(self):
        f = floats(encode_frame(1, 0, make_pose(), []), POSE_OFS, 132)
        for i in (0, 15, 32):
            self.assertEqual(f[i * 4:i * 4 + 4], (-i, -(i + 0.25), -(i + 0.5), 0.5))

    def test_hand_origin_is_wrist_and_converted(self):
        data = encode_frame(1, 0, None, [make_hand(True), make_hand(False)])
        for ofs in (LEFT_OFS, RIGHT_OFS):
            f = floats(data, ofs, 63)
            self.assertEqual(f[0:3], (0.0, 0.0, 0.0))
            for j in (1, 9, 20):
                self.assertEqual(f[j * 3:j * 3 + 3], (-j / 64, -2 * j / 64, -3 * j / 64))


class PalmQuaternionTest(unittest.TestCase):
    def quat(self, axes, is_left=True):
        ofs = LEFT_OFS if is_left else RIGHT_OFS
        return floats(encode_frame(1, 0, None, [make_hand(is_left, axes=axes)]), ofs + 63 * 4, 4)

    def assertVecAlmostEqual(self, a, b):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=5)

    def check_axes(self, side, palm_mp, finger_mp, finger_unity, palm_unity):
        q = self.quat((side, palm_mp, finger_mp))
        self.assertAlmostEqual(math.sqrt(sum(c * c for c in q)), 1.0, places=5)
        self.assertVecAlmostEqual(rotate(q, (0, 0, 1)), finger_unity)   # +z = 손가락 방향
        self.assertVecAlmostEqual(rotate(q, (0, 1, 0)), palm_unity)     # +y = 손바닥 방향

    def test_fingers_up_palm_toward_camera(self):
        # MediaPipe: 손가락 위(-y), 손바닥 카메라 쪽(-z) -> Unity: 손가락 +y, 손바닥 +z(캐릭터 앞)
        self.check_axes((1, 0, 0), (0, 0, -1), (0, -1, 0), (0, 1, 0), (0, 0, 1))

    def test_fingers_forward_palm_down(self):
        # MediaPipe: 손가락 카메라 쪽(-z), 손바닥 아래(+y) -> Unity: 손가락 +z, 손바닥 -y
        self.check_axes((1, 0, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1), (0, -1, 0))

    def test_identity_rotation(self):
        # Unity 손가락 +z, 손바닥 +y = 회전 없음 (0, 0, 0, 1)
        q = self.quat(((-1, 0, 0), (0, -1, 0), (0, 0, -1)))
        self.assertVecAlmostEqual(q, (0, 0, 0, 1))

    def test_oblique_direction(self):
        s = 1 / math.sqrt(2)
        self.check_axes((0, 0, 1), (s, s, 0), (-s, s, 0), (s, -s, 0), (-s, -s, 0))

    def test_no_axes_gives_zero(self):
        self.assertEqual(self.quat(None), (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(self.quat(None, is_left=False), (0.0, 0.0, 0.0, 0.0))

    def test_degenerate_axes_gives_zero(self):
        # 손가락과 손바닥 방향이 평행이면 회전을 정할 수 없음
        self.assertEqual(self.quat(((0, 0, 0), (0, 1, 0), (0, 1, 0))), (0.0, 0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
