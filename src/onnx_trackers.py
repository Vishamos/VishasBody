"""ONNX Runtime(DirectML GPU) 기반 Pose/Hand 트래커. MediaPipe Tasks(VIDEO 모드)의 결과와 같은 모양을 돌려준다.

모델: tools/convert_onnx.py로 .task에서 변환한 models/*.onnx (신경망 부분만 같고, 나머지 처리는 여기서 재구현)
처리 순서 (MediaPipe 그래프와 같게):
  포즈: 검출(SSD 앵커 2254개 → 가중 NMS) → 회전 영역 크롭 256 → 관절 39점 → 히트맵 보정 → 원본 좌표로 투영
        → 스무딩 → 보조점(33, 34)으로 다음 프레임 영역 추적. 점수가 낮으면 다음 프레임에 다시 검출
  손:   손바닥 검출(앵커 2016개) → 손 영역 크롭 224 → 관절 21점 → 투영 → 스무딩 → 관절로 다음 영역 추적.
        추적 중인 손이 최대 개수보다 적으면 매 프레임 검출을 돌려 새 손을 찾음
그래프 파라미터(영역 배율, 필터 계수 등)는 MediaPipe 공개 그래프 설정 값을 가정했다. .temp/compare_backends.py로 비교 확인.
좌표는 모두 픽셀 단위로 계산하고, 결과에서만 0~1로 정규화한다.
"""
import math
import threading

import cv2
import numpy as np
import onnxruntime as ort

POSE_DETECT_SIZE = 224
POSE_LANDMARK_SIZE = 256
HAND_DETECT_SIZE = 192
HAND_LANDMARK_SIZE = 224
POSE_ANCHOR_STRIDES = (8, 16, 32, 32, 32)   # 28x28x2 + 14x14x2 + 7x7x6 = 2254
HAND_ANCHOR_STRIDES = (8, 16, 16, 16)       # 24x24x2 + 12x12x6 = 2016
NMS_IOU = 0.3
POSE_ROI_SCALE = 1.25
HAND_PALM_ROI = dict(scale=2.6, shift_y=-0.5)    # 손바닥 검출 → 손 영역
HAND_TRACK_ROI = dict(scale=2.0, shift_y=-0.1)   # 손 관절 → 다음 프레임 손 영역
HAND_SAME_IOU = 0.5        # 새로 검출한 손바닥이 추적 중인 손과 이만큼 겹치면 같은 손으로 봄
HAND_DUP_DIST = 0.25       # 두 손의 21점 평균 거리가 손바닥 길이(손목~가운데 뿌리)의 이 비율 미만이면 같은 손
HEATMAP_KERNEL = 7
HEATMAP_MIN_CONF = 0.5
POSE_AUX = (33, 34)        # 영역 계산용 보조점 (골반 중심, 몸 크기 기준점)
HAND_ROI_POINTS = (0, 1, 2, 3, 5, 6, 9, 10, 13, 14, 17, 18)
VISIBILITY_ALPHA = 0.1     # 가시성 저역 필터


class Landmark:
    __slots__ = ("x", "y", "z", "visibility", "presence")

    def __init__(self, x, y, z, visibility=0.0, presence=0.0):
        self.x, self.y, self.z, self.visibility, self.presence = x, y, z, visibility, presence


class Category:
    __slots__ = ("index", "score", "category_name", "display_name")

    def __init__(self, index, score, category_name):
        self.index, self.score, self.category_name, self.display_name = index, score, category_name, ""


class PoseResult:
    def __init__(self, landmarks=None, world=None):
        self.pose_landmarks = [landmarks] if landmarks else []
        self.pose_world_landmarks = [world] if world else []


class HandResult:
    def __init__(self, landmarks, world, handedness):
        self.hand_landmarks = landmarks
        self.hand_world_landmarks = world
        self.handedness = handedness


# ---------- 공통 계산 ----------

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -80.0, 80.0)))   # 큰 음수 입력의 exp 넘침 방지


def normalize_radians(a):
    return a - 2 * math.pi * math.floor((a + math.pi) / (2 * math.pi))


def ssd_anchors(size, strides):
    """앵커 중심 (N, 2), 0~1. 같은 stride가 이어지는 층은 한 격자로 합쳐 칸마다 층 수 x 2개."""
    centers = []
    i = 0
    while i < len(strides):
        j = i
        while j < len(strides) and strides[j] == strides[i]:
            j += 1
        n = math.ceil(size / strides[i])
        grid = (np.stack(np.meshgrid(np.arange(n), np.arange(n)), -1).reshape(-1, 2) + 0.5) / n
        centers.append(np.repeat(grid, 2 * (j - i), axis=0))
        i = j
    return np.concatenate(centers).astype(np.float32)


def roi_points(rect, uv):
    """영역 안 좌표 uv (N, 2; 0~1) → 이미지 픽셀. rect = (cx, cy, w, h, rotation)."""
    cx, cy, w, h, rot = rect
    c, s = math.cos(rot), math.sin(rot)
    u = (uv[:, 0] - 0.5) * w
    v = (uv[:, 1] - 0.5) * h
    return np.stack([cx + u * c - v * s, cy + u * s + v * c], -1)


def crop(rgb, rect, size, border):
    """rect 영역을 size x size로 잘라 0~1 float32 (1, size, size, 3)로."""
    src = roi_points(rect, np.array([[0, 0], [1, 0], [0, 1]], np.float32)).astype(np.float32)
    dst = np.array([[0, 0], [size, 0], [0, size]], np.float32)
    patch = cv2.warpAffine(rgb, cv2.getAffineTransform(src, dst), (size, size),
                           flags=cv2.INTER_LINEAR, borderMode=border)
    return patch[None].astype(np.float32) * (1.0 / 255.0)


def letterbox_rect(width, height):
    # 비율을 유지하고 빈 곳은 0으로 채우는 정사각 영역 (검출 입력용)
    side = max(width, height)
    return (width / 2, height / 2, side, side, 0.0)


def transform_rect(rect, scale, shift_y=0.0):
    """MediaPipe RectTransformation: 회전 방향으로 이동 → 긴 변으로 정사각형 → 배율."""
    cx, cy, w, h, rot = rect
    if shift_y:
        cx += -h * shift_y * math.sin(rot)
        cy += h * shift_y * math.cos(rot)
    side = max(w, h) * scale
    return (cx, cy, side, side, rot)


def rect_from_points(p0, p1, scale):
    """두 점(중심, 크기 기준점)으로 정사각 영역. p0→p1이 위쪽을 향하도록 회전."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    side = 2 * math.hypot(dx, dy) * scale
    rot = normalize_radians(math.pi / 2 - math.atan2(-dy, dx))
    return (float(p0[0]), float(p0[1]), side, side, rot)


def weighted_nms(boxes, scores, kps):
    """가중 NMS. boxes (N, 4: xmin, ymin, xmax, ymax), kps (N, K, 2). 점수 높은 순 [(score, box, kps)]."""
    order = np.argsort(-scores)
    boxes, scores, kps = boxes[order], scores[order], kps[order]
    area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    alive = np.ones(len(scores), bool)
    out = []
    for i in range(len(scores)):
        if not alive[i]:
            continue
        ix = np.clip(np.minimum(boxes[i, 2], boxes[:, 2]) - np.maximum(boxes[i, 0], boxes[:, 0]), 0, None)
        iy = np.clip(np.minimum(boxes[i, 3], boxes[:, 3]) - np.maximum(boxes[i, 1], boxes[:, 1]), 0, None)
        inter = ix * iy
        iou = inter / np.maximum(area[i] + area - inter, 1e-9)
        group = alive & (iou > NMS_IOU)
        group[i] = True
        wsum = scores[group].sum()
        out.append((float(scores[i]),
                    (boxes[group] * scores[group, None]).sum(0) / wsum,
                    (kps[group] * scores[group, None, None]).sum(0) / wsum))
        alive &= ~group
    return out


class OneEuro:
    """MediaPipe OneEuroFilter (배열 단위). value_scale은 값 크기에 맞춘 속도 정규화."""

    def __init__(self, min_cutoff, beta, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self.t = None
        self.raw = self.x = self.dx = None

    @staticmethod
    def _alpha(cutoff, freq):
        # te = 1/freq, tau = 1/(2*pi*cutoff), alpha = 1/(1 + tau/te). cutoff는 숫자나 배열
        return 1.0 / (1.0 + freq / (2 * np.pi * cutoff))

    def __call__(self, t, value, value_scale=1.0):
        if self.t is None:
            self.t, self.raw, self.x, self.dx = t, value, value, np.zeros_like(value)
            return value
        dt = t - self.t
        if dt <= 0:
            return self.x
        freq = 1.0 / dt
        dvalue = (value - self.raw) * value_scale * freq
        a_d = self._alpha(self.d_cutoff, freq)
        self.dx = a_d * dvalue + (1 - a_d) * self.dx
        cutoff = self.min_cutoff + self.beta * np.abs(self.dx)
        a = self._alpha(cutoff, freq)
        self.x = a * value + (1 - a) * self.x
        self.t, self.raw = t, value
        return self.x


class LandmarkSmoother:
    """이미지 좌표 랜드마크 스무딩. 픽셀 (x, y, z) 값을 물체 크기로 정규화한 속도로 거름."""

    def __init__(self, min_cutoff, beta, scale_by_object=True):
        self.f = OneEuro(min_cutoff, beta)
        self.scale_by_object = scale_by_object

    def reset(self):
        self.f.reset()

    def __call__(self, t, pts):
        scale = 1.0
        if self.scale_by_object:
            size = ((pts[:, 0].max() - pts[:, 0].min()) + (pts[:, 1].max() - pts[:, 1].min())) / 2
            scale = 1.0 / max(size, 1e-6)
        return self.f(t, pts, scale)


# DirectML은 서로 다른 세션이라도 두 스레드가 동시에 실행하면 실패한다
# (80004005 "지정되지 않은 오류", main.py의 포즈·손 병렬 실행에서 발생). GPU 실행만 한 번에 하나씩.
_GPU_LOCK = threading.Lock()


class Model:
    """ONNX 세션 + 입력 이름. GPU면 실행을 공용 잠금으로 직렬화한다 (전후 처리는 계속 병렬)."""

    def __init__(self, path, use_gpu):
        so = ort.SessionOptions()
        providers = ["CPUExecutionProvider"]
        if use_gpu:
            so.enable_mem_pattern = False                       # DirectML 권장 설정
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(path), so, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.lock = _GPU_LOCK if use_gpu else None

    @property
    def providers(self):
        return self.session.get_providers()

    def run(self, x):
        if self.lock is None:
            return self.session.run(None, {self.input_name: x})
        with self.lock:
            return self.session.run(None, {self.input_name: x})


def detect_ssd(model, rgb, size, strides, num_kp, threshold, value_range, anchors):
    """검출 모델 실행 → NMS 후 [(score, box 픽셀(xmin, ymin, xmax, ymax), keypoints 픽셀 (K, 2))]."""
    h, w = rgb.shape[:2]
    rect = letterbox_rect(w, h)
    x = crop(rgb, rect, size, cv2.BORDER_CONSTANT)
    if value_range == (-1, 1):
        x = x * 2.0 - 1.0
    raw_boxes, raw_scores = model.run(x)
    scores = sigmoid(np.clip(raw_scores[0, :, 0], -100, 100))
    keep = scores >= threshold
    if not keep.any():
        return []
    b = raw_boxes[0, keep] / size
    a = anchors[keep]
    cx, cy = b[:, 0] + a[:, 0], b[:, 1] + a[:, 1]
    bw, bh = b[:, 2], b[:, 3]
    kps = b[:, 4:4 + 2 * num_kp].reshape(-1, num_kp, 2) + a[:, None, :]
    # 박스 모서리와 키포인트를 이미지 픽셀로 (레터박스 영역은 회전이 없어 모서리 투영으로 충분)
    corners = roi_points(rect, np.concatenate([np.stack([cx - bw / 2, cy - bh / 2], -1),
                                               np.stack([cx + bw / 2, cy + bh / 2], -1)]))
    n = len(cx)
    boxes = np.concatenate([corners[:n], corners[n:]], -1)
    kps = roi_points(rect, kps.reshape(-1, 2)).reshape(n, num_kp, 2)
    return weighted_nms(boxes, scores[keep], kps)


# ---------- 포즈 ----------

class OnnxPoseTracker:
    """MediaPipe Pose Landmarker(VIDEO, num_poses=1)와 같은 결과 모양. with 문으로 사용."""

    def __init__(self, detector_path, landmark_path, use_gpu=True, min_detection=0.5, min_presence=0.5):
        self.det = Model(detector_path, use_gpu)
        self.lmk = Model(landmark_path, use_gpu)
        self.anchors = ssd_anchors(POSE_DETECT_SIZE, POSE_ANCHOR_STRIDES)
        self.min_detection, self.min_presence = min_detection, min_presence
        self.rect = None
        self.smooth_lm = LandmarkSmoother(0.05, 80.0)
        self.smooth_aux = LandmarkSmoother(0.01, 10.0)
        self.smooth_world = LandmarkSmoother(0.1, 40.0, scale_by_object=False)
        self.visibility = None

    @property
    def providers(self):
        return self.lmk.providers

    def _reset(self):
        self.rect = None
        self.visibility = None
        for f in (self.smooth_lm, self.smooth_aux, self.smooth_world):
            f.reset()

    def detect(self, image, timestamp_ms):
        rgb = image.numpy_view() if hasattr(image, "numpy_view") else image
        h, w = rgb.shape[:2]
        t = timestamp_ms / 1000.0
        if self.rect is None:
            found = detect_ssd(self.det, rgb, POSE_DETECT_SIZE, POSE_ANCHOR_STRIDES, 4,
                               self.min_detection, (-1, 1), self.anchors)
            if not found:
                return PoseResult()
            kps = found[0][2]
            self.rect = rect_from_points(kps[0], kps[1], POSE_ROI_SCALE)

        rect = self.rect
        lm, flag, _seg, heat, world = self.lmk.run(crop(rgb, rect, POSE_LANDMARK_SIZE, cv2.BORDER_REPLICATE))
        if float(flag[0, 0]) < self.min_presence:   # 출력에 이미 sigmoid가 적용돼 있음
            self._reset()
            return PoseResult()

        lm = lm.reshape(-1, 5)
        uv = lm[:, :2] / POSE_LANDMARK_SIZE
        refine_with_heatmap(uv, heat[0])
        pix = roi_points(rect, uv)
        z = lm[:, 2] / POSE_LANDMARK_SIZE * rect[2]          # 픽셀 단위 (영역 폭 기준)
        visibility = sigmoid(lm[:, 3])
        presence = sigmoid(lm[:, 4])

        pts = np.concatenate([pix, z[:, None]], -1)
        body = self.smooth_lm(t, pts[:33])
        aux = self.smooth_aux(t, pts[list(POSE_AUX)])
        self.rect = rect_from_points(aux[0], aux[1], POSE_ROI_SCALE)

        c, s = math.cos(rect[4]), math.sin(rect[4])
        wl = world.reshape(-1, 3)[:33]
        wl = np.stack([wl[:, 0] * c - wl[:, 1] * s, wl[:, 0] * s + wl[:, 1] * c, wl[:, 2]], -1)
        wl = self.smooth_world(t, wl)

        vis = visibility[:33]
        self.visibility = vis if self.visibility is None else \
            VISIBILITY_ALPHA * vis + (1 - VISIBILITY_ALPHA) * self.visibility
        vis = self.visibility

        landmarks = [Landmark(float(p[0] / w), float(p[1] / h), float(p[2] / w), float(vis[i]), float(presence[i]))
                     for i, p in enumerate(body)]
        worlds = [Landmark(float(p[0]), float(p[1]), float(p[2]), float(vis[i]), float(presence[i]))
                  for i, p in enumerate(wl)]
        return PoseResult(landmarks, worlds)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def refine_with_heatmap(uv, heatmap):
    """MediaPipe RefineLandmarksFromHeatmap: 히트맵 7x7 창의 sigmoid 가중 평균으로 x, y를 고침 (uv 제자리 수정)."""
    hh, hw, n = heatmap.shape
    half = (HEATMAP_KERNEL - 1) // 2
    for i in range(min(n, len(uv))):
        col, row = int(uv[i, 0] * hw), int(uv[i, 1] * hh)
        if not (0 <= col < hw and 0 <= row < hh):
            continue
        r0, r1 = max(0, row - half), min(hh, row + half + 1)
        c0, c1 = max(0, col - half), min(hw, col + half + 1)
        conf = sigmoid(heatmap[r0:r1, c0:c1, i])
        total = conf.sum()
        if conf.max() < HEATMAP_MIN_CONF or total <= 0:
            continue
        rows, cols = np.mgrid[r0:r1, c0:c1]
        uv[i, 0] = (cols * conf).sum() / total / hw
        uv[i, 1] = (rows * conf).sum() / total / hh


# ---------- 손 ----------

def hand_rect_from_landmarks(pix):
    """MediaPipe HandLandmarksToRect: 손목 → 손가락 뿌리 방향으로 회전한 외접 사각형 (픽셀)."""
    p = pix[list(HAND_ROI_POINTS)]
    x0, y0 = pix[0]
    x1 = ((pix[5, 0] + pix[13, 0]) / 2 + pix[9, 0]) / 2
    y1 = ((pix[5, 1] + pix[13, 1]) / 2 + pix[9, 1]) / 2
    rot = normalize_radians(math.pi / 2 - math.atan2(-(y1 - y0), x1 - x0))
    center = (p.min(0) + p.max(0)) / 2
    c, s = math.cos(-rot), math.sin(-rot)
    d = p - center
    r = np.stack([d[:, 0] * c - d[:, 1] * s, d[:, 0] * s + d[:, 1] * c], -1)
    lo, hi = r.min(0), r.max(0)
    mid = (lo + hi) / 2
    c2, s2 = math.cos(rot), math.sin(rot)
    cx = mid[0] * c2 - mid[1] * s2 + center[0]
    cy = mid[0] * s2 + mid[1] * c2 + center[1]
    return (float(cx), float(cy), float(hi[0] - lo[0]), float(hi[1] - lo[1]), rot)


def rect_iou(a, b):
    """회전을 무시한 두 영역의 IoU (MediaPipe AssociationNormRect와 같음)."""
    ax0, ay0, ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx0, by0, bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def same_hand(a, b):
    """두 손 관절(픽셀, (21, 2 이상))이 같은 손인지. 겹쳐 있는 서로 다른 손은 관절 위치가 달라 걸리지 않는다."""
    palm = max(np.linalg.norm(a[9, :2] - a[0, :2]), np.linalg.norm(b[9, :2] - b[0, :2]), 1e-6)
    return float(np.linalg.norm(a[:, :2] - b[:, :2], axis=1).mean()) < HAND_DUP_DIST * palm


class _HandTrack:
    def __init__(self, rect):
        self.rect = rect
        self.smooth_lm = LandmarkSmoother(0.05, 80.0)
        self.smooth_world = LandmarkSmoother(0.1, 40.0, scale_by_object=False)


class OnnxHandTracker:
    """MediaPipe Hand Landmarker(VIDEO)와 같은 결과 모양. with 문으로 사용."""

    # 손 좌우 출력(sigmoid 값)이 0.5보다 크면 이 라벨 (MediaPipe와 비교해 확인한 값)
    HIGH_LABEL, LOW_LABEL = "Right", "Left"

    def __init__(self, detector_path, landmark_path, use_gpu=True, num_hands=2,
                 min_detection=0.5, min_presence=0.5):
        self.det = Model(detector_path, use_gpu)
        self.lmk = Model(landmark_path, use_gpu)
        self.anchors = ssd_anchors(HAND_DETECT_SIZE, HAND_ANCHOR_STRIDES)
        self.num_hands, self.min_detection, self.min_presence = num_hands, min_detection, min_presence
        self.tracks = []

    @property
    def providers(self):
        return self.lmk.providers

    def detect(self, image, timestamp_ms):
        rgb = image.numpy_view() if hasattr(image, "numpy_view") else image
        h, w = rgb.shape[:2]
        t = timestamp_ms / 1000.0
        tracks = list(self.tracks)
        if len(tracks) < self.num_hands:
            for score, box, kps in detect_ssd(self.det, rgb, HAND_DETECT_SIZE, HAND_ANCHOR_STRIDES, 7,
                                              self.min_detection, (0, 1), self.anchors):
                if len(tracks) >= self.num_hands:
                    break
                bx, by = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                rot = normalize_radians(math.pi / 2 - math.atan2(-(kps[2, 1] - kps[0, 1]), kps[2, 0] - kps[0, 0]))
                rect = transform_rect((bx, by, box[2] - box[0], box[3] - box[1], rot), **HAND_PALM_ROI)
                if all(rect_iou(rect, tr.rect) <= HAND_SAME_IOU for tr in tracks):
                    tracks.append(_HandTrack(rect))

        found = []   # (추적, 존재 점수, 픽셀 점 (21, 3), 월드 점 (21, 3), 좌우 출력)
        for tr in tracks:
            rect = tr.rect
            lm, presence, side, world = self.lmk.run(crop(rgb, rect, HAND_LANDMARK_SIZE, cv2.BORDER_REPLICATE))
            if float(presence[0, 0]) < self.min_presence:
                continue
            lm = lm.reshape(21, 3)
            pix = roi_points(rect, lm[:, :2] / HAND_LANDMARK_SIZE)
            z = lm[:, 2] / HAND_LANDMARK_SIZE * rect[2]
            pts = tr.smooth_lm(t, np.concatenate([pix, z[:, None]], -1))
            c, s = math.cos(rect[4]), math.sin(rect[4])
            wl = world.reshape(21, 3)
            wl = tr.smooth_world(t, np.stack([wl[:, 0] * c - wl[:, 1] * s, wl[:, 0] * s + wl[:, 1] * c, wl[:, 2]], -1))
            tr.rect = transform_rect(hand_rect_from_landmarks(pts[:, :2]), **HAND_TRACK_ROI)
            found.append((tr, float(presence[0, 0]), pts, wl, float(side[0, 0])))

        # 두 추적이 같은 손으로 모이면(손이 겹칠 때) 존재 점수가 높은 쪽만 남김.
        # 남은 추적이 최대 개수보다 적어지므로 다음 프레임에 손바닥 검출이 다시 돌아 다른 손을 찾는다.
        keep = []
        for item in sorted(found, key=lambda f: -f[1]):
            if all(not same_hand(item[2], k[2]) for k in keep):
                keep.append(item)
        found = [f for f in found if any(f is k for k in keep)]   # 원래 추적 순서 유지

        self.tracks = [f[0] for f in found]
        landmarks = [[Landmark(float(p[0] / w), float(p[1] / h), float(p[2] / w)) for p in f[2]] for f in found]
        worlds = [[Landmark(float(p[0]), float(p[1]), float(p[2])) for p in f[3]] for f in found]
        handedness = [[Category(1, f[4], self.HIGH_LABEL) if f[4] > 0.5 else Category(0, 1 - f[4], self.LOW_LABEL)]
                      for f in found]
        return HandResult(landmarks, worlds, handedness)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
