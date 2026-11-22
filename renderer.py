import math

import cv2
import numpy as np
from mediapipe.tasks.python import vision

from hand_math import H_WRIST, H_MIDDLE_MCP, PALM_POINTS
from stats import JOINT_NAMES, PANEL_JOINTS, WRISTS, TIMING_KEYS

DRAW_POSE = list(range(0, 17)) + [23, 24]   # 머리 ~ 손목 + 골반 (손가락은 핸드 트래킹으로 대체)
VIS_THRESHOLD = 0.5              # 이 값보다 가시성이 낮으면 빨간 글씨
POINT_RADIUS = 5                 # 모든 점의 크기 (픽셀)
FONT = cv2.FONT_HERSHEY_SIMPLEX
HAND_CONNECTIONS = [(c.start, c.end) for c in vision.HandLandmarksConnections.HAND_CONNECTIONS]

# 색 (BGR): 몸통 흰색에서 시작해 말단으로 갈수록 각 부위 색이 진해짐
WHITE = (255, 255, 255)
LEFT_COLOR = (255, 90, 30)       # 왼팔/왼손: 파랑
RIGHT_COLOR = (40, 40, 255)      # 오른팔/오른손: 빨강
HEAD_COLOR = (60, 230, 60)       # 머리: 초록

# 팔 단계: 어깨 0 -> 팔꿈치 1 -> 손목 2 -> 손가락 마디 3~6 (끝마디 6)
ARM_LEVEL = {11: 0, 12: 0, 13: 1, 14: 1, 15: 2, 16: 2}
ARM_MAX_LEVEL = 6
# 머리 진하기: 귀·입 < 코 < 눈
HEAD_T = {0: 0.8, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0,
          7: 0.6, 8: 0.6, 9: 0.6, 10: 0.6}


def blend(color, t):
    # t=0 흰색, t=1 원래 색
    return tuple(int(255 * (1 - t) + c * t) for c in color)


def pose_color(i):
    if i in HEAD_T:
        return blend(HEAD_COLOR, HEAD_T[i])
    if i in ARM_LEVEL:
        side = LEFT_COLOR if i % 2 == 1 else RIGHT_COLOR   # 홀수 = 왼쪽
        return blend(side, ARM_LEVEL[i] / ARM_MAX_LEVEL)
    return WHITE                                          # 골반, 몸통 가상 점


def hand_color(k, is_left):
    # 손목(0) = 2단계, 각 손가락 1~4번째 마디 = 3~6단계
    level = 2 if k == 0 else 3 + (k - 1) % 4
    return blend(LEFT_COLOR if is_left else RIGHT_COLOR, level / ARM_MAX_LEVEL)


POSE_COLORS = {i: pose_color(i) for i in DRAW_POSE}       # 한 번만 계산
HAND_COLORS = {side: [hand_color(k, side) for k in range(21)] for side in (True, False)}

BUTTONS = (("debug", "DEBUG [d]"), ("mirror", "MIRROR [m]"), ("quit", "QUIT [q]"))
TOGGLES = ("debug", "mirror")    # ON/OFF 버튼 (quit은 누르면 바로 종료)


class Renderer:
    """미리보기 창. 디버그 ON = 관절/손/축/점검 패널, OFF = 상태 표시만.
    카메라 영상은 어느 모드에서도 표시하지 않음 (방송 송출 방지)."""

    def __init__(self, window_name="capture", debug=False, mirror=True):
        self.window = window_name
        self.state = {"debug": debug, "mirror": mirror}   # mirror는 화면 표시에만 적용
        self._rects = {}
        self._quit_requested = False
        cv2.namedWindow(self.window)
        cv2.setMouseCallback(self.window, self._on_mouse)

    # ---------- 입력 ----------

    def _on_mouse(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        for name, (x1, y1, x2, y2) in self._rects.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                if name == "quit":
                    self._quit_requested = True
                else:
                    self.state[name] = not self.state[name]

    def _window_open(self):
        # 창의 닫기(X) 버튼을 누르면 보이지 않는 상태(0 이하)가 됨
        try:
            return cv2.getWindowProperty(self.window, cv2.WND_PROP_VISIBLE) >= 1
        except cv2.error:
            return False

    def handle_key(self, key):
        """False를 돌려주면 종료. (q 키, QUIT 버튼, 창 닫기 버튼)"""
        if key == ord("q") or self._quit_requested or not self._window_open():
            return False
        if key == ord("d"):
            self.state["debug"] = not self.state["debug"]
        if key == ord("m"):
            self.state["mirror"] = not self.state["mirror"]
        return True

    # ---------- 그리기 ----------

    def render(self, frame_shape, pose_result, hands, stats):
        h, w = frame_shape[:2]
        canvas = np.zeros((h, w, 3), np.uint8)   # 항상 검은 배경

        self._draw_status(canvas, pose_result)
        if self.state["debug"]:
            if pose_result.pose_landmarks:
                self._draw_pose(canvas, pose_result.pose_landmarks[0], w, h)
            for hand in hands:
                self._draw_hand(canvas, hand, w, h)
            self._draw_panel(canvas, pose_result, hands, stats)
        else:
            self._draw_compact(canvas, hands, stats)
        self._draw_buttons(canvas, w)

        cv2.imshow(self.window, canvas)

    def _to_screen(self, x, y, w, h):
        sx = 1.0 - x if self.state["mirror"] else x
        return (int(sx * w), int(y * h))

    def _draw_status(self, canvas, pose_result):
        if pose_result.pose_world_landmarks:
            cv2.putText(canvas, "TRACKING OK", (20, 40), FONT, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(canvas, "NO POSE DETECTED", (20, 40), FONT, 1.0, (0, 0, 255), 2)

    def _draw_pose(self, canvas, pts, w, h):
        for i in DRAW_POSE:
            cv2.circle(canvas, self._to_screen(pts[i].x, pts[i].y, w, h),
                       POINT_RADIUS, POSE_COLORS[i], -1)

        # 몸통 옆 가상 점: 같은 쪽 어깨와 골반의 중간
        for sh, hip in ((11, 23), (12, 24)):
            mx = (pts[sh].x + pts[hip].x) / 2
            my = (pts[sh].y + pts[hip].y) / 2
            cv2.circle(canvas, self._to_screen(mx, my, w, h), POINT_RADIUS, WHITE, -1)

    def _draw_hand(self, canvas, hand, w, h):
        screen = [self._to_screen(p.x, p.y, w, h) for p in hand.landmarks]
        for a, b in HAND_CONNECTIONS:
            cv2.line(canvas, screen[a], screen[b], (90, 90, 90), 1)
        for p, color in zip(screen, HAND_COLORS[hand.is_left]):
            cv2.circle(canvas, p, POINT_RADIUS, color, -1)

        if hand.axes is None:
            return
        # 원점: 손바닥 중심, 축 길이: 손목~중지 뿌리 길이
        ox = int(np.mean([screen[i][0] for i in PALM_POINTS]))
        oy = int(np.mean([screen[i][1] for i in PALM_POINTS]))
        length_px = math.dist(screen[H_WRIST], screen[H_MIDDLE_MCP]) * 0.8
        self._draw_axes(canvas, ox, oy, hand.axes, length_px)

    def _draw_axes(self, canvas, ox, oy, axes, length_px):
        s, n, f = axes
        sx = -1 if self.state["mirror"] else 1   # 좌우 반전 시 x 방향도 반대로
        for axis, color, label in ((s, (0, 0, 255), "X"),
                                   (n, (0, 255, 0), "Y"),
                                   (f, (255, 0, 0), "Z")):
            end = (int(ox + sx * axis[0] * length_px), int(oy + axis[1] * length_px))
            cv2.arrowedLine(canvas, (ox, oy), end, color, 2, tipLength=0.2)
            cv2.putText(canvas, label, end, FONT, 0.5, color, 1)

    def _timing_text(self, stats):
        return "  ".join(f"{k} {stats.time_ema[k]:.1f}ms" for k in TIMING_KEYS)

    def _draw_panel(self, canvas, pose_result, hands, stats):
        # 점검 패널: FPS, 처리 시간, 가시성, 손목 이동량, 손바닥 방향
        y = 70
        cv2.putText(canvas, f"FPS {stats.fps:.1f}", (20, y), FONT, 0.5, WHITE, 1)
        y += 20
        cv2.putText(canvas, self._timing_text(stats), (20, y), FONT, 0.5, (200, 200, 200), 1)
        if pose_result.pose_landmarks:
            pts = pose_result.pose_landmarks[0]
            for i in PANEL_JOINTS:
                y += 20
                vis = pts[i].visibility
                color = (0, 255, 0) if vis >= VIS_THRESHOLD else (0, 0, 255)
                cv2.putText(canvas, f"{JOINT_NAMES[i]:<11} vis {vis:.2f}", (20, y), FONT, 0.5, color, 1)
            for i in WRISTS:
                y += 20
                cv2.putText(canvas, f"{JOINT_NAMES[i]:<11} move {stats.move_ema[i]:5.1f} mm/frame",
                            (20, y), FONT, 0.5, (255, 255, 0), 1)

        palm_z = {hand.is_left: hand.palm_z for hand in hands}
        for is_left, name in ((True, "L hand"), (False, "R hand")):
            y += 20
            z = palm_z.get(is_left)
            if z is None:
                cv2.putText(canvas, f"{name:<11} --", (20, y), FONT, 0.5, (0, 0, 255), 1)
            else:
                facing = "PALM FRONT" if z < 0 else "PALM BACK"
                cv2.putText(canvas, f"{name:<11} {facing} {z:+.2f}", (20, y), FONT, 0.5, (0, 255, 0), 1)

    def _draw_compact(self, canvas, hands, stats):
        # 디버그 OFF: 상태만 간단히
        found = {hand.is_left for hand in hands}
        hand_text = f"L hand {'OK' if True in found else '--'}   R hand {'OK' if False in found else '--'}"
        cv2.putText(canvas, f"FPS {stats.fps:.1f}", (20, 70), FONT, 0.5, WHITE, 1)
        cv2.putText(canvas, self._timing_text(stats), (20, 90), FONT, 0.5, (200, 200, 200), 1)
        cv2.putText(canvas, hand_text, (20, 110), FONT, 0.5, WHITE, 1)

    def _draw_buttons(self, canvas, w):
        for k, (name, label) in enumerate(BUTTONS):
            x1, y1 = w - 150, 15 + k * 40
            x2, y2 = w - 15, y1 + 30
            self._rects[name] = (x1, y1, x2, y2)
            if name in TOGGLES:
                on = self.state[name]
                fill = (0, 160, 0) if on else (70, 70, 70)   # 켜짐 초록, 꺼짐 회색
                text = f"{label} {'ON' if on else 'OFF'}"
            else:
                fill = (40, 40, 170)                         # 종료: 빨강
                text = label
            cv2.rectangle(canvas, (x1, y1), (x2, y2), fill, -1)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), WHITE, 1)
            cv2.putText(canvas, text, (x1 + 6, y1 + 20), FONT, 0.45, WHITE, 1)
