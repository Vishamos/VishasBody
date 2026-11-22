---
name: capture-git
description: Vishas_Capture의 git 운영. 커밋을 만들거나 메시지를 쓸 때 사용한다. 단일 브랜치, 커밋 단위와 시점, 메시지 형식, 커밋 전 검사, 금지 명령을 다룬다.
---

# git 운영

## 저장소
- **공개 저장소** GitHub `Vishamos/VishasBody` (로컬 폴더 이름은 `Vishas_Capture`일 수 있음). **push는 사용자가 한다.**
- 공개이므로 커밋 어디에도 내부 IP, 서버 주소, PC의 로컬 경로·사용자 이름, 개인 정보를 넣지 않는다. PC별 정보는 `CLAUDE.local.md`·`.claude/settings.local.json`(git 제외)에 둔다.
- 브랜치는 `main` 하나만 쓴다. 작업 브랜치·worktree·PR을 쓰지 않는다(VishaSynapse와 같은 이유: 브랜치 전환 시 `.claude/` 규칙이 바뀜).
- 큰 단위가 끝나면 태그(`v0.1.0` 등)로 표시한다.
- 모델 파일(`*.task`)은 커밋하지 않는다(`.gitignore`). 새 모델을 쓰면 README "실행 방법"에 내려받는 주소를 추가한다.

## 커밋 단위와 시점
- **규칙**(`CLAUDE.md`, `.claude/`, `.githooks/`): 수정하고 확인한 직후 바로 커밋한다.
- **코드:** worklist 항목 하나당 커밋 하나(그 커밋만 되돌릴 수 있는 단위). 자체 확인과 커밋 전 검사를 통과하면 바로 커밋한다.
  - 명세 "구현 현황" 갱신과 worklist에서 끝난 항목 삭제는 같은 커밋에 넣는다.
- **문서**(README, 명세 본문, worklist 정리, plan_review): 쌓아 두고, 큰 단위가 끝났다고 판단될 때만 커밋을 **제안**한다.
- 바로 커밋한 뒤에는 `커밋: <해시> <메시지>` 한 줄로 보고한다.
- 파일은 이름을 지정해 올린다(`git add <파일>`). `git add -A`·`git add .`·`commit -a`는 쓰지 않는다.
- 커밋된 코드의 문제는 revert하지 않고 worklist 항목으로 고친다.

## 메시지 형식
- `[항목] 요약 (기획 [태그])` + 필요하면 본문. 예: `[Send-1] WebSocket 등록과 재접속 (기획 [Body-Send])`. 번호 체계는 worklist "운영 방식".
- 규칙 변경은 `[에이전트]`, 기획·명세 문서는 `[기획]`, 그 밖의 문서는 `[문서]`.
- 끝에 공동 작성자 줄. 시스템이 지정한 형식이 있으면 그것을 따른다.

## 커밋 전 검사
`.githooks/pre-commit`(`git config core.hooksPath .githooks`, PC마다 한 번 설정)이 자동으로 실행하고, 실패하면 커밋을 막는다. 막히면 우회(`--no-verify`)하지 않고 원인을 보고한다.
1. 제외 대상 스테이징 여부: `.env` 계열, `settings.local.json`, `*.pem`, `config.local.*`
2. 스테이징된 `.py` 문법 검사(`ast`)

수동 확인: 카메라 이미지·스크린샷이 섞이지 않았는지(방송 화면 보호).

## 하지 않는 것
- push, `push --force`, `reset --hard`, rebase 등 히스토리 재작성
- amend는 사용자가 요청하고 그 커밋이 아직 push되지 않았을 때만(`git log origin/main..main`으로 확인)
- VishaSynapse 저장소에 대한 git 쓰기 명령(`pull`·`fetch` 포함, 읽기는 `ls-remote`·`log`·`status`만)
