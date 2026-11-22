from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision


class PoseTracker:
    """MediaPipe Pose Landmarker (33점) 래퍼. with 문으로 사용."""

    def __init__(self, model_path):
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def detect(self, image, timestamp_ms):
        return self._landmarker.detect_for_video(image, timestamp_ms)

    def close(self):
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class HandTracker:
    """MediaPipe Hand Landmarker (손당 21점, 최대 2손) 래퍼. with 문으로 사용."""

    def __init__(self, model_path):
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)

    def detect(self, image, timestamp_ms):
        return self._landmarker.detect_for_video(image, timestamp_ms)

    def close(self):
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
