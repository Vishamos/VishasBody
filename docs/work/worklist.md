# 작업 목록

## 현재 진행 (갱신: 2026-11-26 09:28)
- 진행 중: 없음 (visha-common 플러그인 작업 흐름으로 전환 — Main)
- 마지막 완료: Track-3 ae90048 (실행 PC 확인 대기)
- 대기:
  - (사용자, 실행 PC) Track-3 확인: 트래커 창이 시작할 때 맨 앞에 오고, 다른 창을 누르면 그 뒤로 가는지
  - (사용자, 실행 PC) 서버를 껐다 켰을 때 `[송신] VishaSynapse 등록 완료`가 다시 나오는지
  - (사용자, 실행 PC) `py -3.12 -m pip show opencv-contrib-python` 버전 알려 주기 → Env-2
  - (사용자, 실행 PC) `.temp/live_bench_hand.py` 삭제: Track-8 작업 중 카메라 영상 미리보기 창을 띄운 측정 스크립트(안전 규칙 1 위반). git 제외라 실행 PC에만 있음
  - (사용자) 노션 정리 (`docs/work/plan_review.md` "노션에 적을 것")
  - (사용자) push
- 다음: Spec-4 (규약 대조) → Track-1 측정값과 기준(손목 3mm) 맞춰 볼지 결정(ONNX 기록 `docs/work/onnx_gpu_backend.md` 5번에 첫 측정값) → Env-2

## 운영 방식
- 형식과 규칙은 `visha-common:design-work` 5절. 끝난 항목은 명세 "구현 현황"에 반영하고 지운다. 명세 밖 항목은 커밋 메시지(작업 번호 포함)로만 남는다.
- 근거 기획이 없으면 `기획: 없음(AI 발견)` 또는 `기획: 없음(사용자 요청)`.
- 영역: Doc(문서), Spec(명세), Send(송신), Track(트래킹), Env(환경). 다음 번호: Doc-3, Spec-5, Send-3, Track-13, Env-3.

## Doc. 문서

## Spec. 명세
- [ ] Spec-4 [P1] VishaSynapse 규약 대조: 명세 01이 참조한 판(`308e7bd`, 2026-11-18) 뒤로 `docs/protocol/README.md` 커밋 3개(2dc71b7, 9104e2f, 1eefccd)가 있음. Body(시그니처 31, 등록, 크기 한도)에 영향이 있는지 보고 참조 규약 해시를 갱신 — 기획: 없음(AI 발견) / 명세: 01 머리말

## Send. 송신

## Track. 트래킹
- [ ] Track-1 [P1] 정지 떨림 측정: 손 5초 정지 × 자세 2∼3개(책상 위, 들어 올림) → 손목 이동량 3mm 이하 양호, 5mm 초과면 스무딩 필요. 측정 모드 추가가 필요하면 별도 제안 — 기획: `[Body-Track-Smooth]` / 명세: 01 §1.5
- [ ] Track-2 [P1] 스무딩 위치 결정 (One Euro Filter, 트래커 쪽이면 1ms 미만) — 기획: `[Body-Track-Smooth]` / 명세: 01 §1.5 (보류 대기: 스무딩 여부와 위치)
- [ ] Track-7 [P2] (재발 시) 손 오탐지: 가까이 앉아 팔을 내렸는데 오른손이 화면 우측 하단∼중앙에 검출됨(2026-11-23). 얼굴을 화면 중앙에 오게 카메라를 조정하니 줄어듦. 재발하면 짝지은 포즈 손목 visibility < 0.5이거나 손목끼리 너무 멀면(어깨너비 절반 등) 손을 버리는 안 — 기획: `[Body-Track-Hand]` / 명세: 01 §1.3
- [ ] Track-10 [P2] ONNX 백엔드의 가정한 값(OneEuro 계수, 손 영역 배율·이동)을 MediaPipe 공개 그래프 설정과 대조. 지금 값은 기억에 의존해 넣음(비교 결과는 양호) — 기획: 없음(AI 발견) / 명세: 01 §1.6

## Env. 환경
- [ ] Env-2 [P1] `requirements.txt` opencv 정리: mediapipe 1.2.0은 `opencv-contrib-python`(5.1.0.95)을 요구하고 `opencv-python`과 같은 `cv2` 폴더를 써서 서로 덮어씀. 실제로 불리는 것은 contrib → `opencv-python` 줄 삭제 권장. 실행 PC의 contrib 버전 확인 후 — 기획: 없음(AI 발견)

## 올린 이슈
