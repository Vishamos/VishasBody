import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import mediapipe as mp

from body_packet import encode_frame
from hand_math import analyze_hands
from renderer import Renderer
from stats import TrackingStats
from synapse_sender import SynapseSender
from trackers import HandTracker, PoseTracker

BASE_DIR = Path(__file__).resolve().parent       # 어느 폴더에서 실행해도 모델을 찾도록
POSE_MODEL = BASE_DIR / "pose_landmarker_full.task"
HAND_MODEL = BASE_DIR / "hand_landmarker.task"
CONFIG_FILE = BASE_DIR / "config.local.json"   # PC별 서버 주소 (git 제외, config.example.json 참고)


def timed(fn, *args):
    # 작업 스레드 안에서 실행 시간까지 같이 잼
    t = time.perf_counter()
    result = fn(*args)
    return result, time.perf_counter() - t


def load_server_url():
    if not CONFIG_FILE.exists():
        return None
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))["server_url"]


def main():
    # 출력을 다른 곳으로 넘길 때(! 실행 등)도 한글이 깨지지 않게 UTF-8로 고정
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="웹캠 상반신 + 손 트래킹 -> VishaSynapse 송신")
    parser.add_argument("--debug", action="store_true", help="디버그 화면으로 시작 (실행 중 d 키로 전환)")
    parser.add_argument("--camera", type=int, default=0, help="카메라 번호")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    server_url = load_server_url()
    if server_url is None:
        print(f"[송신] {CONFIG_FILE.name}이 없어 보내지 않고 트래킹만 합니다")
    sender = SynapseSender(server_url) if server_url else None
    seq = 0
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
                hands = analyze_hands(hand_result, pose_pts)

                if sender:
                    # seq는 패킷을 만들 때마다 올림: 송신 스레드가 버린 프레임은 받는 쪽에서 건너뜀으로 보임
                    seq += 1
                    pose_world = pose_result.pose_world_landmarks[0] if pose_result.pose_world_landmarks else None
                    sender.send(encode_frame(seq, timestamp_ms, pose_world, hands))

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
        if sender:
            sender.close()
        print(stats.summary())


if __name__ == "__main__":
    main()
