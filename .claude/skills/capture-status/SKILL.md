---
name: capture-status
description: 사용자가 "현재 상태는?", "상태 확인", "status", "프로젝트 상황은?"이라고 하면 Vishas_Capture 진행 상황을 보고한다. worklist, 기술 명세의 구현 현황, git 상태, Python 환경, VishaSynapse 규약 갱신 여부를 바탕으로 정리한다.
---

# 상태 보고

## 1. 수집 (읽기 전용)
- `docs/work/worklist.md` (맨 위 "현재 진행"과 남은 항목)
- `docs/tech_spec/*.md`의 "구현 현황" 표
- `git status -sb`, `git log --oneline -5`
- 환경: `py list`(설치된 Python. `python`을 바로 실행하지 않는다, 없으면 자동 설치됨)
- VishaSynapse: 로컬 사본 HEAD와 `git ls-remote https://github.com/Vishamos/VishaSynapse HEAD` 비교, `docs/protocol/README.md`의 "갱신" 날짜가 명세에 반영된 날짜보다 새로운지

## 2. 보고 형식
```
## Vishas_Capture 상태 (YYYY-MM-DD)
- 환경: Python X / mediapipe Y (이 PC 설치 여부)
- 현재 진행: <worklist "현재 진행">
- 진행도: 명세별 "구현 현황" 요약
- 남음: N건 (영역별 개수)
- Synapse 규약: 최신 / 갱신됨(바뀐 절) / 로컬 사본 오래됨(pull 필요)
- 사용자 조치 대기: <있으면>
- 다음 추천: <항목 번호와 이유>
```

## 3. 추천 기준
1. worklist "현재 진행"의 우선순위를 따른다. 그 안에서는 실행 불가 → 송신 연동 → 트래킹 품질 → 문서 순서.
2. 같은 파일을 고치는 항목은 묶어서 추천한다.
3. 사용자 조치(웹캠 측정, 받는 쪽 앱 수정, 노션 정리)는 따로 표시한다.

이 스킬은 파일을 수정하지 않는다.
