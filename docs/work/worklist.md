# 작업 목록

> **현재 진행 (2026-11-22):** Send-1·Send-2 완료(패킷 + WebSocket 송신). 실제 서버 연동 확인 대기.
> **다음 할 일:**
> 1. (사용자) 실행 PC에서 `pip install websockets`, `config.local.json` 작성 → VishaSynapse에 붙여 등록·송신 확인
> 2. Doc-1 README 정리
> 2. 그 사이 사용자가 할 수 있는 것: Track-1 정지 떨림 측정 (웹캠 필요)

## 운영 방식
- **해야 할 작업만 적는다.** 끝난 항목은 지운다. 명세에 근거한 항목은 명세 "구현 현황"에, 명세 밖 항목은 커밋 메시지(항목 번호 포함)로만 남는다.
- 사용자가 항목을 고르면 메인 세션이 수정 방향을 제안하고, 승인된 항목만 반영한다.
- 항목 형식: `- [ ] <번호> <내용> — 기획: [태그] / 명세: <문서 번호> §<절>`. 근거가 없으면 `기획: 없음(AI 발견)`.
- 번호는 `영역-번호`. 영역 안에서 계속 늘리고 다시 쓰지 않는다. 영역: Doc(문서), Spec(명세), Send(송신), Track(트래킹), Env(환경).
  다음 번호: Doc-2, Spec-2, Send-3, Track-3, Env-2. (Spec-1 명세 01 초안 작성 완료, Env-1 2026-11-22 종료: 실행은 기존 환경이 있는 다른 PC에서 git pull 후 실행)

## 사용자 조치 대기
- [ ] 노션 정리 (`docs/work/plan_review.md`)
- [ ] (Vishamos 프로젝트) 수신 버퍼 1KB → 1,080바이트 이상, `docs/protocol/README.md` §5대로 수신

## Doc. 문서
- [ ] Doc-1 README를 새 구조에 맞게 정리(Send-2에서 2·3·4·5번 송신 관련 줄과 6번 임시 형식은 고침): 12번 옛 서버 요약(서버가 먼저 `[0,0]` 인사, deviceType 10·30) 폐기 → `docs/protocol`·Synapse 규약 참조로, 6번 송신 데이터를 명세 01 참조로, 10번 설계 메모 삭제(명세로 옮겨짐), 3번 환경(PC별 경로·Python) 정정, `requirements.txt` 추가(실행 PC 확인 버전: Python 3.12.10, mediapipe 1.2.0, opencv-python 5.0.0.93, websockets 17.4는 개발 PC 기준), 4번 실행 방법에 "실행 PC는 git pull 후 실행, 개발 PC(Python 3.15)는 단위 테스트만" 추가 — 기획: 없음 / 명세: 01

## Send. 송신

## Track. 트래킹
- [ ] Track-1 정지 떨림 측정: 손 5초 정지 × 자세 2∼3개(책상 위, 들어 올림) → 손목 이동량 3mm 이하 양호, 5mm 초과면 스무딩 필요. 측정 모드 추가가 필요하면 별도 제안 — 기획: `[Body-Track-Smooth]` / 명세: 01 §1.5
- [ ] Track-2 스무딩 위치 결정 (One Euro Filter, 트래커 쪽이면 1ms 미만). Track-1 결과에 따름 — 기획: `[Body-Track-Smooth]` / 명세: 01 §1.5
