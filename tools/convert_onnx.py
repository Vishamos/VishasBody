"""MediaPipe .task 모델을 ONNX로 변환해 models/에 저장한다 (src/onnx_trackers.py, --backend onnx용).

필요한 것:
- models/의 .task: pose_landmarker_full.task, hand_landmarker.task (README '실행 방법'으로 내려받음)
  pose_landmarker_heavy.task는 선택. 없는 .task는 건너뛴다.
- TensorFlow + tf2onnx가 있는 별도 가상환경 (무거워서 트래커 실행 환경에는 넣지 않음). 예:
    py -3.12 -m venv C:/Users/<사용자>/.rea_gpu      (경로가 길면 TensorFlow 설치가 Windows 경로 길이 제한에 걸림)
    C:/Users/<사용자>/.rea_gpu/Scripts/python -m pip install tensorflow tf2onnx onnxruntime
실행 (프로젝트 폴더에서):
    C:/Users/<사용자>/.rea_gpu/Scripts/python -I tools/convert_onnx.py

- .task는 ZIP이고 안에 .tflite가 들어 있다.
- pose_detector.tflite는 희소(sparse) 가중치 + DENSIFY 연산을 써서 tf2onnx가 변환하지 못한다.
  TFLite로 DENSIFY 결과(일반 가중치)를 미리 계산해 상수로 넣고 DENSIFY 연산을 지운 뒤 변환한다.
  이때 XNNPACK을 끄지 않으면 DENSIFY 결과가 계산되지 않은 값으로 읽힌다.
- 변환 후 원본 TFLite와 출력을 비교해 상대 오차를 출력한다.
"""
import io
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import onnxruntime as ort
import tensorflow as tf
from tensorflow.lite.python import schema_py_generated as sch
from tensorflow.lite.tools import flatbuffer_utils as fu

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
# (task 파일, 안의 tflite, 저장할 onnx 이름)
TARGETS = [
    ("pose_landmarker_full.task", "pose_detector.tflite", "pose_detector.onnx"),
    ("pose_landmarker_full.task", "pose_landmarks_detector.tflite", "pose_landmarks_full.onnx"),
    ("pose_landmarker_heavy.task", "pose_landmarks_detector.tflite", "pose_landmarks_heavy.onnx"),
    ("hand_landmarker.task", "hand_detector.tflite", "hand_detector.onnx"),
    ("hand_landmarker.task", "hand_landmarks_detector.tflite", "hand_landmarks.onnx"),
]
NO_DELEGATE = tf.lite.experimental.OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES


def densify(src, dst):
    """DENSIFY 연산을 미리 계산한 상수로 바꾼 tflite를 dst에 쓴다. 바꾼 개수를 돌려준다."""
    it = tf.lite.Interpreter(model_path=str(src), experimental_preserve_all_tensors=True,
                             experimental_op_resolver_type=NO_DELEGATE)
    it.allocate_tensors()
    inp = it.get_input_details()[0]
    it.set_tensor(inp["index"], np.zeros(inp["shape"], inp["dtype"]))
    it.invoke()
    m = fu.read_model(str(src))
    g = m.subgraphs[0]
    codes = [max(c.builtinCode, c.deprecatedBuiltinCode) for c in m.operatorCodes]
    keep, n = [], 0
    for op in g.operators:
        if codes[op.opcodeIndex] != sch.BuiltinOperator.DENSIFY:
            keep.append(op)
            continue
        out = op.outputs[0]
        buf = sch.BufferT()
        buf.data = np.frombuffer(it.get_tensor(out).tobytes(), np.uint8)
        m.buffers.append(buf)
        g.tensors[out].buffer = len(m.buffers) - 1
        sparse = g.tensors[op.inputs[0]]   # 안 쓰이게 된 희소 텐서: 남겨 두면 tf2onnx가 읽다가 실패
        sparse.buffer = 0
        sparse.sparsity = None
        n += 1
    g.operators = keep
    fu.write_model(m, str(dst))
    return n


def max_rel_error(tflite_path, onnx_path):
    rng = np.random.default_rng(0)
    it = tf.lite.Interpreter(model_path=str(tflite_path))
    it.allocate_tensors()
    inp = it.get_input_details()[0]
    x = rng.random(inp["shape"], dtype=np.float32)
    it.set_tensor(inp["index"], x)
    it.invoke()
    ref = {d["name"]: it.get_tensor(d["index"]) for d in it.get_output_details()}
    s = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    out = dict(zip([o.name.split(":")[0] for o in s.get_outputs()], s.run(None, {s.get_inputs()[0].name: x})))
    return max(float(np.abs(out[k.split(":")[0]] - v).max() / (np.ptp(v) or 1.0)) for k, v in ref.items())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for task, inner, onnx_name in TARGETS:
            if not (MODELS / task).exists():
                print(f"[변환] models/{task} 없음 -> {onnx_name} 건너뜀")
                continue
            with zipfile.ZipFile(io.BytesIO((MODELS / task).read_bytes())) as z:
                original = tmp / f"{task}_{inner}"
                original.write_bytes(z.read(inner))
            to_convert = original
            if inner == "pose_detector.tflite":
                to_convert = tmp / f"{task}_dense_{inner}"
                print(f"[변환] {inner}: DENSIFY {densify(original, to_convert)}개 제거")
            dst = MODELS / onnx_name
            r = subprocess.run([sys.executable, "-I", "-m", "tf2onnx.convert", "--tflite", str(to_convert),
                                "--output", str(dst), "--opset", "17"], capture_output=True, text=True)
            if r.returncode != 0:
                print(r.stderr[-2000:])
                sys.exit(f"[변환] {onnx_name} 실패")
            print(f"[변환] {task}/{inner} -> models/{onnx_name}  원본 대비 최대 상대 오차 {max_rel_error(original, dst):.1e}")


if __name__ == "__main__":
    main()
