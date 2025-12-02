from typing import Any, Dict

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


@register_engine("QPSAH200S")
class QPSAH200SEngine(PartNumberEngine):
    """
    Engine for QPSAH200S using MASTER_SEGMENTS.

    Public interface:
        quote(part_number: str) -> Dict[str, Any]
    """

    model = "QPSAH200S"

    def __init__(self) -> None:
        self.base_price = BASE_PRICE
        self.master_segments = MASTER_SEGMENTS

    def _parse(self, part_number: str) -> Dict[str, Any]:
        if not part_number:
            raise PartNumberError(
                "Part number is required.",
                segment="model",
                invalid_code=None,
                valid_codes=[self.model],
            )

        raw = part_number.strip().upper()
        pieces = raw.split("-")

        # Expect model + 11 segments
        if len(pieces) != 12:
            raise PartNumberError(
                f"Expected 12 segments including model, got {len(pieces)}.",
                segment="model",
                invalid_code=raw,
                valid_codes=[self.model],
            )

        model_code = pieces[0]
        if model_code != self.model:
            raise PartNumberError(
                f"Invalid model [{model_code}].",
                segment="model",
                invalid_code=model_code,
                valid_codes=[self.model],
            )

        segment_codes = pieces[1:]

        segments_output: Dict[str, Any] = {}
        total_adders = 0.0

        for index, code in enumerate(segment_codes, start=1):
            seg_def = self.master_segments[index]
            seg_key = seg_def["key"]
            seg_name = seg_def["name"]
            options = seg_def["options"]

            if code not in options:
                raise PartNumberError(
                    f"Invalid code [{code}] for segment [{seg_name}]. "
                    f"Valid options are: {', '.join(options.keys())}",
                    segment=seg_name,
                    invalid_code=code,
                    valid_codes=list(options.keys()),
                )

            opt = options[code]
            adder = float(opt.get("adder", 0.0))
            total_adders += adder

            segments_output[seg_key] = {
                "code": code,
                "description": opt.get("description", ""),
                "adder": adder,
                "default": bool(opt.get("default", False)),
            }

        final_price = self.base_price + total_adders

        return {
            "model": self.model,
            "part_number": part_number,
            "base_price": self.base_price,
            "total_adders": total_adders,
            "final_price": final_price,
            "segments": segments_output,
        }

    def quote(self, part_number: str) -> Dict[str, Any]:
        result = self._parse(part_number)
        result["success"] = True
        return result
