"""Body 프레임 패킷(1,080바이트) 인코딩. 기준: 명세 01 §4, 배치는 docs/protocol/README.md §2.

numpy 없이 표준 라이브러리만 쓴다(점 75개 규모라 충분히 빠르고, 테스트를 어느 PC에서나 돌리기 위해).
"""
import math
import struct

# VishaSynapse 시그니처와 Body 패킷 값
SIG_VISHAMOS = 11
SIG_BODY = 31
KIND_BODY_FRAME = 31
VERSION = 1

FLAG_POSE = 1 << 0
FLAG_LEFT_HAND = 1 << 1
FLAG_RIGHT_HAND = 1 << 2

POSE_POINTS = 33
HAND_POINTS = 21
HAND_WRIST = 0
POSE_FLOATS = POSE_POINTS * 4             # x, y, z, visibility
HAND_FLOATS = HAND_POINTS * 3 + 4         # x, y, z + 손바닥 쿼터니언
FLOAT_COUNT = POSE_FLOATS + HAND_FLOATS * 2

# to, from, kind, version, flags, 예약 3바이트, seq, timestamp_ms, float 268개
PACKET_FORMAT = f"<BBBBB3xII{FLOAT_COUNT}f"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)

ZERO_QUAT = (0.0, 0.0, 0.0, 0.0)


def to_unity(x, y, z):
    # MediaPipe(x 오른쪽, y 아래, z 카메라에서 멀어짐) -> Unity(x 캐릭터 오른쪽, y 위, z 앞)
    return -x, -y, -z


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _normalize(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return None if n < 1e-9 else (v[0] / n, v[1] / n, v[2] / n)


def look_rotation(forward, up):
    """Unity Quaternion.LookRotation(forward, up)과 같은 (x, y, z, w). 계산할 수 없으면 ZERO_QUAT."""
    f = _normalize(forward)
    if f is None:
        return ZERO_QUAT
    r = _normalize(_cross(up, f))         # Unity: right = Cross(up, forward)
    if r is None:
        return ZERO_QUAT
    u = _cross(f, r)

    # 열이 (right, up, forward)인 회전 행렬 -> 쿼터니언
    m00, m01, m02 = r[0], u[0], f[0]
    m10, m11, m12 = r[1], u[1], f[1]
    m20, m21, m22 = r[2], u[2], f[2]
    trace = m00 + m11 + m22
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        return ((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s)
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        return (0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s)
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        return ((m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s)
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2
    return ((m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s)


def palm_quaternion(axes):
    """hand_math 손바닥 축 (옆, 손바닥, 손가락; MediaPipe 좌표)을 Unity 좌표의 쿼터니언으로."""
    if axes is None:
        return ZERO_QUAT
    _, palm, finger = axes
    return look_rotation(to_unity(*finger), to_unity(*palm))


def _pose_values(pose_world):
    values = []
    for lm in pose_world:
        values += [*to_unity(lm.x, lm.y, lm.z), lm.visibility]
    return values


def _hand_values(hand):
    # 원점을 손목으로 옮긴 뒤 Unity 좌표로 (명세 01 §4.7)
    w = hand.world_landmarks[HAND_WRIST]
    values = []
    for lm in hand.world_landmarks:
        values += to_unity(lm.x - w.x, lm.y - w.y, lm.z - w.z)
    values += palm_quaternion(hand.axes)
    return values


def encode_frame(seq, timestamp_ms, pose_world, hands):
    """한 프레임을 1,080바이트로.

    pose_world: pose_world_landmarks[0] (33점) 또는 None
    hands: hand_math.HandState 목록 (is_left, world_landmarks, axes를 씀)
    """
    flags = 0
    pose = [0.0] * POSE_FLOATS
    left = [0.0] * HAND_FLOATS
    right = [0.0] * HAND_FLOATS

    if pose_world:
        flags |= FLAG_POSE
        pose = _pose_values(pose_world)
    for hand in hands:
        # 같은 쪽 손이 둘로 판정되면 먼저 온 손만 쓴다
        if hand.is_left and not flags & FLAG_LEFT_HAND:
            flags |= FLAG_LEFT_HAND
            left = _hand_values(hand)
        elif not hand.is_left and not flags & FLAG_RIGHT_HAND:
            flags |= FLAG_RIGHT_HAND
            right = _hand_values(hand)

    return struct.pack(PACKET_FORMAT, SIG_VISHAMOS, SIG_BODY, KIND_BODY_FRAME, VERSION, flags,
                       seq, timestamp_ms, *pose, *left, *right)
