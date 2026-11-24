# 작업 목록

> **현재 진행 (2026-11-24):** 송신·루트 위치 완료(패킷 버전 2, 1,092바이트). ONNX GPU 백엔드 추가(Track-8), 기본값으로 전환(Track-12).
> **다음 할 일:**
> 1. (Vishamos) 버전 2 수신·루트 위치 적용 확인 후 이슈 #1 닫기, 팔 점 visibility 처리 이슈 #2
> 2. (사용자, 실행 PC) Track-3 확인: 트래커 창이 시작할 때 맨 앞에 오고, 다른 창을 누르면 그 뒤로 가는지
> 3. (사용자) 실행 PC 확인: 서버 재시작 후 재등록, `py -3.12 -m pip show opencv-contrib-python` 버전 → Env-2
> 4. Track-1 정지 떨림: ONNX 기록(`docs/work/onnx_gpu_backend.md` 5번)에 첫 측정값이 있음. 기준(손목 3mm)과 맞춰 볼지 결정

## 운영 방식
- **해야 할 작업만 적는다.** 끝난 항목은 지운다. 명세에 근거한 항목은 명세 "구현 현황"에, 명세 밖 항목은 커밋 메시지(항목 번호 포함)로만 남는다.
- 사용자가 항목을 고르면 메인 세션이 수정 방향을 제안하고, 승인된 항목만 반영한다.
- 항목 형식: `- [ ] <번호> <내용> — 기획: [태그] / 명세: <문서 번호> §<절>`. 근거가 없으면 `기획: 없음(AI 발견)`.
- 번호는 `영역-번호`. 영역 안에서 계속 늘리고 다시 쓰지 않는다. 영역: Doc(문서), Spec(명세), Send(송신), Track(트래킹), Env(환경).
  다음 번호: Doc-3, Spec-4, Send-3, Track-13, Env-3. (Spec-1 명세 01 초안 작성 완료, Env-1 2026-11-22 종료: 실행은 기존 환경이 있는 다른 PC에서 git pull 후 실행)

## 사용자 조치 대기
- [ ] 노션 정리 (`docs/work/plan_review.md`)
- [ ] (Vishamos 프로젝트) 버전 2 수신(1,092바이트, 루트 위치 적용): 이슈 Vishamos/Vishamos#1
- [ ] (Vishamos 프로젝트) 팔 점 visibility가 낮을 때 직전 값 유지·약하게 반영(프로토콜 §3.1): 이슈 Vishamos/Vishamos#2
- [ ] (실행 PC) 서버를 껐다 켰을 때 `[송신] VishaSynapse 등록 완료`가 다시 나오는지
- [ ] (실행 PC) `.temp/live_bench_hand.py` 삭제: Track-8 작업 중 카메라 영상 미리보기 창을 띄운 측정 스크립트(안전 규칙 1 위반). git 제외라 실행 PC에만 있음
- [ ] (실행 PC) `py -3.12 -m pip show opencv-contrib-python` 버전 알려 주기 (Env-2에 필요)
- [ ] (선택) 세 번째 바이트 `kind` 31 유지 여부. 권장: 유지(Body 메시지 종류 구분용, 명세 01 §4.2 사용자 답변). 헷갈림은 Synapse·Vishamos 로그에 "kind"로 표시해 해결

## Doc. 문서

## Spec. 명세

## Send. 송신

## Track. 트래킹
- [ ] Track-1 정지 떨림 측정: 손 5초 정지 × 자세 2∼3개(책상 위, 들어 올림) → 손목 이동량 3mm 이하 양호, 5mm 초과면 스무딩 필요. 측정 모드 추가가 필요하면 별도 제안 — 기획: `[Body-Track-Smooth]` / 명세: 01 §1.5
- [ ] Track-2 스무딩 위치 결정 (One Euro Filter, 트래커 쪽이면 1ms 미만). Track-1 결과에 따름 — 기획: `[Body-Track-Smooth]` / 명세: 01 §1.5
- [ ] Track-7 (보류, 재발 시) 손 오탐지: 가까이 앉아 팔을 내렸는데 오른손이 화면 우측 하단∼중앙에 검출됨(2026-11-23). 얼굴을 화면 중앙에 오게 카메라를 조정하니 줄어듦. 재발하면 짝지은 포즈 손목 visibility < 0.5이거나 손목끼리 너무 멀면(어깨너비 절반 등) 손을 버리는 안 — 기획: `[Body-Track-Hand]` / 명세: 01 §1.3
- [ ] Track-10 ONNX 백엔드의 가정한 값(OneEuro 계수, 손 영역 배율·이동)을 MediaPipe 공개 그래프 설정과 대조. 지금 값은 기억에 의존해 넣음(비교 결과는 양호) — 기획: 없음(AI 발견) / 명세: 01 §1.6

## Env. 환경
- [ ] Env-2 `requirements.txt` opencv 정리: mediapipe 1.2.0은 `opencv-contrib-python`(5.1.0.95)을 요구하고 `opencv-python`과 같은 `cv2` 폴더를 써서 서로 덮어씀. 실제로 불리는 것은 contrib → `opencv-python` 줄 삭제 권장. 실행 PC의 contrib 버전 확인 후 — 기획: 없음(AI 발견)
