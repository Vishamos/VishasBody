---
name: simple-test
description: VishasBody 최소 실행 테스트. developer가 구현 직후, 메인 스레드가 직접 코드를 고친 뒤 에러가 없는지 확인할 때 사용한다 (문법 검사, 단위 테스트, 웹캠 없는 스모크 테스트).
---

# 최소 실행 테스트

에러 없이 도는지만 본다. 명세 기준 검증은 qa가 한다.

## Python
- 프로젝트용 Python(3.12, `requirements.txt` 설치)으로 실행한다. PC마다 위치가 다르므로 `CLAUDE.local.md`를 따른다. 보통 `.venv/Scripts/python`이다. 아래 `<py>`가 그것이다.
- 낯선 PC에서는 `python`을 바로 실행하지 않고 `py list`로 먼저 확인한다(없으면 Windows가 Python을 자동 설치한다).

## 순서
1. **문법 검사** (바뀐 `.py` 파일마다, `py_compile` 금지: `__pycache__`를 만듦):
   ```bash
   python -B .claude/hooks/check_syntax.py <파일들>
   ```
   Edit·Write 뒤에는 같은 스크립트가 훅으로 자동 실행된다.
2. **단위 테스트**:
   ```bash
   <py> -B -m unittest discover -s test
   ```
3. **스모크 테스트** (웹캠 없이 `main.main()` 실행):
   - 스크립트는 `.temp/`(git 제외)에 Write 도구로 만들고 `<py> -B .temp/<파일>.py` 한 줄로 실행한다.
   - `cv2.VideoCapture`, `cv2.imshow`, `cv2.waitKey`, `cv2.namedWindow`, `cv2.setMouseCallback`, `cv2.getWindowProperty`를 가짜로 바꾼다. `getWindowProperty`는 1을 돌려줘야 한다(아니면 창이 닫힌 것으로 보고 루프가 끝남).
   - 가짜 카메라 프레임은 단색·도형으로 만든다. 실제 사진·영상 파일을 쓰지 않는다.
   - 서버가 필요하면 테스트 안에서 `127.0.0.1`의 기본이 아닌 포트에 가짜 서버를 띄운다. 실제 VishaSynapse 서버에 접속하지 않는다.
   - ONNX 백엔드(기본)는 DirectML GPU가 없는 PC에서 실패할 수 있다. 그때는 `--backend mediapipe`로 돌리고 보고에 적는다.
   - 끝나면 스크립트를 지운다.

## 결과
- 단계마다 통과/실패, 실행하지 못한 것과 이유.
- 실제 웹캠·서버 연동은 확인할 수 없으므로 "사용자가 확인할 것"으로 넘긴다.
