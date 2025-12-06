# Backend/nl_regression.py
"""
Lightweight regression harness for QuotePilot natural-language + engines.

Run with:
    python -m Backend.nl_regression

This does NOT hit the HTTP API. It calls the NL interpreters and engines
directly so you can quickly see if changes broke anything.
"""

from typing import List, Dict, Any

from Backend.PartNumberEngine.nl_qpsah200s import interpret_qpsah200s_description
from Backend.PartNumberEngine.nl_qpmag import interpret_qpmag_description
from Backend.PartNumberEngine.base_engine import get_engine, PartNumberError


class TestCase:
    def __init__(
        self,
        model: str,
        description: str,
        expected_model: str,
        expected_part_prefix: str | None = None,
    ):
        self.model = model
        self.description = description
        self.expected_model = expected_model
        # Only check the beginning of the part number (you can tighten later)
        self.expected_part_prefix = expected_part_prefix


def run_case(case: TestCase) -> Dict[str, Any]:
    """
    Run one NL → engine test case and return a dict with the results.
    """
    # 1) Run the appropriate interpreter
    if case.model.upper() == "QPSAH200S":
        nl_result = interpret_qpsah200s_description(case.description)
    elif case.model.upper() == "QPMAG":
        nl_result = interpret_qpmag_description(case.description)
    else:
        return {
            "case": case,
            "passed": False,
            "error": f"Unknown model for test harness: {case.model}",
        }

    part_number = nl_result.get("part_number")
    model_from_nl = nl_result.get("model", case.model)

    if not part_number:
        return {
            "case": case,
            "passed": False,
            "error": "NL interpreter did not return a part number",
            "nl_result": nl_result,
        }

    # 2) Price it with the real engine (should NOT raise in NL path)
    engine = get_engine(model_from_nl)
    try:
        pricing = engine.price_part_number(part_number)
    except PartNumberError as exc:
        return {
            "case": case,
            "passed": False,
            "error": f"Engine raised PartNumberError: {exc}",
            "nl_result": nl_result,
        }

    # 3) Basic assertions
    passed = True
    failures: list[str] = []

    # Model check
    if model_from_nl != case.expected_model:
        passed = False
        failures.append(
            f"Model mismatch: expected {case.expected_model}, got {model_from_nl}"
        )

    # Part prefix check if provided
    if case.expected_part_prefix:
        if not part_number.startswith(case.expected_part_prefix):
            passed = False
            failures.append(
                f"Part prefix mismatch: expected prefix {case.expected_part_prefix}, got {part_number}"
            )

    return {
        "case": case,
        "passed": passed,
        "failures": failures,
        "nl_result": nl_result,
        "pricing": pricing,
    }


def print_report(results: List[Dict[str, Any]]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print("=" * 72)
    print(f"QuotePilot NL regression summary: {passed}/{total} passed, {failed} failed")
    print("=" * 72)
    print()

    for idx, result in enumerate(results, start=1):
        case: TestCase = result["case"]
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{idx}] {status}: {case.model} | \"{case.description}\"")

        nl_part = result.get("nl_result", {}).get("part_number")
        print(f"    NL part: {nl_part}")

        if not result["passed"]:
            error = result.get("error")
            if error:
                print(f"    ERROR: {error}")
            for failure in result.get("failures", []):
                print(f"    - {failure}")

        print()


def run_strict_engine_test() -> Dict[str, Any]:
    """
    Direct engine-level regression for strict validation.

    This ensures that passing an invalid code to the explicit engine path
    raises PartNumberError with the structured fields populated.
    """
    name = "QPSAH200S invalid output signal code raises structured PartNumberError"
    engine = get_engine("QPSAH200S")

    test_part = "QPSAH200S-Z-M-G-3-C-3-1-1-C-1-M"  # Z is invalid for output signal

    try:
        engine.price_part_number(test_part)
    except PartNumberError as exc:
        passed = True
        failures: list[str] = []

        # Segment key/label should clearly map to "output signal type"
        norm_segment = (exc.segment or "").replace(" ", "").replace("_", "").lower()
        if "output" not in norm_segment or "signal" not in norm_segment:
            passed = False
            failures.append(
                f"segment mismatch: expected something like 'output_signal_type', got {exc.segment!r}"
            )

        if exc.invalid_code != "Z":
            passed = False
            failures.append(
                f"invalid_code mismatch: expected 'Z', got {exc.invalid_code!r}"
            )

        expected_valid = ["A", "B", "C"]
        if sorted(exc.valid_codes or []) != expected_valid:
            passed = False
            failures.append(
                f"valid_codes mismatch: expected {expected_valid}, got {exc.valid_codes}"
            )

        return {
            "name": name,
            "passed": passed,
            "failures": failures,
            "error_obj": exc,
        }

    # If we get here, no error was raised (which is a failure for this test)
    return {
        "name": name,
        "passed": False,
        "failures": [
            "Expected PartNumberError, but engine.price_part_number did not raise."
        ],
        "error_obj": None,
    }


def main() -> None:
    # You can expand this list as you find important scenarios
    cases: List[TestCase] = [
        # DP transmitter: medium span, general purpose
        TestCase(
            model="QPSAH200S",
            description="DP transmitter, 0-150 inches of water, stainless wetted, coated aluminum housing, 4-20 mA.",
            expected_model="QPSAH200S",
            expected_part_prefix="QPSAH200S-A-M-",
        ),
        # DP transmitter: high span
        TestCase(
            model="QPSAH200S",
            description="DP transmitter, 0 to 800 inWC, stainless steel wetted parts, explosion proof.",
            expected_model="QPSAH200S",
            expected_part_prefix="QPSAH200S-A-H-",
        ),
        # DP transmitter: extreme span request (should snap to high range)
        TestCase(
            model="QPSAH200S",
            description="DP transmitter, 0 to 5000 inches of water column, stainless wetted parts, general purpose area.",
            expected_model="QPSAH200S",
            expected_part_prefix="QPSAH200S-A-H-",
        ),
        # MAG meter: 1 inch PTFE, wafer, 4-20 mA
        TestCase(
            model="QPMAG",
            description="1 inch mag meter, PTFE liner, stainless electrodes, wafer style, 4-20 mA output.",
            expected_model="QPMAG",
            expected_part_prefix="QPMAG-04-PT-SS-F1-",
        ),
        # MAG meter: 3 inch, flanged 150, AC power
        TestCase(
            model="QPMAG",
            description="3 inch magnetic flowmeter, hard rubber liner, 150 class flanged, AC power, general purpose area.",
            expected_model="QPMAG",
            expected_part_prefix="QPMAG-10-HR-",
        ),
    ]

    results: List[Dict[str, Any]] = []
    for case in cases:
        results.append(run_case(case))

    print_report(results)

    # ------------------------------------------------------------------
    # Strict engine validation block
    # ------------------------------------------------------------------
    strict_result = run_strict_engine_test()

    print("=" * 72)
    print("Strict engine validation tests")
    print("=" * 72)
    print()

    status = "PASS" if strict_result["passed"] else "FAIL"
    print(f"[S1] {status}: {strict_result['name']}")
    if not strict_result["passed"]:
        for failure in strict_result.get("failures", []):
            print(f"    - {failure}")
    print()


if __name__ == "__main__":
    main()
