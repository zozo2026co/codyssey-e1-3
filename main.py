"""Codyssey E1-3: Mini NPU Simulator. Python 3.8+, standard library only."""
import json
import math
import re
import time
from pathlib import Path

EPSILON = 1e-9
REPEATS = 20
DATA_PATH = Path(__file__).resolve().parent / "data.json"


def normalize_label(value):
    if not isinstance(value, str):
        raise ValueError("라벨은 문자열이어야 합니다")
    labels = {"+": "Cross", "cross": "Cross", "x": "X"}
    result = labels.get(value.strip().lower())
    if result is None:
        raise ValueError("지원하지 않는 라벨: {!r} (Cross/+ 또는 X/x 사용)".format(value))
    return result


def validate_matrix(matrix, size, label):
    if not isinstance(matrix, list) or len(matrix) != size:
        raise ValueError("{}: 행 수가 {}개여야 합니다".format(label, size))
    for row_index, row in enumerate(matrix, start=1):
        if not isinstance(row, list) or len(row) != size:
            raise ValueError("{}: {}행은 열 수가 {}개여야 합니다".format(label, row_index, size))
        for col_index, value in enumerate(row, start=1):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("{}: ({}, {}) 위치는 유한한 숫자여야 합니다".format(label, row_index, col_index))
    return matrix


def mac(pattern, filter_matrix):
    """Same-position multiply-accumulate via two explicit loops."""
    score = 0.0
    for row in range(len(pattern)):
        for col in range(len(pattern[row])):
            score += pattern[row][col] * filter_matrix[row][col]
    return score


def decide(score_first, score_second, first_label="A", second_label="B"):
    if abs(score_first - score_second) < EPSILON:
        return "UNDECIDED"
    return first_label if score_first > score_second else second_label


def benchmark(pattern, filter_matrix, repeats=REPEATS):
    """Average only the MAC-call interval; no printing or file I/O."""
    mac(pattern, filter_matrix)  # warm-up, excluded
    elapsed_ns = 0
    for _ in range(repeats):
        start = time.perf_counter_ns()
        mac(pattern, filter_matrix)
        elapsed_ns += time.perf_counter_ns() - start
    return elapsed_ns / repeats / 1_000_000


def read_matrix(name, size=3):
    print("\n{} ({}줄, 각 줄에 숫자 {}개 입력)".format(name, size, size))
    matrix = []
    while len(matrix) < size:
        raw = input("{}행 > ".format(len(matrix) + 1)).split()
        if len(raw) != size:
            print("입력 형식 오류: 각 줄에 {}개의 숫자를 공백으로 구분해 입력하세요.".format(size))
            continue
        try:
            row = [float(x) for x in raw]
            if any(not math.isfinite(x) for x in row):
                raise ValueError("유한하지 않은 숫자")
        except ValueError:
            print("입력 형식 오류: NaN/무한대를 제외한 숫자만 입력하세요.")
            continue
        matrix.append(row)
    return matrix


def default_matrix(size, kind):
    """Only for the 3x3 benchmark, not an extra user-visible generator mode."""
    if kind == "Cross":
        return [[1 if r == size // 2 or c == size // 2 else 0 for c in range(size)] for r in range(size)]
    return [[1 if r == c or r + c == size - 1 else 0 for c in range(size)] for r in range(size)]


def print_performance(size_to_matrices):
    print("\n[성능 분석: MAC 함수 호출만 측정 / 크기당 {}회 평균]".format(REPEATS))
    print("{:<12} {:>16} {:>15}".format("크기", "평균 시간(ms)", "MAC 위치 수(N²)"))
    print("-" * 49)
    for size in (3, 5, 13, 25):
        pair = size_to_matrices.get(size)
        if pair is None:
            print("{:<12} {:>16} {:>15}".format("{}x{}".format(size, size), "미측정", size * size))
            continue
        pattern, filter_matrix = pair
        ms = benchmark(pattern, filter_matrix)
        print("{:<12} {:>16.6f} {:>15}".format("{}x{}".format(size, size), ms, size * size))
    print("※ N²은 필터 1개당 곱셈 위치 수입니다. 시간은 실행 환경에 따라 달라집니다.")


def mode_manual():
    print("\n[모드 1] 3x3 직접 입력")
    filter_a = read_matrix("필터 A")
    filter_b = read_matrix("필터 B")
    print("\n필터 2개 입력 완료")
    pattern = read_matrix("입력 패턴")
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    # Both filters are measured; report mean MAC call time across two filters.
    time_a = benchmark(pattern, filter_a)
    time_b = benchmark(pattern, filter_b)
    decision = decide(score_a, score_b)
    print("\n========== MAC 결과 ==========")
    print("필터 2개 입력 완료")
    print("A 점수: {:.12g}".format(score_a))
    print("B 점수: {:.12g}".format(score_b))
    print("평균 처리 시간: {:.6f} ms (필터당 MAC 호출, 각 {}회 측정)".format((time_a + time_b) / 2, REPEATS))
    print("최종 판정: {}".format("판정 불가(UNDECIDED)" if decision == "UNDECIDED" else decision))
    print("동점 기준: |A-B| < {}".format(EPSILON))
    print("※ 모드 1은 정답 데이터가 없어 PASS/FAIL을 집계하지 않습니다.")
    print_performance({3: (pattern, filter_a)})


def parse_size(key):
    match = re.fullmatch(r"size_([1-9][0-9]*)_([1-9][0-9]*)", key)
    if match is None:
        raise ValueError("패턴 키 형식 오류: size_N_번호여야 합니다")
    return int(match.group(1))


def prepare_filter_group(filter_groups, size):
    group_name = "size_{}".format(size)
    group = filter_groups.get(group_name)
    if not isinstance(group, dict):
        raise ValueError("{} 필터가 없거나 객체가 아닙니다".format(group_name))
    normalized = {}
    for raw_name, matrix in group.items():
        standard = normalize_label(raw_name)
        if standard in normalized:
            raise ValueError("{}: {} 필터가 중복됩니다".format(group_name, standard))
        normalized[standard] = validate_matrix(matrix, size, "{}/{}".format(group_name, standard))
    if set(normalized) != {"Cross", "X"}:
        raise ValueError("{}: Cross, X 필터가 모두 필요합니다".format(group_name))
    return normalized


def mode_json():
    print("\n[모드 2] data.json 자동 분석")
    print("JSON 경로: {}".format(DATA_PATH))
    try:
        with DATA_PATH.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print("JSON 로드 실패: {}".format(exc))
        print("원본 data.json을 main.py와 같은 폴더에 넣고 다시 실행하세요.")
        return
    if not isinstance(data, dict) or not isinstance(data.get("filters"), dict) or not isinstance(data.get("patterns"), dict):
        print("JSON 스키마 오류: filters와 patterns는 객체여야 합니다.")
        return
    filters = data["filters"]
    patterns = data["patterns"]
    print("JSON 로드 완료: 필터 그룹 {}개, 패턴 {}개".format(len(filters), len(patterns)))
    if not patterns:
        print("패턴이 없어 분석할 수 없습니다.")
    cache = {}
    sample_for_speed = {3: (default_matrix(3, "Cross"), default_matrix(3, "Cross"))}
    for size in (5, 13, 25):
        try:
            group = prepare_filter_group(filters, size)
            cache[size] = (group, None)
            sample_for_speed[size] = (group["Cross"], group["Cross"])
            print("필터 로드 완료: size_{} (Cross, X)".format(size))
        except ValueError as exc:
            print("필터 확인: {}".format(exc))
    passed = 0
    failed = []
    print("\n[패턴별 분석]")
    for key, item in patterns.items():
        print("\n--- {} ---".format(key))
        try:
            if not isinstance(key, str):
                raise ValueError("패턴 키가 문자열이 아닙니다")
            size = parse_size(key)
            group_key = "size_{}".format(size)
            print("선택 로그: JSON 패턴 {} → N={} → {}의 Cross/X 필터".format(key, size, group_key))
            if size in cache:
                chosen = cache[size][0]
            else:
                chosen = prepare_filter_group(filters, size)
                cache[size] = (chosen, None)
                if size in (3, 5, 13, 25):
                    sample_for_speed[size] = (chosen["Cross"], chosen["Cross"])
            if not isinstance(item, dict):
                raise ValueError("패턴 항목이 객체가 아닙니다")
            pattern = validate_matrix(item.get("input"), size, "{} 입력".format(key))
            expected = normalize_label(item.get("expected"))
            score_cross = mac(pattern, chosen["Cross"])
            score_x = mac(pattern, chosen["X"])
            prediction = decide(score_cross, score_x, "Cross", "X")
            print("Cross 점수: {:.12g} / X 점수: {:.12g}".format(score_cross, score_x))
            print("판정: {} / expected: {}".format(prediction, expected))
            if prediction == expected:
                passed += 1
                print("결과: PASS")
            else:
                reason = "동점(EPSILON)으로 UNDECIDED" if prediction == "UNDECIDED" else "예상 라벨과 판정 불일치"
                failed.append((key, reason))
                print("결과: FAIL - {}".format(reason))
        except (ValueError, TypeError, OverflowError) as exc:
            failed.append((key, str(exc)))
            print("결과: FAIL - {}".format(exc))
    print_performance(sample_for_speed)
    print("\n========== 전체 결과 요약 ==========")
    print("전체 테스트: {}개".format(len(patterns)))
    print("PASS: {}개 / FAIL: {}개".format(passed, len(failed)))
    if failed:
        print("실패 케이스:")
        for key, reason in failed:
            print("- {}: {}".format(key, reason))
    else:
        print("실패 케이스: 없음")
    print("※ 모드 2는 expected와 비교하므로 UNDECIDED가 FAIL로 집계될 수 있습니다.")


def main():
    print("=== Mini NPU Simulator (Codyssey E1-3) ===")
    while True:
        print("\n1. 사용자 입력 (3x3)\n2. data.json 자동 분석\n0. 종료")
        try:
            choice = input("선택 > ").strip()
            if choice == "1":
                mode_manual()
            elif choice == "2":
                mode_json()
            elif choice == "0":
                print("프로그램을 종료합니다.")
                break
            else:
                print("0, 1, 2 중 하나를 입력하세요.")
        except (EOFError, KeyboardInterrupt):
            print("\n프로그램을 종료합니다.")
            break


if __name__ == "__main__":
    main()
