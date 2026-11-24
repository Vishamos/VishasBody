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
from root_position import DEFAULT_FOV_DEG, estimate_root, focal_px
from stats import TrackingStats
from synapse_sender import SynapseSender
from trackers import HandTracker, PoseTracker

ROOT_DIR = Path(__file__).resolve().parent.parent   # 프로젝트 폴더. 어느 폴더에서 실행해도 찾도록
POSE_MODEL = ROOT_DIR / "models" / "pose_landmarker_full.task"
HAND_MODEL = ROOT_DIR / "models" / "hand_landmarker.task"
# --backend onnx: tools/convert_onnx.py로 변환한 모델, ONNX Runtime DirectML(GPU)로 실행
ONNX_MODELS = {name: ROOT_DIR / "models" / f"{name}.onnx"
               for name in ("pose_detector", "pose_landmarks_full", "hand_detector", "hand_landmarks")}
CONFIG_FILE = ROOT_DIR / "config" / "config.local.json"   # PC별 서버 주소·카메라 화각 (git 제외, config.example.json 참고)


def timed(fn, *args):
    # 작업 스레드 안에서 실행 시간까지 같이 잼
    t = time.perf_counter()
    result = fn(*args)
    return result, time.perf_counter() - t


def load_config():
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def main():
    # 출력을 다른 곳으로 넘길 때(! 실행 등)도 한글이 깨지지 않게 UTF-8로 고정
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="웹캠 상반신 + 손 트래킹 -> VishaSynapse 송신")
    parser.add_argument("--debug", action="store_true", help="디버그 화면으로 시작 (실행 중 d 키로 전환)")
    parser.add_argument("--camera", type=int, default=0, help="카메라 번호")
    parser.add_argument("--backend", choices=("mediapipe", "onnx"), default="mediapipe",
                        help="추론 방식: mediapipe(CPU, 기본) / onnx(ONNX Runtime DirectML GPU)")
    args = parser.parse_args()

    missing = [p.name for p in (POSE_MODEL, HAND_MODEL) if not p.exists()]
    if missing:
        print(f"[모델] models 폴더에 {', '.join(missing)}이 없습니다. README '실행 방법'의 명령으로 내려받으세요")
        return
    if args.backend == "onnx":
        missing = [p.name for p in ONNX_MODELS.values() if not p.exists()]
        if missing:
            print(f"[모델] models 폴더에 {', '.join(missing)}이 없습니다. tools/convert_onnx.py로 변환하세요")
            return
        from onnx_trackers import OnnxHandTracker, OnnxPoseTracker
        pose_tracker = OnnxPoseTracker(ONNX_MODELS["pose_detector"], ONNX_MODELS["pose_landmarks_full"])
        hand_tracker = OnnxHandTracker(ONNX_MODELS["hand_detector"], ONNX_MODELS["hand_landmarks"])
        print(f"[추론] ONNX Runtime: {pose_tracker.providers[0]}")
    else:
        pose_tracker = PoseTracker(POSE_MODEL)
        hand_tracker = HandTracker(HAND_MODEL)
        print("[추론] MediaPipe (CPU)")

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    config = load_config()
    server_url = config["server_url"] if config else None
    fov_deg = config.get("camera_fov_deg", DEFAULT_FOV_DEG)
    focal = None            # 첫 프레임 해상도로 한 번 계산 (명세 01 §5.3)
    if server_url is None:
        print("[송신] config 폴더에 config.local.json이 없어 보내지 않고 트래킹만 합니다 "
              "(config.example.json을 복사해 server_url을 고치면 송신)")
    sender = SynapseSender(server_url) if server_url else None
    seq = 0
    stats = TrackingStats()
    renderer = Renderer("capture", debug=args.debug)
    start = time.time()
    hand_job = None         # 실행 중인 손 추론 (C#의 Task)
    hand_pose_pts = None    # 손 추론에 넘긴 프레임의 포즈 (좌우 판정용)
    hands = []              # 최신 완료 손 결과

    try:
        with pose_tracker, hand_tracker, ThreadPoolExecutor(max_workers=2) as pool:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                stats.begin_frame()
                height, width = frame.shape[:2]
                if focal is None:
                    focal = focal_px(width, height, fov_deg)
                    print(f"[루트] 해상도 {width}x{height}, 대각선 화각 {fov_deg}°")

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((time.time() - start) * 1000)

                # 추론: Pose는 매 프레임 기다리고, Hand는 기다리지 않음 (명세 01 §1.1)
                # 손 추론이 끝나 있으면 결과를 받고 이 프레임으로 다시 시작, 아니면 직전 손 결과를 그대로 씀
                t0 = time.perf_counter()
                pose_job = pool.submit(timed, pose_tracker.detect, image, timestamp_ms)
                hand_result = None
                if hand_job is not None and hand_job.done():
                    hand_result, hand_sec = hand_job.result()
                    stats.add_time("hand", hand_sec)
                    hand_job = None
                hand_started = hand_job is None
                if hand_started:
                    hand_job = pool.submit(timed, hand_tracker.detect, image, timestamp_ms)
                pose_result, pose_sec = pose_job.result()
                stats.add_time("pose", pose_sec)
                stats.add_time("infer", time.perf_counter() - t0)   # 프레임이 추론을 기다린 실제 시간

                pose_pts = pose_result.pose_landmarks[0] if pose_result.pose_landmarks else None
                if hand_result is not None:
                    hands = analyze_hands(hand_result, hand_pose_pts)
                if hand_started:
                    hand_pose_pts = pose_pts
                pose_world = pose_result.pose_world_landmarks[0] if pose_result.pose_world_landmarks else None
                root = estimate_root(pose_pts, pose_world, width, height, focal)

                if sender:
                    # seq는 패킷을 만들 때마다 올림: 송신 스레드가 버린 프레임은 받는 쪽에서 건너뜀으로 보임
                    seq += 1
                    sender.send(encode_frame(seq, timestamp_ms, pose_world, hands, root))

                stats.update(pose_result, hands)

                # 화면 (그리기 + 창 갱신 + 키 입력 대기 시간 포함)
                t3 = time.perf_counter()
                renderer.render(frame.shape, pose_result, hands, stats, root)
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
