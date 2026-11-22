import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import mediapipe as mp

from hand_math import analyze_hands
from renderer import Renderer
from stats import TrackingStats
from trackers import HandTracker, PoseTracker
from udp_sender import UdpSender

BASE_DIR = Path(__file__).resolve().parent       # 어느 폴더에서 실행해도 모델을 찾도록
POSE_MODEL = BASE_DIR / "pose_landmarker_full.task"
HAND_MODEL = BASE_DIR / "hand_landmarker.task"
UNITY_ADDR = ("127.0.0.1", 9000)   # 유니티가 받는 IP, 포트


def timed(fn, *args):
    # 작업 스레드 안에서 실행 시간까지 같이 잼
    t = time.perf_counter()
    result = fn(*args)
    return result, time.perf_counter() - t


def main():
    # 출력을 다른 곳으로 넘길 때(! 실행 등)도 한글이 깨지지 않게 UTF-8로 고정
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="웹캠 상반신 + 손 트래킹 -> 유니티 UDP 전송")
    parser.add_argument("--debug", action="store_true", help="디버그 화면으로 시작 (실행 중 d 키로 전환)")
    parser.add_argument("--camera", type=int, default=0, help="카메라 번호")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    sender = UdpSender(UNITY_ADDR)
    stats = TrackingStats()
    renderer = Renderer("capture", debug=args.debug)
    start = time.time()

    try:
        with PoseTracker(POSE_MODEL) as pose_tracker, HandTracker(HAND_MODEL) as hand_tracker, \
                ThreadPoolExecutor(max_workers=2) as pool:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                stats.begin_frame()

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((time.time() - start) * 1000)

                # 추론: 같은 사진을 Pose와 Hand가 동시에 분석
                t0 = time.perf_counter()
                pose_job = pool.submit(timed, pose_tracker.detect, image, timestamp_ms)
                hand_job = pool.submit(timed, hand_tracker.detect, image, timestamp_ms)
                pose_result, pose_sec = pose_job.result()
                hand_result, hand_sec = hand_job.result()
                stats.add_time("pose", pose_sec)
                stats.add_time("hand", hand_sec)
                stats.add_time("infer", time.perf_counter() - t0)   # 둘 다 끝날 때까지 실제 걸린 시간

                pose_pts = pose_result.pose_landmarks[0] if pose_result.pose_landmarks else None
                if pose_result.pose_world_landmarks:
                    sender.send_pose(pose_result.pose_world_landmarks[0])

                hands = analyze_hands(hand_result, pose_pts)
                stats.update(pose_result, hands)

                # 화면 (그리기 + 창 갱신 + 키 입력 대기 시간 포함)
                t3 = time.perf_counter()
                renderer.render(frame.shape, pose_result, hands, stats)
                key = cv2.waitKey(1) & 0xFF
                stats.add_time("draw", time.perf_counter() - t3)
                if not renderer.handle_key(key):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        sender.close()
        print(stats.summary())


if __name__ == "__main__":
    main()
