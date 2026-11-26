"""Python 문법 검사 (ast, __pycache__를 만들지 않음).

- 인자로 파일을 주면 그 파일들을 검사한다(simple-test).
- 인자가 없으면 Claude Code PostToolUse 훅 입력(stdin JSON)의 tool_input.file_path를 검사한다.
실패하면 stderr에 쓰고 종료 코드 2(훅에서 Claude에게 오류를 돌려줌).
"""
import ast
import json
import sys


def check(path):
    try:
        with open(path, encoding="utf-8") as f:
            ast.parse(f.read(), path)
    except SyntaxError as e:
        sys.stderr.write(f"[문법 검사] {path}:{e.lineno} {e.msg}\n")
        return False
    return True


def main():
    files = sys.argv[1:]
    if not files:
        try:
            files = [json.load(sys.stdin)["tool_input"]["file_path"]]
        except (ValueError, KeyError, TypeError):
            return 0  # 입력을 못 읽으면 막지 않는다
    files = [f for f in files if f.endswith(".py")]
    ok = all([check(f) for f in files])
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
