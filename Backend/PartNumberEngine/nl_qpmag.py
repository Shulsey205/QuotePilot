from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import re


# --------------------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------------------


@dataclass
class SegmentChoice:
    segment: str
    code: str
    reason: str
    priority: int


@dataclass
class SegmentRule:
    segment: str
    code: str
    patterns: List[str]
    priority: int = 0  # higher number wins


# --------------------------------------------------------------------------------------
# Baseline configuration for QPMAG
# --------------------------------------------------------------------------------------
# Must match MASTER_SEGMENTS in qpmag_engine.py:
#
#   1) line_size
#   2) liner_material
#   3) electrode_material
#   4) process_connection
#   5) housing_material
#   6) output_signal
#   7) power_supply
#   8) area_classification
#   9) options
#
# Baseline: QPMAG-04-PT-SS-F1-C-1-1-C-00


BASELINE_PART_NUMBER = "QPMAG-04-PT-SS-F1-C-1-1-C-00"

BASELINE_SEGMENTS: List[Tuple[str, str]] = [
    ("model", "QPMAG"),
    ("line_size", "04"),
    ("liner_material", "PT"),
    ("electrode_material", "SS"),
    ("process_connection", "F1"),
    ("housing_material", "C"),
    ("output_signal", "1"),
    ("power_supply", "1"),
    ("area_classification", "C"),
    ("options", "00"),
]

DEFAULT_CODES: Dict[str, str] = {
    "line_size": "04",
    "liner_material": "PT",
    "electrode_material": "SS",
    "process_connection": "F1",
    "housing_material": "C",
    "output_signal": "1",
    "power_supply": "1",
    "area_classification": "C",
    "options": "00",
}


# --------------------------------------------------------------------------------------
# Natural-language rules
# --------------------------------------------------------------------------------------


NL_RULES: List[SegmentRule] = [
    # Liner material
    SegmentRule("liner_material", "PT", [r"\bptfe\b", r"\bteflon\b"], priority=8),
    SegmentRule("liner_material", "HR", [r"\bhard rubber\b", r"\brubber liner\b"], priority=7),
    SegmentRule("liner_material", "PU", [r"\bpolyurethane\b", r"\bpu liner\b"], priority=6),
    SegmentRule("liner_material", "PP", [r"\bpolypropylene\b", r"\bpp liner\b"], priority=6),

    # Electrode material
    SegmentRule("electrode_material", "SS", [r"\bstainless\b", r"\b316\b"], priority=5),
    SegmentRule("electrode_material", "HC", [r"\bhastelloy\b"], priority=7),
    SegmentRule("electrode_material", "TI", [r"\btitanium\b"], priority=8),

    # Process connection
    SegmentRule("process_connection", "F1", [r"\bwafer\b"], priority=7),
    SegmentRule("process_connection", "F2", [r"\bflange\b", r"\b150\s*class\b"], priority=7),
    SegmentRule("process_connection", "F3", [r"\b300\s*class\b"], priority=8),

    # Housing
    SegmentRule("housing_material", "S", [r"\bstainless housing\b", r"\bss housing\b"], priority=8),
    SegmentRule("housing_material", "C", [r"\bcoated aluminum\b", r"\baluminum housing\b"], priority=6),

    # Output signal
    SegmentRule(
        "output_signal",
        "1",
        [r"\b4\s*-\s*20\s*m?a?\b", r"\b4\s*to\s*20\s*m?a?\b", r"\bhart\b"],
        priority=7,
    ),
    SegmentRule("output_signal", "2", [r"\bpulse\b", r"\bfrequency output\b"], priority=8),
    SegmentRule("output_signal", "3", [r"\bmodbus\b", r"\bfieldbus\b", r"\bdigital output\b"], priority=9),

    # Power supply
    SegmentRule("power_supply", "1", [r"\b24\s*v\s*dc\b", r"\b24vdc\b", r"\bdc power\b"], priority=7),
    SegmentRule(
        "power_supply",
        "2",
        [r"\bac power\b", r"\b110v\b", r"\b120v\b", r"\b230v\b"],
        priority=8,
    ),

    # Area classification
    SegmentRule(
        "area_classification",
        "C",
        [r"\bgeneral purpose\b", r"\bnon[- ]hazardous\b", r"\bsafe area\b"],
        priority=4,
    ),
    SegmentRule(
        "area_classification",
        "D",
        [r"\bdivision\s*2\b", r"\bdiv\s*2\b", r"\bzone\s*2\b"],
        priority=7,
    ),
    SegmentRule(
        "area_classification",
        "E",
        [r"\bexplosion[\s-]*proof\b", r"\bxp\b", r"\bflameproof\b"],
        priority=9,
    ),

    # Options
    SegmentRule("options", "01", [r"\bgrounding rings\b"], priority=6),
    SegmentRule("options", "02", [r"\bgrounding electrodes\b"], priority=6),
    SegmentRule("options", "03", [r"\bgrounding rings\b.*\bgrounding electrodes\b"], priority=8),
]


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _apply_rule_table(text: str, rules: List[SegmentRule]) -> Dict[str, SegmentChoice]:
    normalized = _normalize(text)
    choices: Dict[str, SegmentChoice] = {}

    for rule in rules:
        for pattern in rule.patterns:
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                prev = choices.get(rule.segment)
                candidate = SegmentChoice(
                    segment=rule.segment,
                    code=rule.code,
                    reason=f"Matched pattern '{pattern}'",
                    priority=rule.priority,
                )
                if prev is None or candidate.priority >= prev.priority:
                    choices[rule.segment] = candidate
                break

    return choices


def _infer_line_size(text: str, choices: Dict[str, SegmentChoice], warnings: List[str]) -> None:
    """
    Infer line size from inches or DN notation and emit a warning if we
    need to round to the nearest catalog size.
    """
    normalized = _normalize(text)

    # Strip voltages
    normalized = re.sub(r"\b\d+\s*v(dc|ac)?\b", " ", normalized)
    normalized = re.sub(r"\b\d+\s*volt(s)?\b", " ", normalized)

    size_map: List[Tuple[float, str]] = [
        (1.0, "04"),
        (1.5, "06"),
        (2.0, "08"),
        (3.0, "10"),
        (4.0, "12"),
    ]

    inch_match = re.findall(
        r"(\d(?:\.\d+)?)\s*(?:\"|in\b|inch\b|inches\b)",
        normalized,
    )
    numeric_size: Optional[float] = None
    if inch_match:
        try:
            numeric_size = float(inch_match[0])
        except Exception:
            numeric_size = None

    if numeric_size is None:
        dn = re.search(r"\bdn(25|40|50|80|100)\b", normalized)
        if dn:
            numeric_size = {
                "25": 1.0,
                "40": 1.5,
                "50": 2.0,
                "80": 3.0,
                "100": 4.0,
            }[dn.group(1)]

    if numeric_size is None:
        return

    best_code: Optional[str] = None
    best_diff: Optional[float] = None
    best_size: Optional[float] = None
    for size, code in size_map:
        diff = abs(size - numeric_size)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_code = code
            best_size = size

    if best_code is None or best_size is None:
        return

    # Only warn if the requested size is not an exact catalog size.
    if abs(best_size - numeric_size) > 0.01:
        # If it is outside the catalog range, call that out explicitly.
        if numeric_size < min(s for s, _ in size_map) or numeric_size > max(
            s for s, _ in size_map
        ):
            warnings.append(
                f"Requested line size about {numeric_size:.1f} inch; "
                f"maximum catalog size is {max(s for s, _ in size_map):.1f} inch "
                f"(code {best_code}). Using closest size {best_size:.1f} inch (code {best_code})."
            )
        else:
            warnings.append(
                f"Requested line size about {numeric_size:.1f} inch; "
                f"using closest catalog size {best_size:.1f} inch (code {best_code})."
            )

    choices["line_size"] = SegmentChoice(
        segment="line_size",
        code=best_code,
        reason=f"Inferred line size ~{numeric_size} inch (using code {best_code}).",
        priority=100,
    )


def _build_segments_from_choices(
    description: str,
    rule_choices: Dict[str, SegmentChoice],
    warnings: List[str],
) -> Tuple[List[Tuple[str, str]], Dict[str, Dict[str, Any]], List[str], List[str]]:
    segment_explanations: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    _infer_line_size(description, rule_choices, warnings)

    final_segments: List[Tuple[str, str]] = []

    for seg_name, baseline in BASELINE_SEGMENTS:
        if seg_name == "model":
            final_code = baseline
            reason = "Model fixed by product selection (QPMAG)."
            source = "fixed"
        else:
            choice = rule_choices.get(seg_name)
            if choice:
                final_code = choice.code
                reason = choice.reason
                source = "nl"
            else:
                final_code = DEFAULT_CODES[seg_name]
                reason = "No explicit NL match; using default."
                source = "default"

        final_segments.append((seg_name, final_code))
        segment_explanations[seg_name] = {
            "code": final_code,
            "reason": reason,
            "source": source,
        }

    return final_segments, segment_explanations, errors, warnings


def _segments_to_part_number(segments: List[Tuple[str, str]]) -> str:
    return "-".join(code for _, code in segments)


# --------------------------------------------------------------------------------------
# Public interface
# --------------------------------------------------------------------------------------


def interpret_qpmag_description(description: str) -> Dict[str, Any]:
    """
    Convert a plain-English QPMAG request into a part number and explanations.

    Returns:
        {
            "success": bool,
            "part_number": str,
            "segments": {...},
            "errors": [...],
            "warnings": [...],
        }
    """
    description = (description or "").strip()
    warnings: List[str] = []

    if not description:
        final_segments, explanations, errors, warnings = _build_segments_from_choices(
            "",
            {},
            warnings,
        )
        return {
            "success": True,
            "part_number": _segments_to_part_number(final_segments),
            "segments": explanations,
            "errors": errors,
            "warnings": warnings,
        }

    rule_choices = _apply_rule_table(description, NL_RULES)
    final_segments, explanations, errors, warnings = _build_segments_from_choices(
        description,
        rule_choices,
        warnings,
    )

    return {
        "success": True,
        "part_number": _segments_to_part_number(final_segments),
        "segments": explanations,
        "errors": errors,
        "warnings": warnings,
    }
