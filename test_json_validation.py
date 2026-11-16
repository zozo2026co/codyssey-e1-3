"""Codyssey E1-3 JSON error-handling check. Does not modify data.json."""
import copy
import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import main


def main_test():
    original_path = Path(__file__).resolve().parent / "data.json"
    original_bytes = original_path.read_bytes()
    with original_path.open("r", encoding="utf-8-sig") as file:
        original = json.load(file)

    altered = copy.deepcopy(original)
    key = "size_5_1"
    altered["patterns"][key]["input"][0].pop()  # 5 numbers -> 4

    with tempfile.TemporaryDirectory() as directory:
        temporary_path = Path(directory) / "data_error_test.json"
        temporary_path.write_text(json.dumps(altered, ensure_ascii=False), encoding="utf-8")
        original_setting = main.DATA_PATH
        output = io.StringIO()
        try:
            main.DATA_PATH = temporary_path
            with redirect_stdout(output):
                main.mode_json()
        finally:
            main.DATA_PATH = original_setting

    report = output.getvalue()
    print(report)
    checks = {
        "잘못된 열 수를 FAIL로 처리": "size_5_1 입력: 1행은 열 수가 5개여야 합니다" in report,
        "다음 사례 분석 계속 진행": "--- size_5_2 ---" in report and "결과: PASS" in report,
        "전체 6개 사례 집계 유지": "전체 테스트: 6개" in report,
        "원본 파일 미수정": original_path.read_bytes() == original_bytes,
    }
    print("\n[시험 결과]")
    for name, ok in checks.items():
        print("{}: {}".format(name, "PASS" if ok else "FAIL"))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main_test()
