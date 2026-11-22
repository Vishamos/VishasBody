# 노션 기획 반영 질문

노션 `VishaSTD / VishasBody`에 반영할 질문과 사용자 결정. 반영되면 지운다.
마지막으로 읽은 노션 판: 2026-11-22 01:54

## 노션 정리 (기획 검토 요청)
1. **`[Body-Receiver]`의 "시퀀스 번호가 이전보다 작은 패킷은 버림"은 바꿔야 한다.** WebSocket(TCP)이라 순서가 뒤바뀌지 않고, 트래커를 다시 켜면 seq가 1부터 시작해서 이 규칙대로면 재시작 후 모든 패킷을 버린다. → "seq가 작아지면 트래커 재시작으로 보고 상태 초기화" (프로토콜 §5)
2. `[Body-Receiver]` 절은 `docs/protocol/README.md` §5로 옮겼다. 노션에는 "받는 쪽 규칙은 Vishas_Capture `docs/protocol/README.md`" 한 줄로 줄여도 된다.
3. `[Body-Track-Smooth]` 측정 방법: "10초 정지" → "5초 정지 × 자세 2∼3개(책상 위, 들어 올림)"
4. `[Body-Packet]`의 `//` 블렌드 쉐이프 질문 답: 몸은 해당 없음(뼈 회전). 손가락 굽힘 값은 가능하지만 보류(명세 01 §4.11).
5. 태그 서식 통일: `[Body-Track-Smooth]`, `[Body-Packet-Header]`, `-Pose`, `-Hand`, `-Coord`가 코드 서식이 아님. `[Body-Track-Perf]`가 목록 밖에 있음.

## 사용자 답변 (노션 이전 필요)
- (2026-11-22) `[Body-Packet-Coord]` 트래커가 Unity 좌표로 변환해서 보냄. 쿼터니언 순서 x, y, z, w
- (2026-11-22) `[Body-Packet-Header]` 종류 번호 31, flags 뒤 예약 바이트 3개로 4바이트 정렬 → 1,080바이트 (노션의 "약 1,077바이트"도 고칠 것)
- (2026-11-22) 서브에이전트(developer·qa·security)는 두지 않는다. 테스트는 `test/`(커밋) + `.temp/`(임시)
- (2026-11-22) `[Body-Packet-Hand]` 손 좌표 원점은 손목(0번). 손바닥 회전은 `LookRotation(손가락 방향=+z, 손바닥 방향=+y)`, 계산 불가면 (0, 0, 0, 0)
- (2026-11-22) `[Body-Packet-Header]` seq는 1부터 +1, timestamp_ms는 프레임을 읽은 시각(트래커 시작 후 ms)
- (2026-11-22) `[Body-Track-Perf]` 몸 프레임은 손 추론을 기다리지 않는다. 손은 최신 완료 결과를 쓴다(손 약 15∼30 FPS, 몸 30 FPS). 근거: 손이 보이면 25 FPS로 떨어짐(GitHub 이슈 #1)
- (2026-11-22) VishaSynapse 기준은 GitHub `Vishamos/VishaSynapse`, 저장소 전체 읽기 허용(수정 금지)
