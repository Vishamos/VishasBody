import sys
import time
import socket
import struct
import math

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# 출력을 다른 곳으로 넘길 때(! 실행 등)도 한글이 깨지지 않게 UTF-8로 고정
sys.stdout.reconfigure(encoding="utf-8")

MODEL_PATH = "pose_landmarker_full.task"
HAND_MODEL_PATH = "hand_landmarker.task"
UNITY_ADDR = ("127.0.0.1", 9000)   # 유니티가 받는 IP, 포트

DRAW_POSE = list(range(0, 17)) + [23, 24]   # 머리 ~ 손목 + 골반 (손가락은 핸드 트래킹으로 대체)
REQUIRED = (11, 12, 13, 14, 15, 16)  # 이 점들이 보여야 정상: 어깨, 팔꿈치, 손목
PANEL_JOINTS = REQUIRED + (23, 24)   # 화면/요약에 가시성을 표시할 점 (골반은 참고용)
VIS_THRESHOLD = 0.5              # 이 값보다 가시성이 낮으면 "안 보임"으로 판단
POINT_RADIUS = 5                 # 모든 점의 크기 (픽셀)

# 핸드 랜드마크 번호 (21점)
H_WRIST, H_INDEX_MCP, H_MIDDLE_MCP, H_PINKY_MCP = 0, 5, 9, 17
PALM_POINTS = (0, 5, 9, 13, 17)  # 손바닥 중심 계산용: 손목 + 손가락 뿌리 4개
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


def to_screen_x(x, mirror):
    return 1.0 - x if mirror else x


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


def draw_axes(canvas, ox, oy, axes, length_px, mirror):
    s, n, f = axes
    sx = -1 if mirror else 1                       # 좌우 반전 시 x 방향도 반대로
    for axis, color, label in ((s, (0, 0, 255), "X"),
                               (n, (0, 255, 0), "Y"),
                               (f, (255, 0, 0), "Z")):
        end = (int(ox + sx * axis[0] * length_px), int(oy + axis[1] * length_px))
        cv2.arrowedLine(canvas, (ox, oy), end, color, 2, tipLength=0.2)
        cv2.putText(canvas, label, end, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


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


# 화면 버튼 (마우스 클릭으로 토글)
ui = {"mirror": True, "rects": {}}


def on_mouse(event, x, y, flags, param):
    if event != cv2.EVENT_LBUTTONDOWN:
        return
    for name, (x1, y1, x2, y2) in ui["rects"].items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            ui[name] = not ui[name]


def draw_buttons(canvas, w):
    font = cv2.FONT_HERSHEY_SIMPLEX
    for k, (name, label) in enumerate((("mirror", "MIRROR [m]"),)):
        x1, y1 = w - 150, 15 + k * 40
        x2, y2 = w - 15, y1 + 30
        ui["rects"][name] = (x1, y1, x2, y2)
        on = ui[name]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 160, 0) if on else (70, 70, 70), -1)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (255, 255, 255), 1)
        cv2.putText(canvas, f"{label} {'ON' if on else 'OFF'}", (x1 + 6, y1 + 20),
                    font, 0.45, (255, 255, 255), 1)


options = vision.PoseLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=vision.RunningMode.VIDEO,
    num_poses=1,
    min_pose_detection_confidence=0.5,
    min_pose_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)

hand_options = vision.HandLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path=HAND_MODEL_PATH),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=2,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
seq = 0
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
start = time.time()

# 트래킹 점검용 통계
JOINT_NAMES = {11: "L shoulder", 12: "R shoulder", 13: "L elbow",
               14: "R elbow", 15: "L wrist", 16: "R wrist",
               23: "L hip", 24: "R hip"}
WRISTS = (15, 16)
frames = detected = tracked = 0
vis_sum = {i: 0.0 for i in PANEL_JOINTS}
move_sum = {i: 0.0 for i in WRISTS}      # 손목이 한 프레임에 움직인 거리 합 (mm)
move_ema = {i: 0.0 for i in WRISTS}      # 화면 표시용 평균
move_n = 0
prev_wl = None
hand_found = {True: 0, False: 0}         # 손 검출된 프레임 수 (True=왼손)
fps = 0.0
prev_t = time.time()

cv2.namedWindow("pose")
cv2.setMouseCallback("pose", on_mouse)

with vision.PoseLandmarker.create_from_options(options) as landmarker, \
        vision.HandLandmarker.create_from_options(hand_options) as hand_landmarker:
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frames += 1
        now = time.time()
        dt = now - prev_t
        prev_t = now
        if dt > 0:
            fps = 1.0 / dt if fps == 0 else fps * 0.9 + (1.0 / dt) * 0.1

        # 좌우 반전은 화면 표시에만 적용 (유니티로 보내는 좌표는 그대로)
        mirror = ui["mirror"]
        canvas = np.zeros_like(frame)   # 카메라 영상은 표시하지 않음 (검은 화면)
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int((time.time() - start) * 1000)
        result = landmarker.detect_for_video(image, timestamp_ms)
        hand_result = hand_landmarker.detect_for_video(image, timestamp_ms)

        pts = None
        if result.pose_world_landmarks:
            values = []
            for lm in result.pose_world_landmarks[0]:
                values += [lm.x, lm.y, lm.z, lm.visibility]

            seq += 1
            sock.sendto(struct.pack("<I132f", seq, *values), UNITY_ADDR)

            pts = result.pose_landmarks[0]

            def pose_screen(x, y):
                return (int(to_screen_x(x, mirror) * w), int(y * h))

            for i in DRAW_POSE:
                cv2.circle(canvas, pose_screen(pts[i].x, pts[i].y), POINT_RADIUS, POSE_COLORS[i], -1)

            # 몸통 옆 가상 점: 같은 쪽 어깨와 골반의 중간
            for sh, hip in ((11, 23), (12, 24)):
                mx = (pts[sh].x + pts[hip].x) / 2
                my = (pts[sh].y + pts[hip].y) / 2
                cv2.circle(canvas, pose_screen(mx, my), POINT_RADIUS, WHITE, -1)

            # 통계: 가시성, 손목 프레임 간 이동량 (가만히 있을 때 = 떨림)
            wl = result.pose_world_landmarks[0]
            detected += 1
            for i in PANEL_JOINTS:
                vis_sum[i] += pts[i].visibility
            if prev_wl is not None:
                move_n += 1
                for i in WRISTS:
                    d = math.dist((wl[i].x, wl[i].y, wl[i].z),
                                  (prev_wl[i].x, prev_wl[i].y, prev_wl[i].z)) * 1000
                    move_sum[i] += d
                    move_ema[i] = move_ema[i] * 0.9 + d * 0.1
            prev_wl = wl
        else:
            prev_wl = None

        # 핸드 트래킹: 21점 + 손바닥 축
        palm_z = {True: None, False: None}       # 손바닥 축의 z (음수 = 카메라 쪽)
        for k, is_left in enumerate(assign_sides(hand_result, pts)):
            hl = hand_result.hand_landmarks[k]          # 화면 좌표 (0~1)
            hw = hand_result.hand_world_landmarks[k]    # 실제 거리 (미터, 손 중심 기준)
            hand_found[is_left] += 1

            screen = [(int(to_screen_x(p.x, mirror) * w), int(p.y * h)) for p in hl]
            for a, b in HAND_CONNECTIONS:
                cv2.line(canvas, screen[a], screen[b], (90, 90, 90), 1)
            for p, color in zip(screen, HAND_COLORS[is_left]):
                cv2.circle(canvas, p, POINT_RADIUS, color, -1)

            def v(i):
                return np.array([hw[i].x, hw[i].y, hw[i].z])

            axes = palm_axes(v(H_WRIST), v(H_MIDDLE_MCP), v(H_INDEX_MCP), v(H_PINKY_MCP), is_left)
            if axes is None:
                continue
            palm_z[is_left] = axes[1][2]

            # 원점: 손바닥 중심, 축 길이: 손목~중지 뿌리 길이
            ox = int(np.mean([screen[i][0] for i in PALM_POINTS]))
            oy = int(np.mean([screen[i][1] for i in PALM_POINTS]))
            palm_px = math.dist(screen[H_WRIST], screen[H_MIDDLE_MCP])
            draw_axes(canvas, ox, oy, axes, palm_px * 0.8, mirror)

        # 상태 표시
        warning = None
        if not result.pose_world_landmarks:
            warning = "NO POSE DETECTED"
        elif any(result.pose_landmarks[0][i].visibility < VIS_THRESHOLD for i in REQUIRED):
            warning = "UPPER BODY NOT VISIBLE"

        if warning:
            cv2.putText(canvas, warning, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)   # 빨간 글씨
        else:
            cv2.putText(canvas, "TRACKING OK", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)   # 초록 글씨
            tracked += 1

        # 점검 패널: FPS, 필수 관절 가시성, 손목 이동량, 손바닥 방향
        font = cv2.FONT_HERSHEY_SIMPLEX
        y = 70
        cv2.putText(canvas, f"FPS {fps:.1f}   [q] quit", (20, y), font, 0.5, (255, 255, 255), 1)
        if result.pose_landmarks:
            for i in PANEL_JOINTS:
                y += 20
                vis = result.pose_landmarks[0][i].visibility
                color = (0, 255, 0) if vis >= VIS_THRESHOLD else (0, 0, 255)
                cv2.putText(canvas, f"{JOINT_NAMES[i]:<11} vis {vis:.2f}", (20, y), font, 0.5, color, 1)
            for i in WRISTS:
                y += 20
                cv2.putText(canvas, f"{JOINT_NAMES[i]:<11} move {move_ema[i]:5.1f} mm/frame",
                            (20, y), font, 0.5, (255, 255, 0), 1)
        for is_left, name in ((True, "L hand"), (False, "R hand")):
            y += 20
            z = palm_z[is_left]
            if z is None:
                cv2.putText(canvas, f"{name:<11} --", (20, y), font, 0.5, (0, 0, 255), 1)
            else:
                facing = "PALM FRONT" if z < 0 else "PALM BACK"
                cv2.putText(canvas, f"{name:<11} {facing} {z:+.2f}", (20, y), font, 0.5, (0, 255, 0), 1)

        draw_buttons(canvas, w)

        cv2.imshow("pose", canvas)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("m"):
            ui["mirror"] = not ui["mirror"]

cap.release()
cv2.destroyAllWindows()

# 종료 시 요약
elapsed = time.time() - start
print("\n===== 트래킹 요약 =====")
print(f"시간 {elapsed:.1f}s, 프레임 {frames}, 평균 FPS {frames / max(elapsed, 1e-6):.1f}")
if frames:
    print(f"포즈 검출 {detected / frames * 100:.1f}%, TRACKING OK {tracked / frames * 100:.1f}%")
    print(f"손 검출  왼손 {hand_found[True] / frames * 100:.1f}%, 오른손 {hand_found[False] / frames * 100:.1f}%")
if detected:
    for i in PANEL_JOINTS:
        print(f"  {JOINT_NAMES[i]:<11} 평균 가시성 {vis_sum[i] / detected:.2f}")
if move_n:
    for i in WRISTS:
        print(f"  {JOINT_NAMES[i]:<11} 평균 이동 {move_sum[i] / move_n:.1f} mm/frame")
