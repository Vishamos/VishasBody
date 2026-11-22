"""카메라 기준 골반 중심 위치(루트 위치) 추정. 기준: 명세 01 §5.

월드 좌표(골반 원점, 미터)를 t만큼 옮겨 카메라로 투영했을 때 화면 좌표와 맞도록 t를 최소제곱으로 구한다.
MediaPipe 월드 좌표 축은 카메라와 나란하므로(x 오른쪽, y 아래, z 카메라에서 멀어짐) 모르는 값은 t뿐이다.
점 25개 이하, 미지수 3개라 표준 라이브러리로 충분하다(body_packet.py와 같이 테스트를 어느 PC에서나 돌리기 위해).
"""
import math

DEFAULT_FOV_DEG = 72.0     # 실행 PC 웹캠 RPC-20F 스펙 화각(대각선으로 해석, 명세 01 §5.3)
ROOT_POINTS = range(25)    # 몸 점 0~24. 다리(25~32)는 앉은 자세에서 추측값이라 뺀다(§5.1)
VIS_THRESHOLD = 0.5
MIN_POINTS = 4


def focal_px(width, height, fov_deg):
    """대각선 화각(도) -> 초점거리(픽셀)."""
    return (math.hypot(width, height) / 2) / math.tan(math.radians(fov_deg) / 2)


def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def estimate_root(pose_pts, pose_world, width, height, focal):
    """(tx, ty, tz) 미터, MediaPipe 카메라 축. 계산할 수 없으면 None (§5.2).

    pose_pts: pose_landmarks[0] (화면 좌표 0~1, visibility)
    pose_world: pose_world_landmarks[0] (미터, 골반 원점)
    """
    if not pose_pts or not pose_world:
        return None
    cx, cy = width / 2, height / 2
    m = [[0.0] * 3 for _ in range(3)]   # 정규방정식 A^T A
    b = [0.0] * 3                       # A^T y
    count = 0
    for i in ROOT_POINTS:
        if pose_pts[i].visibility < VIS_THRESHOLD:
            continue
        count += 1
        du = pose_pts[i].x * width - cx
        dv = pose_pts[i].y * height - cy
        w = pose_world[i]
        # f·tx − du·tz = du·Z − f·X,  f·ty − dv·tz = dv·Z − f·Y
        for row, rhs in (((focal, 0.0, -du), du * w.z - focal * w.x),
                         ((0.0, focal, -dv), dv * w.z - focal * w.y)):
            for r in range(3):
                b[r] += row[r] * rhs
                for c in range(3):
                    m[r][c] += row[r] * row[c]
    if count < MIN_POINTS:
        return None

    det = _det3(m)
    if abs(det) < 1e-12:
        return None
    t = []
    for k in range(3):   # 크라메르 공식
        mk = [[b[r] if c == k else m[r][c] for c in range(3)] for r in range(3)]
        t.append(_det3(mk) / det)
    if t[2] <= 0:        # 카메라 뒤
        return None
    return tuple(t)
