import math
from dataclasses import dataclass

import numpy as np

# 핸드 랜드마크 번호 (21점)
H_WRIST, H_INDEX_MCP, H_MIDDLE_MCP, H_PINKY_MCP = 0, 5, 9, 17
PALM_POINTS = (0, 5, 9, 13, 17)  # 손바닥 중심 계산용: 손목 + 손가락 뿌리 4개


@dataclass
class HandState:
    is_left: bool            # 사람 기준 왼손이면 True
    landmarks: list          # 화면 좌표 (0~1), 21점
    world_landmarks: list    # 실제 거리 (미터, 손 중심 기준), 21점
    axes: tuple | None       # (X 옆, Y 손바닥, Z 손가락) 단위 벡터, 계산 불가면 None

    @property
    def palm_z(self):
        # 손바닥 축의 z (음수 = 카메라 쪽)
        return None if self.axes is None else float(self.axes[1][2])


def palm_axes(wrist_p, finger_p, index_p, pinky_p, is_left):
    forward = finger_p - wrist_p                   # 손목 -> 손가락 방향
    across = index_p - pinky_p                     # 새끼 -> 검지 방향 (손 폭)

    normal = np.cross(forward, across)             # 손바닥 쪽 수직 방향
    if not is_left:
        normal = -normal                           # 오른손은 부호가 반대

    if np.linalg.norm(forward) < 1e-6 or np.linalg.norm(normal) < 1e-6:
        return None
    f = forward / np.linalg.norm(forward)
    n = normal / np.linalg.norm(normal)
    s = np.cross(n, f)                             # 옆 방향 (f, n과 수직)
    return s, n, f


def assign_sides(hand_result, pose_pts):
    # 각 손이 사람 기준 왼손(True)인지 오른손(False)인지 정함
    # 포즈의 손목(15=왼, 16=오른)과 가까운 쪽으로 매칭
    hands = hand_result.hand_landmarks
    if not hands:
        return []
    if pose_pts is None:
        # 포즈가 없으면 handedness 라벨 사용
        # (라벨은 좌우 반전된 셀카 영상 기준이라, 반전 안 한 입력에서는 반대로 읽음)
        return [hand_result.handedness[k][0].category_name == "Right" for k in range(len(hands))]

    def d(k, pose_i):
        return math.hypot(hands[k][H_WRIST].x - pose_pts[pose_i].x,
                          hands[k][H_WRIST].y - pose_pts[pose_i].y)

    if len(hands) == 1:
        return [d(0, 15) < d(0, 16)]
    # 손 2개: 두 가지 짝 중 거리 합이 작은 쪽
    if d(0, 15) + d(1, 16) <= d(0, 16) + d(1, 15):
        return [True, False]
    return [False, True]


def analyze_hands(hand_result, pose_pts):
    """핸드 트래킹 결과를 좌우가 정해진 HandState 목록으로 변환."""
    hands = []
    for k, is_left in enumerate(assign_sides(hand_result, pose_pts)):
        hw = hand_result.hand_world_landmarks[k]

        def v(i):
            return np.array([hw[i].x, hw[i].y, hw[i].z])

        axes = palm_axes(v(H_WRIST), v(H_MIDDLE_MCP), v(H_INDEX_MCP), v(H_PINKY_MCP), is_left)
        hands.append(HandState(is_left, hand_result.hand_landmarks[k], hw, axes))
    return hands
