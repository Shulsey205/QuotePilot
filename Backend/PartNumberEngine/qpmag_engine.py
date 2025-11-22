from typing import Any, Dict, List

from .base_engine import PartNumberEngine, PartNumberError, register_engine


BASE_PRICE = 2500.0


# Master segment definition for QPMAG magnetic flowmeter
MASTER_SEGMENTS_MAG: Dict[int, Dict[str, Any]] = {
    1: {
        "key": "line_size",
        "name": "Line size",
        "options": {
            "1": {"description": '1 inch line size', "adder": 0.0},
            "2": {"description": '2 inch line size', "adder": 150.0},
            "3": {"description": '3 inch line size', "adder": 250.0},
            "4": {"description": '4 inch line size', "adder": 350.0},
            "6": {"description": '6 inch line size', "adder": 500.0},
        },
    },
    2: {
        "key": "body_material",
        "name": "Body material",
        "options": {
            "C": {"description": "Carbon steel", "adder": 0.0},
            "S": {"description": "304 stainless steel", "adder": 250.0},
            "H": {"description": "316 stainless steel", "adder": 400.0},
        },
    },
    3: {
        "key": "liner",
        "name": "Liner material",
        "options": {
            "SR": {"description": "Soft rubber", "adder": 0.0},
            "HR": {"description": "Hard rubber", "adder": 75.0},
            "PTFE": {"description": "PTFE liner", "adder": 250.0},
            "PFA": {"description": "PFA liner", "adder": 350.0},
        },
    },
    4: {
        "key": "electrodes",
        "name": "Electrode material",
        "options": {
            "316": {"description": "316 stainless", "adder": 0.0},
            "HC": {"description": "Hastelloy C", "adder": 300.0},
            "TI": {"description": "Titanium", "adder": 350.0},
        },
    },
    5: {
        "key": "process_connection",
        "name": "Process connection",
        "options": {
            "150": {"description": "150 lb flanges", "adder": 0.0},
            "300": {"description": "300 lb flanges", "adder": 250.0},
            "WA": {"description": "Wafer style", "adder": 100.0},
        },
    },
    6: {
        "key": "grounding_rings",
        "name": "Grounding rings",
        "options": {
            "R": {"description": "No grounding rings", "adder": 0.0},
            "G": {"description": "Grounding rings included", "adder": 150.0},
        },
    },
    7: {
        "key": "output",
        "name": "Output signal",
        "options": {
            "4": {"description": "4–20 mA + pulse", "adder": 0.0},
            "2": {"description": "4–20 mA only", "adder": 0.0},
            "H": {"description": "HART digital", "adder": 150.0},
            "F": {"description": "Foundation Fieldbus", "adder": 200.0},
        },
    },
    8: {
        "key": "approvals",
        "name": "Approvals",
        "options": {
            "0": {"description": "General purpose", "adder": 0.0},
            "1": {"description": "Non-incendive", "adder": 150.0},
            "2": {"description": "Hazardous location approvals", "adder": 300.0},
        },
    },
    9: {
        "key": "cable_length",
        "name": "Cable length",
        "options": {
            "00": {"description": "Integral mount", "adder": 0.0},
            "10": {"description": "10 meter remote cable", "adder": 100.0},
            "20": {"description": "20 meter remote cable", "adder": 175.0},
        },
    },
    10: {
        "key": "options",
        "name": "Options",
        "options": {
            "00": {"description": "No options", "adder": 0.0},
            "HC": {"description": "Electrode cleaning", "adder": 150.0},
            "DI": {"description": "Extra digital output", "adder": 75.0},
        },
    },
}


# Convert to engine-friendly layout (same pattern as your DP engine)
SEGMENTS_MAG: List[Dict[str, Any]] = [
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
    for index, seg in sorted(MASTER_SEGMENTS_MAG.items())
]


@register_engine
class QPMAGEngine(PartNumberEngine):

    model = "QPMAG"

    def quote(self, part_number: str) -> Dict[str, Any]:

        if not part_number or not isinstance(part_number, str):
            raise PartNumberError(
                "Part number must be a non-empty string",
                segment="Part number",
                invalid_code=str(part_number),
            )

        raw = part_number.strip()
        parts = raw.split("-")

        expected_segments = 1 + len(SEGMENTS_MAG)

        if len(parts) != expected_segments:
            raise PartNumberError(
                f"Expected {len(SEGMENTS_MAG)} segments after model, got {len(parts) - 1}",
                segment="Structure",
                invalid_code=raw,
            )

        model_code = parts[0]
        segment_codes = parts[1:]

        if model_code.upper() != "QPMAG":
            raise PartNumberError(
                f"Invalid model [{model_code}], expected [QPMAG]",
                segment="Model",
                invalid_code=model_code,
                valid_codes=["QPMAG"],
            )

        adders_total = 0.0
        segment_breakdown: List[Dict[str, Any]] = []

        for seg_def, code in zip(SEGMENTS_MAG, segment_codes):

            seg_name = seg_def["name"]
            codes_map = seg_def["codes"]

            if code not in codes_map:
                raise PartNumberError(
                    f"Invalid code [{code}] for segment [{seg_name}]",
                    segment=seg_name,
                    invalid_code=code,
                    valid_codes=list(codes_map.keys()),
                )

            info = codes_map[code]
            adder = info["adder"]

            segment_breakdown.append(
                {
                    "segment_index": seg_def["index"],
                    "segment_name": seg_name,
                    "code": code,
                    "description": info["description"],
                    "adder": adder,
                }
            )

            adders_total += adder

        final_price = BASE_PRICE + adders_total

        normalized = "-".join([self.model] + segment_codes)

        return {
            "model": self.model,
            "input_part_number": raw,
            "normalized_part_number": normalized,
            "segments": segment_breakdown,
            "base_price": BASE_PRICE,
            "adders_total": adders_total,
            "final_price": final_price,
        }
