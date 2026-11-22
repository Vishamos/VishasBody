# VishasBody: 버추얼 방송용 웹캠 바디 트래커

> 마지막 갱신: 2026-11-22
> 새 대화를 시작할 때 이 파일 하나로 현재 상태를 파악할 수 있게 정리한 문서입니다.

---

## 1. 목표와 범위

전체 시스템 목표: 웹캠 1대(상반신·팔·손) + iPhone(얼굴 표정)으로 PC의 Unity 캐릭터를 움직여 방송 송출

**이 프로젝트(Python 트래커)의 책임은 딱 두 가지:**
1. 웹캠 영상에서 상반신·손을 **트래킹**
2. 그 결과를 **서버(수신 측)에 연결해서 송신**

수신 측(Unity 등)과 iPhone 쪽은 이 프로젝트 범위 밖입니다. 인증과 전송 방식은 **VishaSynapse `Protocol/` 폴더의 프로토콜 문서**(추후 작성)에 맞춰 구현합니다.

## 2. 전체 구조

```
┌──────────── 이 프로젝트 ────────────┐
[웹캠] → 트래킹 (Pose + Hand, 병렬) → 송신 ──(프로토콜 문서에 따름)──→ [VishaSynapse 중앙 서버 :4000] ──→ VISHAMOS(캐릭터) 등
└─────────────────────────────────────┘
```

- 중앙 서버는 기존 프로젝트 **VishaSynapse** (WebSocket, 기기 종류별 메시지 전달 허브). 자세한 내용은 **12번** 참고

| 항목 | 상태 |
|---|---|
| 트래킹 (몸 + 손) | ✅ 동작, 30 FPS |
| 송신 | 🔶 구현 완료, 실제 서버 연동 확인 전 (WebSocket → VishaSynapse, 몸 + 양손 1,080바이트) |
| 프로토콜 | 📝 VishaSynapse 접속 규약 확정, Body 데이터 형식 확정 (`docs/protocol/README.md`, `docs/tech_spec/01_body_packet.md`) |

## 3. 환경

- Windows 11, PowerShell, Python 3.12.10, mediapipe 1.2.0, opencv-python 5.0.0.93, websockets 17.4
- CPU 8스레드, GPU GTX 1060 6GB
- (전체 시스템용, 이 프로젝트에서는 미사용) iPhone SE (A12 이상 → TrueDepth 없이 ARKit 얼굴 추적 가능), Mac + Xcode 보유
- 저장소: GitHub `Vishamos/VishasBody` (`main` 브랜치, 공개, MIT)

## 4. 실행 방법

모델 파일은 저장소에 없습니다. 처음 한 번 이 폴더에 내려받습니다 (Google MediaPipe 공식 모델, Apache 2.0).

```powershell
Invoke-WebRequest https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task -OutFile pose_landmarker_full.task
Invoke-WebRequest https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task -OutFile hand_landmarker.task
```

패키지는 `BodyTracker.bat`이 빠진 것이 있을 때 `requirements.txt`대로 자동 설치합니다(실행할 Python과 같은 Python에 설치). 직접 설치하려면 `py -3.12 -m pip install -r requirements.txt`.

서버 주소는 처음 한 번 준비합니다.

```powershell
Copy-Item config.example.json config.local.json   # 열어서 server_url을 서버 PC의 LAN IP로 고침 (git 제외)
```

- `config.local.json`이 없으면 보내지 않고 트래킹만 합니다. 서버가 꺼져 있으면 2초마다 다시 접속합니다.

```powershell
python main.py            # 기본: 간단 상태 화면
python main.py --debug    # 디버그 화면으로 시작
```

| 조작 | 기능 |
|---|---|
| `d` / DEBUG 버튼 | 디버그 화면 ON/OFF |
| `m` / MIRROR 버튼 | 좌우 반전 (화면 표시에만 적용, 전송 좌표는 그대로) |
| `q` / QUIT 버튼 / 창 닫기(X) | 종료 → 터미널에 트래킹 요약 출력 |

- Claude Code에서 `! python main.py`로 실행하면 종료 요약이 대화에 바로 남음
- **카메라 영상은 어느 모드에서도 표시하지 않음** (방송 송출 방지, 의도된 설계)

## 5. 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | 진입점. 카메라 루프, Pose/Hand **병렬 추론**, 각 부품 연결 |
| `trackers.py` | `PoseTracker`, `HandTracker` (MediaPipe VIDEO 모드 래퍼) |
| `hand_math.py` | `HandState`, 손바닥 축 계산, 왼손/오른손 판정 |
| `body_packet.py` | 한 프레임을 1,080바이트 패킷으로 (Unity 좌표 변환, 손바닥 쿼터니언). 형식은 `docs/protocol/README.md` |
| `synapse_sender.py` | `SynapseSender` (송신 스레드: 접속 → 등록 → 최신 패킷 송신, 끊기면 재접속) |
| `BodyTracker.bat` | 실행 파일. `.venv`가 있으면 그 Python, 없으면 `py -3.12`. 빠진 패키지 자동 설치 |
| `requirements.txt` | 패키지 버전 고정 (mediapipe, opencv-python, websockets) |
| `config.example.json` | 서버 주소 설정 예시. `config.local.json`으로 복사해 씀 |
| `stats.py` | `TrackingStats` (FPS, 가시성, 이동량, 단계별 처리 시간, 종료 요약) |
| `renderer.py` | `Renderer` (색 정의, 디버그/간단 화면, 버튼·키 입력) |
| `pose_test.py` | 분리 전 단일 파일 버전. **비교용으로만 보관**, 더 이상 수정 안 함 |
| `*.task` | 모델: `pose_landmarker_full`, `hand_landmarker`. git 제외, 4번의 명령으로 내려받음 |
| `__pycache__/` | Python이 자동 생성하는 캐시. 정상, 신경 쓰지 않아도 됨 |

## 6. 송신 데이터

### 현재 형식
- WebSocket 바이너리 1,080바이트, 프레임마다. 배치와 받는 쪽 규칙은 `docs/protocol/README.md`, 근거는 `docs/tech_spec/01_body_packet.md`

### 트래커가 내보낼 수 있는 데이터 (프로토콜 설계 시 참고)
| 데이터 | 내용 | 현재 전송 |
|---|---|---|
| 포즈 | `pose_world_landmarks` 33점 × [x, y, z, visibility]. 단위 미터, 엉덩이 중심이 원점 | ✅ |
| 손 | 손마다 21점 (화면 좌표 + 실제 거리), 왼손/오른손 구분, 손바닥 축 (X 옆 / Y 손바닥 / Z 손가락) | ❌ |
| 상태 | 포즈 검출 여부, 손 검출 여부, 관절별 가시성 | ❌ |

- 좌표계: MediaPipe 기준 = **오른손 좌표계** (x 오른쪽, **y 아래**, **z 카메라에서 멀어지는 쪽**)
- 왼쪽/오른쪽은 **사람 기준** (MediaPipe 홀수 번호 = 왼쪽)

### ⚠️ Unity(왼손 좌표계)로 변환 규칙
- 손잡이 방향이 다르면 **축을 홀수 개** 뒤집어야 함
- ~~y·z 부호 반전~~ (두 축 = 거울상이 되어 왼팔 데이터가 캐릭터 오른쪽에 찍힘, **틀린 규칙**)
- **올바른 변환** (캐릭터가 Unity +z를 바라볼 때): 위치 `(x, y, z) → (-x, -y, -z)`, 쿼터니언은 **그대로** (세 축 모두 반전하면 회전값 불변)
- 거울 모드가 필요하면: x를 한 번 더 반전 **+ 왼쪽/오른쪽 이름을 서로 바꿈** (좌표만 뒤집으면 팔이 엇갈림)
- 아직 Unity에서 실제 검증은 안 함 → 첫 연결 때 한 손만 들어서 확인

## 7. 주요 결정과 이유

| 결정 | 이유 |
|---|---|
| 웹캠 1대 (2대 구성 폐기) | 단순화 |
| 상반신만 사용 | 방송 자세 (앉아서 책상 앞) |
| **Hand Landmarker 추가** | Pose 모델의 손 점(검지·새끼)으로는 손 뒤집기(앞/뒤)가 판별되지 않았음. Hand 21점으로는 `PALM FRONT/BACK` 정상 판별 확인 |
| **Pose와 Hand 병렬 실행** (스레드 2개) | 순차 실행 시 약 20 FPS → 병렬 시 30 FPS. MediaPipe가 C++ 추론 중 GIL을 풀어서 실제로 동시에 돎 (벤치마크 ×1.90) |
| **GPU 사용 안 함** | Windows용 MediaPipe는 GPU가 빌드에서 빠져 있음 (`GPU processing is disabled in build flags`). GTX 1060은 Unity + OBS가 써야 함 |
| **목표: 30 FPS 유지** | 프레임 예산 약 33ms. 새 기능은 이 안에 들어가는지 먼저 확인 |
| `UPPER BODY NOT VISIBLE` 경고 삭제 | 의도대로 동작하지 않았음. 상태는 `TRACKING OK` / `NO POSE DETECTED`만 |
| 몸통은 **어깨선 위주**로 계산하는 게 적합 (수신 측 참고) | 앉은 자세에서 골반 가시성 **0.00** (책상에 가려 MediaPipe가 추측한 값) → 골반은 고정하거나 약하게만 반영 |
| 트래커는 **트래킹 + 연결·송신만** 담당 | 역할 분리. 인증·전송 방식은 프로토콜 문서로 정하고, 송신 부분만 교체하면 되게 함 |
| **자체 바이너리 프로토콜** (타 프로그램 호환 고려 안 함) | 내 프로그램끼리만 통신. 가볍고 정확하게. VMC/OSC 같은 표준은 쓰지 않음 |

## 8. 최근 측정값 (병렬화 전, 실제 웹캠)

```
평균 FPS 19.8 (병렬화 후 30 근처로 체감 확인)
처리 시간  pose 22.1ms, hand 22.4ms, draw 3.7ms
손 검출    왼손 50.7%, 오른손 46.1%   ← 움직이며 측정, 팔이 화면 밖으로 자주 나감
가시성     어깨 1.00 / 팔꿈치 0.56~0.62 / 손목 0.56~0.70 / 골반 0.00
```

- 손목 이동량(mm/frame)은 움직이면서 잰 값이라 **떨림 수치가 아님**. 정지 테스트는 아직 안 함

## 9. 디버그 화면 표시 규칙

- 점 크기 통일: 반지름 5px (`renderer.py`의 `POINT_RADIUS`)
- 색: 몸통 흰색에서 시작해 말단으로 갈수록 진해짐
  - 어깨·골반·몸통 가상 점: 흰색
  - 왼팔 → 왼손 손끝: 파랑 그라데이션 / 오른팔 → 오른손 손끝: 빨강 그라데이션
  - 머리: 초록 (귀·입 < 코 < 눈)
- 몸통 가상 점: 같은 쪽 어깨와 골반의 중간
- 손바닥 축: 원점 = 손바닥 중심, X 빨강(옆) / Y 초록(손바닥 방향) / Z 파랑(손가락 방향)

## 10. 다음 할 일과 설계 메모

남은 작업은 [`docs/work/worklist.md`](docs/work/worklist.md)에서 관리합니다. 아래 메모는 Body 패킷 명세(worklist Spec-1)의 초안입니다.

### 프로토콜 설계 시 참고 메모
- **보낼 데이터**: 위치 + 회전이면 수신 측 처리에 충분. 단 위치만으로는 뼈 축 비틀림(roll)을 알 수 없으므로 **손바닥 회전(쿼터니언)은 필수** (아래팔 비틀림, 손 뒤집기)
- **같이 보내야 할 것**: 신뢰도 (관절별 가시성 또는 부위별 검출 여부. 트래킹을 놓쳤을 때 마지막 자세 유지나 기본 자세 복귀에 필요) + 시간 정보 (오래된 패킷 버리기, 스무딩의 dt 계산)
- **문서에 정할 것**: ① 좌표계 (트래커가 Unity 좌표로 변환해서 보내는 쪽 추천) ② 단위·원점 (미터, 엉덩이 중심) ③ 쿼터니언 성분 순서 ④ 신뢰도 단위 ⑤ 시퀀스 번호와 타임스탬프 중 선택
- 수신 측은 절대 위치가 아니라 **방향**으로 본 회전을 계산 (사람과 캐릭터의 체형이 다르므로)
- TCP/HTTP 인증 후 UDP로 보낼 때, **UDP 패킷 자체는 인증으로 보호되지 않음**. 필요하면 인증 때 받은 세션 토큰을 패킷마다 넣거나 HMAC 서명을 붙여야 함
- 같은 PC / 집 공유기 안이면 보안 위협은 낮음 → 핸드셰이크의 실질적 가치는 **서버 찾기, 버전·형식 협상, 연결 상태 표시**

### 바이너리 패킷 설계 메모 (계산값)
- **프레임당 패킷 1개**에 포즈 + 양손을 모두 담는 구성 추천: 같은 순간의 데이터가 항상 같이 도착하고, 수신 측 처리가 단순함
- 크기 예시 (float32, 리틀 엔디언 `<`):
  | 부분 | 내용 | 바이트 |
  |---|---|---|
  | 헤더 | magic u16, version u8, flags u8 (포즈/왼손/오른손 검출 비트), seq u32, timestamp_ms u32 | 12 |
  | 포즈 | 33점 × (x, y, z, visibility) | 528 |
  | 손 ×2 | 21점 × (x, y, z) + 손바닥 쿼터니언 4 | 536 |
  | **합계** | | **1,076** |
- 30 FPS면 약 **31.5 KB/s** → 부하 거의 없음
- UDP 한 패킷 안전 크기(약 1,472바이트, MTU 1500 기준) 안에 들어감 → 패킷이 쪼개지지 않음. **이 한도를 넘지 않게 유지**
- 정밀도: float32는 1m 근처에서 0.12µm 단위 → 트래킹 오차(수 mm)보다 훨씬 정밀. float16은 1m 근처 약 1mm 단위라 크기는 절반이 되지만, 정확도를 우선하면 **float32 유지**
- magic + version으로 잘못된 패킷과 구버전 패킷을 거름. 손상 검사는 UDP 체크섬이 이미 해 주므로 CRC 불필요
- 검출 안 된 부위는 flags 비트로 표시하고 값은 0으로 채워서 **크기를 항상 고정** (수신 측 파싱 단순화)
- C# 수신: 리틀 엔디언 그대로 읽으면 됨 (`BinaryReader` 또는 `MemoryMarshal.Cast<byte, float>`). 양쪽 모두 구조체 필드 순서와 크기를 문서와 똑같이 맞출 것

## 11. 참고: 비슷한 방송용 프로그램 (트래킹 품질 비교용)

- **Warudo**: Unity 기반 3D VTuber 앱, 웹캠 MediaPipe + iPhone 얼굴 조합 지원
- **XR Animator**: MediaPipe 웹캠 트래커 (오픈소스)
- **VSeeFace**, **VMagicMirror**, **Webcam Motion Capture**
- iPhone 얼굴 전송 앱: iFacialMocap, Facemotion3d, Waidayo
- 이 프로젝트는 이 프로그램들과 호환하지 않음 (자체 바이너리 프로토콜)

## 12. 중앙 서버: VishaSynapse (별도 저장소)

- GitHub `Vishamos/VishaSynapse`. 방송용 기기·프로그램을 WebSocket으로 잇는 중계 서버
- 이 트래커는 시그니처 **31(Body)**로 등록하고 Vishamos(11)로 바이너리를 보냄
- 접속·등록·메시지 규약: VishaSynapse `docs/protocol/README.md` (이 프로젝트에서는 읽기만 함)
- Body 데이터 형식: 이 저장소 `docs/protocol/README.md`
