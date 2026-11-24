# 노션 기획 반영 질문

노션 `VishaSTD / VishasBody`에 반영할 질문과 사용자 결정. 반영되면 지운다.
마지막으로 읽은 노션 판: 2026-11-22 01:54

## 노션 정리 (기획 검토 요청)
1. **`[Body-Receiver]`의 "시퀀스 번호가 이전보다 작은 패킷은 버림"은 바꿔야 한다.** WebSocket(TCP)이라 순서가 뒤바뀌지 않고, 트래커를 다시 켜면 seq가 1부터 시작해서 이 규칙대로면 재시작 후 모든 패킷을 버린다. → "seq가 작아지면 트래커 재시작으로 보고 상태 초기화" (프로토콜 §5)
2. `[Body-Receiver]` 절은 `docs/protocol/README.md` §5로 옮겼다. 노션에는 "받는 쪽 규칙은 VishasBody `docs/protocol/README.md`" 한 줄로 줄여도 된다.
3. `[Body-Track-Smooth]` 측정 방법: "10초 정지" → "5초 정지 × 자세 2∼3개(책상 위, 들어 올림)"
4. `[Body-Packet]`의 `//` 블렌드 쉐이프 질문 답: 몸은 해당 없음(뼈 회전). 손가락 굽힘 값은 가능하지만 보류(명세 01 §4.11).
5. 태그 서식 통일: `[Body-Track-Smooth]`, `[Body-Packet-Header]`, `-Pose`, `-Hand`, `-Coord`가 코드 서식이 아님. `[Body-Track-Perf]`가 목록 밖에 있음.

## 사용자 답변 (노션 이전 필요)
- (2026-11-22) `[Body-Packet-Coord]` 트래커가 Unity 좌표로 변환해서 보냄. 쿼터니언 순서 x, y, z, w
- (2026-11-22) `[Body-Packet-Header]` 종류 번호 31, flags 뒤 예약 바이트 3개로 4바이트 정렬 → 1,080바이트 (노션의 "약 1,077바이트"도 고칠 것. 2026-11-23 루트 위치 추가로 최종 1,092바이트, 아래 항목)
- (2026-11-22) 서브에이전트(developer·qa·security)는 두지 않는다. 테스트는 `test/`(커밋) + `.temp/`(임시)
- (2026-11-22) `[Body-Packet-Hand]` 손 좌표 원점은 손목(0번). 손바닥 회전은 `LookRotation(손가락 방향=+z, 손바닥 방향=+y)`, 계산 불가면 (0, 0, 0, 0)
- (2026-11-22) `[Body-Packet-Header]` seq는 1부터 +1, timestamp_ms는 프레임을 읽은 시각(트래커 시작 후 ms)
- (2026-11-22) `[Body-Track-Perf]` 몸 프레임은 손 추론을 기다리지 않는다. 손은 최신 완료 결과를 쓴다(손 약 15∼30 FPS, 몸 30 FPS). 근거: 손이 보이면 25 FPS로 떨어짐(GitHub 이슈 #1)
- (2026-11-22) VishaSynapse 기준은 GitHub `Vishamos/VishaSynapse`, 저장소 전체 읽기 허용(수정 금지)
- (2026-11-23) **새 기획 항목(태그 제안 `[Body-Packet-Root]`)**: 아바타가 사람의 앞뒤·좌우 이동을 따라가도록 카메라 기준 골반 위치를 보냄. 패킷 맨 끝에 float 3개 → 1,092바이트, 버전 2, flags bit3 = 위치 유효. 위치 계산에는 몸통(얼굴·어깨·골반)만 쓴다(팔은 뻗으면 깊이 추정이 틀려 위치를 끌고 감). 카메라 화각은 PC별 설정(기본 72°), 줄자로 잰 거리에서 한 번 보정: 실행 PC 웹캠 RPC-20F는 **60°**(1.0m·1.4m 실측, 오차 약 5% 이내). 시작 위치 기준 보정은 받는 쪽(명세 01 §5)
- (2026-11-23) `[Body-Packet-Header]` 크기 1,080 → 1,092바이트, 버전 1 → 2 (위 항목 때문)
- (2026-11-23) `[Body-Receiver]` Body 데이터 규약의 기준은 VishasBody 저장소(`docs/protocol/`). 받는 쪽이 어긋나면 이쪽을 맞추지 않고, 필요한 수정은 그 저장소의 GitHub 이슈로 올린다(예: Vishamos/Vishamos#1 버전 2 수신)
- (2026-11-24) `[Body-Tech]` 추론 백엔드 선택 추가: MediaPipe(CPU, 기본) / ONNX Runtime DirectML(GPU, `BodyTrackerGPU.bat`). Windows MediaPipe에 GPU가 없어 모델을 ONNX로 변환해 실행, 포즈 23 → 10ms, 손 28∼31 → 13∼14ms. 방송 중(OBS + Vishamos)에도 30 FPS·OBS 손실 프레임 0. 기본값을 GPU로 바꿀지는 사용자 결정 대기(명세 01 §1.6)
