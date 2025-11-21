from typing import Any, Dict, List

from .base_engine import PartNumberEngine, PartNumberError


BASE_PRICE = 1000.0


# Segment metadata and pricing rules for QPSAH200S
# Order matters: index 0 = Segment 1, index 10 = Segment 11.
SEGMENTS: List[Dict[str, Any]] = [
    {
        "index": 1,
        "name": "Output signal type",
        "codes": {
            # Spec + pricing: A baseline, B/C +150
            "A": {"description": "HART communication with 4–20 mA analog signal", "adder": 0.0},
            "B": {"description": "Fieldbus digital communication", "adder": 150.0},
            "C": {"description": "Profibus digital communication", "adder": 150.0},
        },
    },
    {
        "index": 2,
        "name": "Span range",
        "codes": {
            # Pricing: M baseline, others add
            "M": {"description": "4 to 400 inches of water column", "adder": 0.0},
            "L": {"description": "2 to 40 inches of water column", "adder": 100.0},
            "D": {"description": "2 to 20 inches of water column", "adder": 150.0},
            "F": {"description": "20 to 2000 inches of water column", "adder": 200.0},
        },
    },
    {
        "index": 3,
        "name": "Wetted parts material",
        "codes": {
            # Pricing: G baseline
            "G": {"description": "316 stainless steel wetted parts", "adder": 0.0},
            "A": {"description": "Hastelloy wetted parts", "adder": 200.0},
            "B": {"description": "Cover flange material", "adder": 50.0},
            "D": {"description": "Titanium wetted parts", "adder": 300.0},
        },
    },
    {
        "index": 4,
        "name": "Process connection",
        "codes": {
            # Pricing: 3 baseline, 1/2 zero
            "3": {"description": "1/2 inch NPT female process connection", "adder": 0.0},
            "2": {"description": "1/4 inch NPT female process connection", "adder": 0.0},
            "1": {"description": "No process connection", "adder": 0.0},
        },
    },
    {
        "index": 5,
        "name": "Housing material",
        "codes": {
            # Pricing: C baseline
            "C": {"description": "316 stainless steel housing", "adder": 0.0},
            "B": {"description": "Cast aluminum alloy with corrosion resistance", "adder": 100.0},
            "A": {"description": "Cast aluminum housing", "adder": 0.0},
        },
    },
    {
        "index": 6,
        "name": "Installation orientation",
        "codes": {
            # Pricing: 3 baseline, 4 +50
            "3": {"description": "Universal flange installation", "adder": 0.0},
            "1": {"description": "Horizontal installation", "adder": 0.0},
            "2": {"description": "Vertical installation", "adder": 0.0},
            "4": {"description": "Vertical with left side high pressure", "adder": 50.0},
        },
    },
    {
        "index": 7,
        "name": "Electrical connection",
        "codes": {
            # Pricing: 1 baseline, 2 +50
            "1": {"description": "1/2 inch NPT female electrical connection", "adder": 0.0},
            "2": {"description": "G 1/2 inch female electrical connection", "adder": 50.0},
            "3": {"description": "1/4 inch NPT female electrical connection", "adder": 0.0},
        },
    },
    {
        "index": 8,
        "name": "Display",
        "codes": {
            # Pricing: 1 baseline, 0 zero
            "1": {"description": "With display", "adder": 0.0},
            "0": {"description": "Without display", "adder": 0.0},
        },
    },
    {
        "index": 9,
        "name": "Mounting bracket",
        "codes": {
            # Pricing: C baseline, B +50
            "C": {"description": "Universal bracket", "adder": 0.0},
            "A": {"description": "304 stainless bracket", "adder": 0.0},
            "B": {"description": "316 stainless bracket", "adder": 50.0},
        },
    },
    {
        "index": 10,
        "name": "Area classification",
        "codes": {
            # Pricing: 1 baseline
            "1": {"description": "General purpose", "adder": 0.0},
            "2": {"description": "Explosion proof", "adder": 200.0},
            "3": {"description": "Class I Div 2", "adder": 150.0},
            "4": {"description": "Canadian specifications", "adder": 100.0},
        },
    },
    {
        "index": 11,
        "name": "Optional features",
        "codes": {
            # Pricing: 02 baseline
            "02": {"description": "Memory card", "adder": 0.0},
            "01": {"description": "Signal cable", "adder": 50.0},
            "03": {"description": "High corrosion resistance coating", "adder": 150.0},
            "04": {"description": "Unlimited software updates", "adder": 200.0},
        },
    },
]


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

            # Segment 11 can have codes like "02", which are fine as-is.
            # We do not strip leading zeros.
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
