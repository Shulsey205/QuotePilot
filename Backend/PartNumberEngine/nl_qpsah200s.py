# Backend/PartNumberEngine/nl_qpsah200s.py

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
            r"\bfoundation\b.*\bfieldbus\b",
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

    # Span range (M/H) - textual hints. Numeric ranges are handled separately.
    SegmentRule(
        segment="span_range",
        code="M",
        patterns=[
            r"\blow(?:\s+range|\s+pressure)?\b",
            r"\bmedium(?:\s+range|\s+pressure)?\b",
        ],
        priority=5,
    ),
    SegmentRule(
        segment="span_range",
        code="H",
        patterns=[
            r"\bhigh(?:\s+range|\s+pressure)?\b",
            r"\bwide\s+range\b",
        ],
        priority=6,
    ),

    # Wetted parts (G/A/D)
    SegmentRule(
        segment="wetted_parts_material",
        code="G",  # 316 SS
        patterns=[
            r"\bstainless\b",
            r"\b316\b",
            r"\bss\s+wetted\b",
        ],
        priority=5,
    ),
    SegmentRule(
        segment="wetted_parts_material",
        code="A",  # Hastelloy
        patterns=[
            r"\bhastelloy\b",
            r"\bhc\b\s*wetted\b",
        ],
        priority=6,
    ),
    SegmentRule(
        segment="wetted_parts_material",
        code="D",  # Titanium
        patterns=[
            r"\btitanium\b",
            r"\bti\s*wetted\b",
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
            r"\bwith local\b",
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
            r"\bremote\b\s*mount\b",
        ],
        priority=6,
    ),

    # Mounting bracket (C/A/B)
    SegmentRule(
        segment="mounting_bracket",
        code="C",
        patterns=[
            r"\buniversal bracket\b",
            r"\bpipe\b.*\bmount\b",
            r"\bwall\b.*\bmount\b",
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
            r"\bsafe area\b",
        ],
        priority=3,
    ),
    SegmentRule(
        segment="area_classification",
        code="2",  # explosion proof
        patterns=[
            r"\bexplosion[\s-]*proof\b",
            r"\bxp\b",
            r"\bflameproof\b",
        ],
        priority=10,
    ),
    SegmentRule(
        segment="area_classification",
        code="3",  # Class I Div 2
        patterns=[
            r"\bclass\s*i\b.*\bdiv\s*2\b",
            r"\bcl\s*1\s*div\s*2\b",
            r"\bclass\s*1\s*division\s*2\b",
            r"\bzone\s*2\b",
        ],
        priority=9,
    ),
    SegmentRule(
        segment="area_classification",
        code="4",  # Canadian / CSA
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


def _extract_span_numeric_value(text: str) -> Optional[float]:
    """
    Try to extract a span max value from the text while ignoring
    non-span numbers such as:
      - 4-20 mA
      - 24 VDC, 120 VAC, etc.
      - Class 1 Div 2
    Returns the best-guess max span value in inWC (or generic units).
    """
    normalized = _normalize(text)

    # Remove obvious non-span numeric patterns up front
    # 4-20 mA / 4 to 20 mA
    normalized = re.sub(r"\b4\s*[-to]+\s*20\s*m?a?\b", " ", normalized)
    # Voltages
    normalized = re.sub(r"\b\d+\s*v(dc|ac)?\b", " ", normalized)
    normalized = re.sub(r"\b\d+\s*volt(s)?\b", " ", normalized)
    # Class/Division markers
    normalized = re.sub(r"\bclass\s*\d+\b", " ", normalized)
    normalized = re.sub(r"\bdiv(ision)?\s*\d+\b", " ", normalized)
    normalized = re.sub(r"\bzone\s*\d+\b", " ", normalized)

    # Ranges like "0-150 in", "0 to 300 in wc"
    range_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*[-to]+\s*(\d+(?:\.\d+)?)(?:\s*(in(?:ch(?:es)?)?|inwc|in\s*wc|\"))?",
        normalized,
    )
    candidates: List[float] = []

    for low_str, high_str, _unit in range_matches:
        try:
            low = float(low_str)
            high = float(high_str)
        except ValueError:
            continue
        # Guard against obviously non-span ranges such as 1-2, 2-3
        if high <= 5:
            continue
        candidates.append(high)

    # Standalone numbers followed by in/inwc etc,
    # like "150 in wc", "250 inwc", "400 inches of water"
    single_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*(in(?:ch(?:es)?)?(?:\s*of\s*water)?|inwc|in\s*wc|\"|iwc)",
        normalized,
    )
    for value_str, _unit in single_matches:
        try:
            value = float(value_str)
        except ValueError:
            continue
        if value <= 5:
            continue
        candidates.append(value)

    if not candidates:
        return None

    return max(candidates)


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
    warnings: List[str],
) -> None:
    """
    Use the numeric span (if any) to force M vs H and optionally
    emit a warning when the requested span exceeds catalog limits.
    """
    span_max = _extract_span_numeric_value(text)
    if span_max is None:
        return

    # Catalog limit = 1000 inWC (code H). Anything above that is clamped.
    if span_max > 1000:
        warnings.append(
            f"Requested span up to about {span_max:g} inWC; "
            "maximum catalog span is 1000 inWC (code H). Using H (400–1000 inWC)."
        )

    if span_max > 400:
        choices["span_range"] = SegmentChoice(
            segment="span_range",
            code="H",
            reason=f"Inferred span up to {span_max:g} > 400, using high span (H).",
            priority=100,
        )
    else:
        # Medium range for anything up to and including 400
        existing = choices.get("span_range")
        candidate = SegmentChoice(
            segment="span_range",
            code="M",
            reason=f"Inferred span up to {span_max:g} ≤ 400, using medium span (M).",
            priority=90,
        )
        if existing is None or candidate.priority >= existing.priority:
            choices["span_range"] = candidate


def _build_segments_from_choices(
    description: str,
    rule_choices: Dict[str, SegmentChoice],
    warnings: List[str],
) -> Tuple[List[Tuple[str, str]], Dict[str, Dict[str, Any]], List[str]]:
    segment_explanations: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    # Apply numeric span logic (and possible warnings)
    _apply_span_numeric_hint(description, rule_choices, warnings)

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
    """
    Convert a plain-English QPSAH200S request into a part number and segment explanations.

    Returns:
        {
            "success": bool,
            "part_number": str,
            "segments": {segment_name: {...}},
            "errors": [str, ...],
            "warnings": [str, ...],
        }
    """
    description = (description or "").strip()
    warnings: List[str] = []

    if not description:
        final_segments, segment_explanations, errors = _build_segments_from_choices(
            description="",
            rule_choices={},
            warnings=warnings,
        )
        part_number = _segments_to_part_number(final_segments)
        return {
            "success": True,
            "part_number": part_number,
            "segments": segment_explanations,
            "errors": errors,
            "warnings": warnings,
        }

    rule_choices = _apply_rule_table(description, NL_RULES)
    final_segments, segment_explanations, errors = _build_segments_from_choices(
        description=description,
        rule_choices=rule_choices,
        warnings=warnings,
    )
    part_number = _segments_to_part_number(final_segments)
    success = len(errors) == 0

    return {
        "success": success,
        "part_number": part_number,
        "segments": segment_explanations,
        "errors": errors,
        "warnings": warnings,
    }
