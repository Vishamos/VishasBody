import math
import time

JOINT_NAMES = {11: "L shoulder", 12: "R shoulder", 13: "L elbow",
               14: "R elbow", 15: "L wrist", 16: "R wrist",
               23: "L hip", 24: "R hip"}
PANEL_JOINTS = (11, 12, 13, 14, 15, 16, 23, 24)   # 가시성을 기록할 점
WRISTS = (15, 16)
# 단계별 처리 시간 (ms). pose와 hand는 동시에 돌고, infer는 둘 다 끝날 때까지의 실제 시간
TIMING_KEYS = ("pose", "hand", "infer", "draw")


def _ema(old, new, a=0.1):
    # 화면 표시용 평균 (최근 값에 가중치)
    return new if old == 0 else old * (1 - a) + new * a


class TrackingStats:
    """트래킹 점검용 통계: FPS, 가시성, 손목 이동량, 손 검출, 단계별 시간."""

    def __init__(self):
        self.start = time.time()
        self.frames = 0
        self.detected = 0
        self.fps = 0.0
        self.vis_sum = {i: 0.0 for i in PANEL_JOINTS}
        self.move_sum = {i: 0.0 for i in WRISTS}   # 손목이 한 프레임에 움직인 거리 합 (mm)
        self.move_ema = {i: 0.0 for i in WRISTS}
        self.move_n = 0
        self.hand_found = {True: 0, False: 0}      # 손 검출된 프레임 수 (True=왼손)
        self.time_sum = {k: 0.0 for k in TIMING_KEYS}
        self.time_ema = {k: 0.0 for k in TIMING_KEYS}
        self._prev_t = time.time()
        self._prev_wl = None

    def begin_frame(self):
        self.frames += 1
        now = time.time()
        dt = now - self._prev_t
        self._prev_t = now
        if dt > 0:
            self.fps = _ema(self.fps, 1.0 / dt)

    def add_time(self, key, seconds):
        ms = seconds * 1000
        self.time_sum[key] += ms
        self.time_ema[key] = _ema(self.time_ema[key], ms)

    def update(self, pose_result, hands):
        for hand in hands:
            self.hand_found[hand.is_left] += 1

        if not pose_result.pose_world_landmarks:
            self._prev_wl = None
            return

        pts = pose_result.pose_landmarks[0]
        wl = pose_result.pose_world_landmarks[0]
        self.detected += 1
        for i in PANEL_JOINTS:
            self.vis_sum[i] += pts[i].visibility

        # 손목 프레임 간 이동량 (가만히 있을 때 = 떨림)
        if self._prev_wl is not None:
            self.move_n += 1
            for i in WRISTS:
                d = math.dist((wl[i].x, wl[i].y, wl[i].z),
                              (self._prev_wl[i].x, self._prev_wl[i].y, self._prev_wl[i].z)) * 1000
                self.move_sum[i] += d
                self.move_ema[i] = _ema(self.move_ema[i], d)
        self._prev_wl = wl

    def summary(self):
        elapsed = time.time() - self.start
        lines = ["", "===== 트래킹 요약 =====",
                 f"시간 {elapsed:.1f}s, 프레임 {self.frames}, 평균 FPS {self.frames / max(elapsed, 1e-6):.1f}"]
        if self.frames:
            lines.append(f"포즈 검출 {self.detected / self.frames * 100:.1f}%")
            lines.append(f"손 검출  왼손 {self.hand_found[True] / self.frames * 100:.1f}%, "
                         f"오른손 {self.hand_found[False] / self.frames * 100:.1f}%")
            lines.append("평균 처리 시간  " + ", ".join(
                f"{k} {self.time_sum[k] / self.frames:.1f}ms" for k in TIMING_KEYS))
        if self.detected:
            for i in PANEL_JOINTS:
                lines.append(f"  {JOINT_NAMES[i]:<11} 평균 가시성 {self.vis_sum[i] / self.detected:.2f}")
        if self.move_n:
            for i in WRISTS:
                lines.append(f"  {JOINT_NAMES[i]:<11} 평균 이동 {self.move_sum[i] / self.move_n:.1f} mm/frame")
        return "\n".join(lines)
