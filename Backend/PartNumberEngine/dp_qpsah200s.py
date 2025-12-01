from typing import Any, Dict, List

from .base_engine import PartNumberEngine, PartNumberError, register_engine


BASE_PRICE = 1000.0


# Master definition of all segments, options, and pricing for QPSAH200S.
# This matches your combined spec + pricing PDF, with updated span range options.
MASTER_SEGMENTS: Dict[int, Dict[str, Any]] = {
    1: {
        "key": "output_signal_type",
        "name": "Output signal type",
        "options": {
            "A": {
                "description": "HART communication with 4–20 mA analog signal",
                "adder": 0.0,
                "default": True,
            },
            "B": {
                "description": "Fieldbus digital communication",
                "adder": 150.0,
                "default": False,
            },
            "C": {
                "description": "Profibus digital communication",
                "adder": 150.0,
                "default": False,
            },
        },
    },
    2: {
        "key": "span_range",
        "name": "Span range",
        "options": {
            "M": {
                "description": "0 to 400 inches of water column",
                "adder": 0.0,
                "default": True,
            },
            "H": {
                "description": "400 to 1000 inches of water column",
                "adder": 200.0,
                "default": False,
            },
        },
    },
    3: {
        "key": "wetted_parts_material",
        "name": "Wetted parts material",
        "options": {
            "G": {
                "description": "316 stainless steel wetted parts",
                "adder": 0.0,
                "default": True,
            },
            "A": {
                "description": "Hastelloy wetted parts",
                "adder": 200.0,
                "default": False,
            },
            "B": {
                "description": "Cover flange material",
                "adder": 50.0,
                "default": False,
            },
            "D": {
                "description": "Titanium wetted parts",
                "adder": 300.0,
                "default": False,
            },
        },
    },
    4: {
        "key": "process_connection",
        "name": "Process connection",
        "options": {
            "3": {
                "description": "1/2 inch NPT female process connection",
                "adder": 0.0,
                "default": True,
            },
            "2": {
                "description": "1/4 inch NPT female process connection",
                "adder": 0.0,
                "default": False,
            },
            "1": {
                "description": "No process connection",
                "adder": 0.0,
                "default": False,
            },
        },
    },
    5: {
        "key": "housing_material",
        "name": "Housing material",
        "options": {
            "C": {
                "description": "316 stainless steel housing",
                "adder": 0.0,
                "default": True,
            },
            "B": {
                "description": "Cast aluminum alloy with corrosion resistance",
                "adder": 100.0,
                "default": False,
            },
            "A": {
                "description": "Cast aluminum housing",
                "adder": 0.0,
                "default": False,
            },
        },
    },
    6: {
        "key": "installation_orientation",
        "name": "Installation orientation",
        "options": {
            "3": {
                "description": "Universal flange installation",
                "adder": 0.0,
                "default": True,
            },
            "1": {
                "description": "Horizontal installation",
                "adder": 0.0,
                "default": False,
            },
            "2": {
                "description": "Vertical installation",
                "adder": 0.0,
                "default": False,
            },
            "4": {
                "description": "Vertical with left side high pressure",
                "adder": 50.0,
                "default": False,
            },
        },
    },
    7: {
        "key": "electrical_connection",
        "name": "Electrical connection",
        "options": {
            "1": {
                "description": "1/2 inch NPT female electrical connection",
                "adder": 0.0,
                "default": True,
            },
            "2": {
                "description": "G 1/2 inch female electrical connection",
                "adder": 50.0,
                "default": False,
            },
            "3": {
                "description": "1/4 inch NPT female electrical connection",
                "adder": 0.0,
                "default": False,
            },
        },
    },
    8: {
        "key": "display",
        "name": "Display",
        "options": {
            "1": {
                "description": "With display",
                "adder": 0.0,
                "default": True,
            },
            "0": {
                "description": "Without display",
                "adder": 0.0,
                "default": False,
            },
        },
    },
    9: {
        "key": "mounting_bracket",
        "name": "Mounting bracket",
        "options": {
            "C": {
                "description": "Universal bracket",
                "adder": 0.0,
                "default": True,
            },
            "A": {
                "description": "304 stainless bracket",
                "adder": 0.0,
                "default": False,
            },
            "B": {
                "description": "316 stainless bracket",
                "adder": 50.0,
                "default": False,
            },
        },
    },
    10: {
        "key": "area_classification",
        "name": "Area classification",
        "options": {
            "1": {
                "description": "General purpose",
                "adder": 0.0,
                "default": True,
            },
            "2": {
                "description": "Explosion proof",
                "adder": 200.0,
                "default": False,
            },
            "3": {
                "description": "Class I Div 2",
                "adder": 150.0,
                "default": False,
            },
            "4": {
                "description": "Canadian specifications",
                "adder": 100.0,
                "default": False,
            },
        },
    },
    11: {
        "key": "optional_features",
        "name": "Optional features",
        "options": {
            "02": {
                "description": "Memory card",
                "adder": 0.0,
                "default": True,
            },
            "01": {
                "description": "Signal cable",
                "adder": 50.0,
                "default": False,
            },
            "03": {
                "description": "High corrosion resistance coating",
                "adder": 150.0,
                "default": False,
            },
            "04": {
                "description": "Unlimited software updates",
                "adder": 200.0,
                "default": False,
            },
        },
    },
}


# Derived list structure used by the engine logic below
SEGMENTS: List[Dict[str, Any]] = [
    {
        "index": index,
        "name": seg["name"],
        "codes": {
            code: {
                "description": opt["description"],
                "adder": float(opt["adder"]),
            }
            for code, opt in seg["options"].items()
        },
    }
    for index, seg in sorted(MASTER_SEGMENTS.items())
]


@register_engine
class QPSAH200SEngine(PartNumberEngine):
    """
    Engine for QPSAH200S differential pressure transmitter.

    Responsibilities:
      - Parse the part number into segments
      - Validate each segment code
      - Calculate pricing (base price + adders)
      - Return a structured result for the API/UI
    """

    model = "QPSAH200S"

    def quote(self, part_number: str) -> Dict[str, Any]:
        if not part_number or not isinstance(part_number, str):
            raise PartNumberError(
                "Part number must be a non-empty string",
                segment="Part number",
                invalid_code=str(part_number),
            )

        # Keep the raw input
        input_part_number = part_number.strip()

        # Split on hyphens
        parts = input_part_number.split("-")

        # Expect: model + 11 segments
        if len(parts) != 12:
            raise PartNumberError(
                f"Expected 11 segments after the model, got {len(parts) - 1}",
                segment="Part number structure",
                invalid_code=input_part_number,
            )

        model_code = parts[0]
        segment_codes = parts[1:]

        if model_code != self.model:
            raise PartNumberError(
                f"Invalid model [{model_code}]. Expected [{self.model}]",
                segment="Model",
                invalid_code=model_code,
                valid_codes=[self.model],
            )

        segment_breakdown: List[Dict[str, Any]] = []
        adders_total = 0.0

        # Validate each segment against SEGMENTS definition
        for seg_def, code in zip(SEGMENTS, segment_codes):
            seg_name = seg_def["name"]
            codes_map = seg_def["codes"]

            # Segment 11 uses codes like "02" which we keep as-is
            if code not in codes_map:
                valid_codes = list(codes_map.keys())
                raise PartNumberError(
                    f"Invalid code [{code}] for segment [{seg_name}]. "
                    f"Valid options are: {', '.join(valid_codes)}",
                    segment=seg_name,
                    invalid_code=code,
                    valid_codes=valid_codes,
                )

            info = codes_map[code]
            description = info["description"]
            adder = float(info["adder"])

            segment_breakdown.append(
                {
                    "segment_index": seg_def["index"],
                    "segment_name": seg_name,
                    "code": code,
                    "description": description,
                    "adder": adder,
                }
            )
            adders_total += adder

        final_price = BASE_PRICE + adders_total

        # Normalized part number: reassembled from parsed pieces
        normalized_part_number = "-".join([self.model] + segment_codes)

        return {
            "model": self.model,
            "input_part_number": input_part_number,
            "normalized_part_number": normalized_part_number,
            "segments": segment_breakdown,
            "base_price": BASE_PRICE,
            "adders_total": adders_total,
            "final_price": final_price,
        }
