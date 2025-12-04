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

# Safe defaults when NL says nothing
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
    SegmentRule(
        segment="liner_material",
        code="PT",  # PTFE
        patterns=[
            r"\bptfe\b",
            r"\bteflon\b",
        ],
        priority=8,
    ),
    SegmentRule(
        segment="liner_material",
        code="HR",  # hard rubber
        patterns=[
            r"\bhard rubber\b",
            r"\brubber liner\b",
        ],
        priority=7,
    ),
    SegmentRule(
        segment="liner_material",
        code="PU",  # polyurethane
        patterns=[
            r"\bpolyurethane\b",
            r"\bpu liner\b",
        ],
        priority=6,
    ),
    SegmentRule(
        segment="liner_material",
        code="PP",  # polypropylene
        patterns=[
            r"\bpolypropylene\b",
            r"\bpp liner\b",
        ],
        priority=6,
    ),

    # Electrode material
    SegmentRule(
        segment="electrode_material",
        code="SS",
        patterns=[
            r"\bstainless\b",
            r"\b316\b",
        ],
        priority=5,
    ),
    SegmentRule(
        segment="electrode_material",
        code="HC",
        patterns=[
            r"\bhastelloy\b",
        ],
        priority=7,
    ),
    SegmentRule(
        segment="electrode_material",
        code="TI",
        patterns=[
            r"\btitanium\b",
        ],
        priority=8,
    ),

    # Process connection
    SegmentRule(
        segment="process_connection",
        code="F1",
        patterns=[
            r"\bwafer\b",
        ],
        priority=7,
    ),
    SegmentRule(
        segment="process_connection",
        code="F2",
        patterns=[
            r"\bflange\b",
            r"\b150\s*class\b",
        ],
        priority=7,
    ),
    SegmentRule(
        segment="process_connection",
        code="F3",
        patterns=[
            r"\b300\s*class\b",
        ],
        priority=8,
    ),

    # Housing material
    SegmentRule(
        segment="housing_material",
        code="S",  # stainless
        patterns=[
            r"\bstainless housing\b",
            r"\bss housing\b",
        ],
        priority=8,
    ),
    SegmentRule(
        segment="housing_material",
        code="C",  # coated aluminum
        patterns=[
            r"\bcoated aluminum\b",
            r"\baluminum housing\b",
        ],
        priority=6,
    ),

    # Output signal
    SegmentRule(
        segment="output_signal",
        code="1",
        patterns=[
            r"\b4\s*-\s*20\s*m?a?\b",
            r"\b4\s*to\s*20\s*m?a?\b",
            r"\bhart\b",
        ],
        priority=7,
    ),
    SegmentRule(
        segment="output_signal",
        code="2",
        patterns=[
            r"\bpulse\b",
            r"\bfrequency output\b",
        ],
        priority=8,
    ),
    SegmentRule(
        segment="output_signal",
        code="3",
        patterns=[
            r"\bmodbus\b",
            r"\bfieldbus\b",
            r"\bdigital output\b",
        ],
        priority=9,
    ),

    # Power supply
    SegmentRule(
        segment="power_supply",
        code="1",  # 24 VDC
        patterns=[
            r"\b24\s*v\s*dc\b",
            r"\b24vdc\b",
            r"\bdc power\b",
        ],
        priority=7,
    ),
    SegmentRule(
        segment="power_supply",
        code="2",  # AC
        patterns=[
            r"\bac power\b",
            r"\b110v\b",
            r"\b120v\b",
            r"\b230v\b",
        ],
        priority=8,
    ),

    # Area classification
    SegmentRule(
        segment="area_classification",
        code="C",  # general purpose
        patterns=[
            r"\bgeneral purpose\b",
            r"\bnon[- ]hazardous\b",
        ],
        priority=4,
    ),
    SegmentRule(
        segment="area_classification",
        code="D",  # Div 2
        patterns=[
            r"\bdivision\s*2\b",
            r"\bdiv\s*2\b",
            r"\bzone\s*2\b",
        ],
        priority=7,
    ),
    SegmentRule(
        segment="area_classification",
        code="E",  # explosion-proof
        patterns=[
            r"\bexplosion[\s-]*proof\b",
            r"\bxp\b",
            r"\bflameproof\b",
        ],
        priority=9,
    ),

    # Options
    SegmentRule(
        segment="options",
        code="01",
        patterns=[
            r"\bgrounding rings\b",
        ],
        priority=6,
    ),
    SegmentRule(
        segment="options",
        code="02",
        patterns=[
            r"\bgrounding electrodes\b",
        ],
        priority=6,
    ),
    SegmentRule(
        segment="options",
        code="03",
        patterns=[
            r"\bgrounding rings\b.*\bgrounding electrodes\b",
        ],
        priority=8,
    ),
]


# --------------------------------------------------------------------------------------
# Helper functions
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
                reason = f"Matched pattern '{pattern}' for segment '{rule.segment}'"
                candidate = SegmentChoice(
                    segment=rule.segment,
                    code=rule.code,
                    reason=reason,
                    priority=rule.priority,
                )
                if prev is None or candidate.priority >= prev.priority:
                    choices[rule.segment] = candidate
                break

    return choices


def _infer_line_size(text: str, choices: Dict[str, SegmentChoice]) -> None:
    """
    Use numeric hints like '2 inch', '3"' or DN sizes to pick a line size.
    """
    normalized = _normalize(text)

    # Simple inch-based detection
    size_map = [
        (1.0, "04"),
        (1.5, "06"),
        (2.0, "08"),
        (3.0, "10"),
        (4.0, "12"),
    ]

    # Look for patterns like '2"', '2 in', '2 inch'
    inch_match = re.findall(r"(\d(?:\.\d)?)\s*(?:\"|in\b|inch\b)", normalized)
    numeric_size: Optional[float] = None
    if inch_match:
        try:
            numeric_size = float(inch_match[0])
        except ValueError:
            numeric_size = None

    # DN-based hints
    if numeric_size is None:
        dn_match = re.search(r"\bdn(25|40|50|80|100)\b", normalized)
        if dn_match:
            dn_val = dn_match.group(1)
            dn_map = {
                "25": 1.0,
                "40": 1.5,
                "50": 2.0,
                "80": 3.0,
                "100": 4.0,
            }
            numeric_size = dn_map.get(dn_val)

    if numeric_size is None:
        return

    # Pick closest size from size_map
    chosen_code = None
    best_diff = None
    for size_val, code in size_map:
        diff = abs(size_val - numeric_size)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            chosen_code = code

    if chosen_code:
        choices["line_size"] = SegmentChoice(
            segment="line_size",
            code=chosen_code,
            reason=f"Inferred line size ~{numeric_size} inch → code {chosen_code}",
            priority=100,
        )


def _build_segments_from_choices(
    description: str,
    rule_choices: Dict[str, SegmentChoice],
) -> Tuple[List[Tuple[str, str]], Dict[str, Dict[str, Any]], List[str]]:
    segment_explanations: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    _infer_line_size(description, rule_choices)

    final_segments: List[Tuple[str, str]] = []

    for seg_name, baseline_code in BASELINE_SEGMENTS:
        if seg_name == "model":
            final_code = baseline_code
            reason = "Model fixed by product selection (QPMAG)."
            source = "fixed"
        else:
            choice = rule_choices.get(seg_name)
            if choice:
                final_code = choice.code
                reason = choice.reason
                source = "nl"
            else:
                final_code = DEFAULT_CODES.get(seg_name, baseline_code)
                if final_code != baseline_code:
                    reason = f"No explicit NL match; using segment default '{final_code}'."
                    source = "default"
                else:
                    reason = "No explicit NL match; using baseline code."
                    source = "baseline"

        final_segments.append((seg_name, final_code))
        segment_explanations[seg_name] = {
            "code": final_code,
            "reason": reason,
            "source": source,
        }

    return final_segments, segment_explanations, errors


def _segments_to_part_number(segments: List[Tuple[str, str]]) -> str:
    codes = [code for _, code in segments]
    return "-".join(codes)


# --------------------------------------------------------------------------------------
# Public interface
# --------------------------------------------------------------------------------------


def interpret_qpmag_description(description: str) -> Dict[str, Any]:
    """
    Convert a plain-English QPMAG request into a part number and segment explanations.

    Returns:
        {
            "success": bool,
            "part_number": str,
            "segments": {segment_name: {...}},
            "errors": [str, ...],
        }
    """
    description = (description or "").strip()

    if not description:
        final_segments, segment_explanations, errors = _build_segments_from_choices(
            description="", rule_choices={}
        )
        part_number = _segments_to_part_number(final_segments)
        return {
            "success": True,
            "part_number": part_number,
            "segments": segment_explanations,
            "errors": errors,
        }

    rule_choices = _apply_rule_table(description, NL_RULES)
    final_segments, segment_explanations, errors = _build_segments_from_choices(
        description=description,
        rule_choices=rule_choices,
    )
    part_number = _segments_to_part_number(final_segments)
    success = len(errors) == 0

    return {
        "success": success,
        "part_number": part_number,
        "segments": segment_explanations,
        "errors": errors,
    }
