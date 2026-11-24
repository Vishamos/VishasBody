# VishasBody: 버추얼 방송용 웹캠 바디 트래커

> 마지막 갱신: 2026-11-24
> 새 대화를 시작할 때 이 파일 하나로 현재 상태를 파악할 수 있게 정리한 문서입니다.

---

## 1. 목표와 범위

전체 시스템 목표: 웹캠 1대(상반신·팔·손) + iPhone(얼굴 표정)으로 PC의 Unity 캐릭터를 움직여 방송 송출

**이 프로젝트(Python 트래커)의 책임은 딱 두 가지:**
1. 웹캠 영상에서 상반신·손을 **트래킹**
2. 그 결과를 **VishaSynapse 중계 서버에 연결해서 송신**

받는 쪽(Vishamos·Unity)과 iPhone 쪽은 이 프로젝트 범위 밖입니다. Body 데이터 형식은 이 저장소가 정하고(`docs/protocol/README.md`), 서버 접속·등록 규약은 VishaSynapse를 따릅니다(12번).

## 2. 전체 구조

```
┌──────────── 이 프로젝트 ────────────┐
[웹캠] → 트래킹 (Pose + Hand, 병렬) → 송신 ──WebSocket──→ [VishaSynapse 중계 서버 :4000] ──→ Vishamos(캐릭터)
└─────────────────────────────────────┘
```

| 항목 | 상태 |
|---|---|
| 트래킹 (몸 + 손) | ✅ 동작, 약 30 FPS. 추론은 MediaPipe(CPU, 기본) 또는 ONNX(GPU, 선택) |
| 루트 위치 (카메라 기준 골반 위치) | ✅ 동작, 실행 PC 보정 완료 (화각 60°) |
| 송신 | ✅ 실제 서버 등록·송신 확인 (2026-11-22). 패킷 버전 2, 1,092바이트 |
| 프로토콜 | ✅ 확정: `docs/protocol/README.md`(받는 쪽용), `docs/tech_spec/01_body_packet.md`(근거·구현 현황) |

## 3. 환경

- Windows 11, Python **3.12** (프로젝트 기준 버전). 패키지 버전은 `requirements.txt`
- 실행 PC(웹캠 있음): CPU 8스레드, GPU GTX 1060 6GB, 웹캠 RPC-20F (지금 설정 1024×576 16:9, 30 FPS)
- 개발 PC는 카메라가 없어 단위 테스트까지만 합니다. PC별 경로·Python은 각 PC의 `CLAUDE.local.md`(git 제외)에 적습니다.
- 저장소: GitHub `Vishamos/VishasBody` (`main` 브랜치, 공개, MIT)

## 4. 실행 방법

**`BodyTracker.bat`을 더블클릭**하면 됩니다(MediaPipe, CPU). GPU로 돌리려면 **`BodyTrackerGPU.bat`**(= `BodyTracker.bat --backend onnx`). 처음 한 번만 아래를 준비합니다.

1. 모델 파일을 `models` 폴더에 내려받습니다 (Google MediaPipe 공식 모델, Apache 2.0, git 제외).
   ```powershell
   Invoke-WebRequest https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task -OutFile models\pose_landmarker_full.task
   Invoke-WebRequest https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task -OutFile models\hand_landmarker.task
   ```
2. (GPU 실행 시만) ONNX 모델 `models/*.onnx`를 준비합니다(git 제외). 이미 변환한 PC에서 복사하거나 `tools/convert_onnx.py`로 변환합니다. 변환에는 TensorFlow가 든 별도 가상환경이 필요합니다(`docs/work/onnx_gpu_backend.md` 8번).
3. 서버 주소 파일을 만듭니다 (git 제외).
   ```powershell
   Copy-Item config\config.example.json config\config.local.json   # 열어서 server_url을 서버 PC의 LAN IP로 고침
   ```
   - 없으면 보내지 않고 트래킹만 합니다. 서버가 꺼져 있으면 2초마다 다시 접속합니다.
   - `camera_fov_deg`: 웹캠 대각선 화각(도, 없으면 72). 루트 위치 거리 계산에 씁니다. 보정 방법은 명세 01 §5.6. **받는 해상도마다 값이 다릅니다.** 실행 PC(RPC-20F): 640×480(4:3, 기본) → **60**, 1024×576(16:9, 960×540 요청) → **74**
   - `camera_width`, `camera_height`: 카메라에 요청할 해상도(없으면 카메라 기본값, 실행 PC는 640x480). 드라이버가 가까운 모드를 고르므로 실제 크기는 실행 시 `[루트] 해상도` 줄에서 확인. 실행 PC(RPC-20F)는 960x540을 요청하면 16:9 1024x576 30 FPS(4:3보다 좌우 약 1.27배 넓음)를 받고, 1024x576을 그대로 요청하면 15 FPS가 됨. **해상도를 바꾸면 `camera_fov_deg`를 다시 보정**

- 패키지는 `BodyTracker.bat`이 빠진 것이 있을 때 `requirements.txt`대로 자동 설치합니다. `.venv`가 있으면 그 Python, 없으면 `py -3.12`를 씁니다. 직접 설치하려면 `py -3.12 -m pip install -r requirements.txt`.
- 개발 PC도 `.venv`(3.12)를 만들어 같은 버전으로 맞춥니다. 웹캠 실행은 실행 PC에서 합니다.
- 옵션: `--debug`(디버그 화면으로 시작), `--camera 1`(카메라 번호), `--backend onnx`(GPU)

| 조작 | 기능 |
|---|---|
| `d` / DEBUG 버튼 | 디버그 화면 ON/OFF |
| `m` / MIRROR 버튼 | 좌우 반전 (화면 표시에만 적용, 전송 좌표는 그대로) |
| `q` / QUIT 버튼 / 창 닫기(X) | 종료 → 터미널에 트래킹 요약 출력 |

- **카메라 영상은 어느 모드에서도 표시하지 않음** (방송 송출 방지, 의도된 설계)

## 5. 파일 구성

| 위치 | 역할 |
|---|---|
| `BodyTracker.bat` | 실행 파일. `.venv`가 있으면 그 Python, 없으면 `py -3.12`. 빠진 패키지 자동 설치. 인자는 `main.py`로 넘김 |
| `BodyTrackerGPU.bat` | `BodyTracker.bat --backend onnx` |
| `requirements.txt` | 패키지 버전 고정 (mediapipe, opencv-python, websockets, onnxruntime-directml) |
| `config/` | `config.example.json`(예시), `config.local.json`(PC별 서버 주소·화각, git 제외) |
| `models/` | MediaPipe 모델 `*.task`(4번 명령으로 내려받음), ONNX 모델 `*.onnx`(변환). 모두 git 제외 |
| `src/main.py` | 진입점. 카메라 루프, Pose/Hand **병렬 추론**(몸은 손을 기다리지 않음), 백엔드 선택, 각 부품 연결 |
| `src/trackers.py` | `PoseTracker`, `HandTracker` (MediaPipe VIDEO 모드 래퍼, CPU) |
| `src/onnx_trackers.py` | `OnnxPoseTracker`, `OnnxHandTracker` (ONNX Runtime DirectML, GPU). MediaPipe의 전후 처리를 다시 구현, 결과 모양이 MediaPipe와 같음 |
| `src/hand_math.py` | `HandState`, 손바닥 축 계산, 왼손/오른손 판정 |
| `src/root_position.py` | 루트 위치(카메라 기준 골반 위치) 계산 (명세 01 §5) |
| `src/body_packet.py` | 한 프레임을 1,092바이트 패킷으로 (Unity 좌표 변환, 손바닥 쿼터니언) |
| `src/synapse_sender.py` | `SynapseSender` (송신 스레드: 접속 → 등록 → 최신 패킷 송신, 끊기면 재접속) |
| `src/stats.py` | `TrackingStats` (FPS, 가시성, 이동량, 단계별 처리 시간, 종료 요약) |
| `src/renderer.py` | `Renderer` (색 정의, 디버그/간단 화면, 버튼·키 입력) |
| `src/legacy/pose_test.py` | 분리 전 단일 파일 버전. **비교용으로만 보관**, 더 이상 수정 안 함 |
| `tools/convert_onnx.py` | `.task` → `models/*.onnx` 변환 (별도 TensorFlow 환경) |
| `test/` | 단위 테스트 (`python -B -m unittest discover -s test`) |
| `docs/` | 기술 명세, Body 프로토콜, 작업 목록 |

## 6. 송신 데이터

- WebSocket 바이너리 1,092바이트, 프레임마다 1개: 몸 33점 + 양손 21점·손바닥 회전 + 루트 위치. Unity 좌표로 변환해서 보냅니다.
- 바이트 배치와 받는 쪽 규칙: [`docs/protocol/README.md`](docs/protocol/README.md). 무엇을 왜 그렇게 정했는지: [`docs/tech_spec/01_body_packet.md`](docs/tech_spec/01_body_packet.md)

## 7. 주요 결정과 이유

| 결정 | 이유 |
|---|---|
| 웹캠 1대 (2대 구성 폐기) | 단순화 |
| 상반신만 사용 | 방송 자세 (앉아서 책상 앞) |
| **Hand Landmarker 추가** | Pose 모델의 손 점(검지·새끼)으로는 손 뒤집기(앞/뒤)가 판별되지 않았음. Hand 21점으로는 `PALM FRONT/BACK` 정상 판별 확인 |
| **Pose와 Hand 병렬 실행**, 몸은 손을 기다리지 않음 | 순차 실행 시 약 20 FPS. 병렬로 30 근처, 손이 보이면 손 추론이 프레임을 붙잡아 25로 떨어져 손은 최신 완료 결과를 씀 (명세 01 §1.1) |
| **GPU는 선택(ONNX 백엔드), 기본은 CPU** | Windows용 MediaPipe는 GPU가 빌드에서 빠져 있음 (`GPU processing is disabled in build flags`). 모델을 ONNX로 바꿔 DirectML로 돌리면 포즈 23 → 10ms, 손 28∼31 → 13∼14ms. 다만 GTX 1060은 Unity + OBS도 쓰므로, 함께 켰을 때 측정 전까지 기본값은 CPU |
| **목표: 30 FPS 유지** | 프레임 예산 약 33ms. 새 기능은 이 안에 들어가는지 먼저 확인 |
| 몸통은 **어깨선 위주**로 계산하는 게 적합 (받는 쪽 참고) | 앉은 자세에서 골반 가시성 **0.00** (책상에 가려 MediaPipe가 추측한 값) |
| 트래커는 **트래킹 + 연결·송신만** 담당 | 역할 분리. 송신 방식은 송신 계층에서만 바꿈 |
| **자체 바이너리 프로토콜** (타 프로그램 호환 고려 안 함) | 내 프로그램끼리만 통신. 가볍고 정확하게. VMC/OSC 같은 표준은 쓰지 않음 |

## 8. 최근 측정값 (실행 PC, 실제 웹캠)

| 백엔드 | FPS | 처리 시간 | 비고 |
|---|---|---|---|
| MediaPipe (CPU) | 29.9∼31.0 (손 있을 때 28.4) | 손 있을 때 pose 25∼26 / hand 27∼28 / infer 25∼27 / draw 3.7ms | 2026-11-22∼24, Unity 실행 중 |
| ONNX (GPU) | 28.5 | pose 13.7 / hand 17.1 / infer 13.9 / draw 3.9ms | 2026-11-24, 640×480, GPU가 한가할 때. Unity + OBS와 함께는 미측정 |
| ONNX (GPU), 1024×576 | 29.4 | pose 14.3 / hand 18.5 / infer 14.5 / draw 3.5ms | 2026-11-24. 손을 쓰는 실행에서 손 검출 74∼80%(640×480과 비슷) |

- 가시성(앉은 자세): 어깨 1.00 / 팔꿈치·손목 0.4∼0.9(팔을 내리면 화면 밖이라 낮음) / 골반 0.00
- 정지 떨림(월드 좌표, 스무딩 없는 모델 출력 기준 비교): MediaPipe 18.0, ONNX 8.7mm/프레임. 자세한 내용은 `docs/work/onnx_gpu_backend.md` 5번

## 9. 디버그 화면 표시 규칙

- 점 크기 통일: 반지름 5px (`renderer.py`의 `POINT_RADIUS`)
- 색: 몸통 흰색에서 시작해 말단으로 갈수록 진해짐
  - 어깨·골반·몸통 가상 점: 흰색
  - 왼팔 → 왼손 손끝: 파랑 그라데이션 / 오른팔 → 오른손 손끝: 빨강 그라데이션
  - 머리: 초록 (귀·입 < 코 < 눈)
- 몸통 가상 점: 같은 쪽 어깨와 골반의 중간
- 손바닥 축: 원점 = 손바닥 중심, X 빨강(옆) / Y 초록(손바닥 방향) / Z 파랑(손가락 방향)
- 가시성 0.5 미만 관절은 패널에 빨간 글씨. 점은 가시성과 관계없이 그림(낮으면 모델이 추측한 위치)

## 10. 남은 작업

[`docs/work/worklist.md`](docs/work/worklist.md)에서 관리합니다.

## 11. 참고: 비슷한 방송용 프로그램 (트래킹 품질 비교용)

- **Warudo**: Unity 기반 3D VTuber 앱, 웹캠 MediaPipe + iPhone 얼굴 조합 지원
- **XR Animator**: MediaPipe 웹캠 트래커 (오픈소스)
- **VSeeFace**, **VMagicMirror**, **Webcam Motion Capture**
- iPhone 얼굴 전송 앱: iFacialMocap, Facemotion3d, Waidayo
- 이 프로젝트는 이 프로그램들과 호환하지 않음 (자체 바이너리 프로토콜)

## 12. 중계 서버: VishaSynapse (별도 저장소)

- GitHub `Vishamos/VishaSynapse`. 방송용 기기·프로그램을 WebSocket으로 잇는 중계 서버
- 이 트래커는 시그니처 **31(Body)**로 등록하고 Vishamos(11)로 바이너리를 보냄
- 접속·등록·메시지 규약: VishaSynapse `docs/protocol/README.md` (이 프로젝트에서는 읽기만 함)
- Body 데이터 형식: 이 저장소 `docs/protocol/README.md`
