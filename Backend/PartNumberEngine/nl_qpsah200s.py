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
    priority: int = 0  # higher number wins when conflicts happen


# --------------------------------------------------------------------------------------
# Baseline configuration for QPSAH200S
# --------------------------------------------------------------------------------------
# Must match MASTER_SEGMENTS in dp_qpsah200s.py:
#
#   1  output_signal_type
#   2  span_range
#   3  wetted_parts_material
#   4  process_connection
#   5  housing_material
#   6  installation_orientation
#   7  electrical_connection
#   8  display
#   9  mounting_bracket
#   10 area_classification
#   11 optional_features
#
# Baseline: QPSAH200S-A-M-G-3-C-3-1-1-C-1-02


BASELINE_PART_NUMBER = "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02"

BASELINE_SEGMENTS: List[Tuple[str, str]] = [
    ("model", "QPSAH200S"),
    ("output_signal_type", "A"),
    ("span_range", "M"),
    ("wetted_parts_material", "G"),
    ("process_connection", "3"),
    ("housing_material", "C"),
    ("installation_orientation", "3"),
    ("electrical_connection", "1"),
    ("display", "1"),
    ("mounting_bracket", "C"),
    ("area_classification", "1"),
    ("optional_features", "02"),
]

# Safe defaults when NL says nothing
DEFAULT_CODES: Dict[str, str] = {
    "output_signal_type": "A",
    "span_range": "M",
    "wetted_parts_material": "G",
    "process_connection": "3",
    "housing_material": "C",
    "installation_orientation": "3",
    "electrical_connection": "1",
    "display": "1",           # With display (matches engine)
    "mounting_bracket": "C",  # Universal bracket
    "area_classification": "1",  # General purpose
    "optional_features": "02",   # Memory card
}


# --------------------------------------------------------------------------------------
# Natural-language rules
# --------------------------------------------------------------------------------------


NL_RULES: List[SegmentRule] = [
    # Output signal type (A/B/C)
    SegmentRule(
        segment="output_signal_type",
        code="A",
        patterns=[
            r"\b4\s*-\s*20\s*m?a?\b",
            r"\b4\s*to\s*20\s*m?a?\b",
            r"\banalog\b",
            r"\bcurrent loop\b",
            r"\bhart\b",
        ],
        priority=5,
    ),
    SegmentRule(
        segment="output_signal_type",
        code="B",  # Fieldbus
        patterns=[
            r"\bfieldbus\b",
        ],
        priority=10,
    ),
    SegmentRule(
        segment="output_signal_type",
        code="C",  # Profibus
        patterns=[
            r"\bprofibus\b",
        ],
        priority=10,
    ),

    # Span range (M/H)
    SegmentRule(
        segment="span_range",
        code="M",
        patterns=[
            r"\blow(?:\s+range|\s+pressure)?\b",
            r"\b0\s*-\s*150\b",
            r"\b0\s*-\s*200\b",
            r"\b0\s*-\s*300\b",
            r"\b0\s*-\s*400\b",
        ],
        priority=5,
    ),
    SegmentRule(
        segment="span_range",
        code="H",
        patterns=[
            r"\bhigh(?:\s+range|\s+pressure)?\b",
            r"\b400\s*in",
            r"\b500\s*in",
            r"\b1000\s*in",
        ],
        priority=6,
    ),

    # Wetted parts (G/A/B/D)
    SegmentRule(
        segment="wetted_parts_material",
        code="G",  # 316 SS
        patterns=[
            r"\bstainless\b",
            r"\b316\b",
        ],
        priority=5,
    ),
    SegmentRule(
        segment="wetted_parts_material",
        code="A",  # Hastelloy
        patterns=[
            r"\bhastelloy\b",
        ],
        priority=6,
    ),
    SegmentRule(
        segment="wetted_parts_material",
        code="D",  # Titanium
        patterns=[
            r"\btitanium\b",
        ],
        priority=7,
    ),

    # Housing (C/B/A)
    SegmentRule(
        segment="housing_material",
        code="C",  # 316 SS housing
        patterns=[
            r"\bstainless housing\b",
            r"\b316\s+housing\b",
            r"\bss housing\b",
        ],
        priority=7,
    ),
    SegmentRule(
        segment="housing_material",
        code="B",  # aluminum with coating
        patterns=[
            r"\bcorrosion[- ]?resistant\b",
            r"\bcoated aluminum housing\b",
        ],
        priority=6,
    ),
    SegmentRule(
        segment="housing_material",
        code="A",  # plain aluminum
        patterns=[
            r"\baluminum housing\b",
            r"\bcast aluminum\b",
        ],
        priority=5,
    ),

    # Display (1 = with, 0 = without)
    SegmentRule(
        segment="display",
        code="1",  # with display
        patterns=[
            r"\bdisplay\b",
            r"\blocal indicator\b",
            r"\bdigital readout\b",
            r"\bgauge face\b",
            r"\bwith display\b",
        ],
        priority=5,
    ),
    SegmentRule(
        segment="display",
        code="0",  # without display
        patterns=[
            r"\bno\s+display\b",
            r"\bwithout display\b",
            r"\bblind\b",
            r"\bhead only\b",
        ],
        priority=6,
    ),

    # Mounting bracket (C/A/B)
    SegmentRule(
        segment="mounting_bracket",
        code="C",
        patterns=[
            r"\buniversal bracket\b",
        ],
        priority=4,
    ),
    SegmentRule(
        segment="mounting_bracket",
        code="A",
        patterns=[
            r"\b304\b.*\bbracket\b",
        ],
        priority=5,
    ),
    SegmentRule(
        segment="mounting_bracket",
        code="B",
        patterns=[
            r"\b316\b.*\bbracket\b",
        ],
        priority=6,
    ),

    # Area classification (1/2/3/4)
    SegmentRule(
        segment="area_classification",
        code="1",  # general purpose
        patterns=[
            r"\bgeneral purpose\b",
            r"\bnon[- ]hazardous\b",
        ],
        priority=3,
    ),
    SegmentRule(
        segment="area_classification",
        code="2",  # explosion proof
        patterns=[
            r"\bexplosion[\s-]*proof\b",
            r"\bxp\b",
        ],
        priority=10,
    ),
    SegmentRule(
        segment="area_classification",
        code="3",  # Class I Div 2
        patterns=[
            r"\bclass\s*i\b.*\bdiv\s*2\b",
            r"\bcl1\s*div2\b",
            r"\bclass\s*1\s*division\s*2\b",
        ],
        priority=9,
    ),
    SegmentRule(
        segment="area_classification",
        code="4",  # Canadian
        patterns=[
            r"\bcanadian\b",
            r"\bcsa\b",
        ],
        priority=8,
    ),
]


# --------------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _extract_max_numeric_value(text: str) -> Optional[float]:
    numbers = re.findall(r"[-+]?\d*\.?\d+", text)
    values: List[float] = []
    for n in numbers:
        try:
            values.append(float(n))
        except ValueError:
            continue
    return max(values) if values else None


def _apply_rule_table(
    text: str,
    rules: List[SegmentRule],
) -> Dict[str, SegmentChoice]:
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


def _apply_span_numeric_hint(
    text: str,
    choices: Dict[str, SegmentChoice],
) -> None:
    max_val = _extract_max_numeric_value(text)
    if max_val is None:
        return

    if max_val > 400:
        choices["span_range"] = SegmentChoice(
            segment="span_range",
            code="H",
            reason=f"Max numeric value {max_val} > 400, using high span (H)",
            priority=100,
        )
    else:
        if "span_range" not in choices:
            choices["span_range"] = SegmentChoice(
                segment="span_range",
                code="M",
                reason=f"Max numeric value {max_val} ≤ 400, using medium span (M)",
                priority=90,
            )


def _build_segments_from_choices(
    description: str,
    rule_choices: Dict[str, SegmentChoice],
) -> Tuple[List[Tuple[str, str]], Dict[str, Dict[str, Any]], List[str]]:
    segment_explanations: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    _apply_span_numeric_hint(description, rule_choices)

    final_segments: List[Tuple[str, str]] = []

    for seg_name, baseline_code in BASELINE_SEGMENTS:
        if seg_name == "model":
            final_code = baseline_code
            reason = "Model fixed by product selection (QPSAH200S)."
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


def interpret_qpsah200s_description(description: str) -> Dict[str, Any]:
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
