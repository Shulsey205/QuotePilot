from typing import Any, Dict, List

from .base_engine import PartNumberEngine


BASE_PRICE = 900.0

# Segment dictionaries for QPMAG mag meter

SIZE_OPTIONS: Dict[str, Dict[str, Any]] = {
    "1": {"description": "one inch", "adder": 0.0},
    "2": {"description": "two inch", "adder": 150.0},
    "4": {"description": "four inch", "adder": 300.0},  # default
}

LINER_OPTIONS: Dict[str, Dict[str, Any]] = {
    "R": {"description": "hard rubber liner", "adder": 0.0},   # default
    "T": {"description": "PTFE liner", "adder": 120.0},
    "P": {"description": "polypropylene liner", "adder": 80.0},
}

ELECTRODE_OPTIONS: Dict[str, Dict[str, Any]] = {
    "S": {"description": "three sixteen stainless steel electrodes", "adder": 0.0},  # default
    "H": {"description": "Hastelloy C electrodes", "adder": 180.0},
    "T": {"description": "titanium electrodes", "adder": 140.0},
}

BODY_OPTIONS: Dict[str, Dict[str, Any]] = {
    "W": {"description": "wafer style body", "adder": 0.0},
    "F": {"description": "flanged ANSI Class one fifty body", "adder": 200.0},  # default
    "S": {"description": "sanitary tri clamp body", "adder": 300.0},
}

DISPLAY_OPTIONS: Dict[str, Dict[str, Any]] = {
    "I": {"description": "integral local display", "adder": 0.0},  # default
    "R": {"description": "remote display with ten foot cable", "adder": 75.0},
    "N": {"description": "no display", "adder": -50.0},
}

OUTPUT_OPTIONS: Dict[str, Dict[str, Any]] = {
    "A": {"description": "four to twenty milliamp with pulse output", "adder": 0.0},  # default
    "P": {"description": "pulse output only", "adder": -40.0},
    "D": {"description": "digital Modbus or RS four eighty five output", "adder": 60.0},
}

POWER_OPTIONS: Dict[str, Dict[str, Any]] = {
    "V": {"description": "twenty four volt DC supply", "adder": 0.0},  # default
    "H": {"description": "one hundred twenty volt AC supply", "adder": 30.0},
    "U": {"description": "universal AC or DC supply", "adder": 75.0},
}

OPTIONS_OPTIONS: Dict[str, Dict[str, Any]] = {
    "00": {"description": "no options", "adder": 0.0},  # default
    "GR": {"description": "grounding rings included", "adder": 85.0},
    "CR": {"description": "thirty foot sensor cable", "adder": 60.0},
}

# Baseline default configuration for QPMAG
BASELINE_PART_NUMBER = "QPMAG-4-R-S-F-I-A-V-00"


class QPMAGEngine(PartNumberEngine):
    model = "QPMAG"

    def quote(self, part_number: str) -> Dict[str, Any]:
        """
        Price and describe a QPMAG mag meter part number.

        Expected pattern:
          QPMAG-size-liner-electrode-body-display-output-power-options

        Example:
          QPMAG-4-R-S-F-I-A-V-00
        """

        normalized = (part_number or "").strip().upper()

        if not normalized or normalized == "QPMAG":
            normalized = BASELINE_PART_NUMBER

        parts = normalized.split("-")

        # If the user omitted the model prefix but supplied segments, assume QPMAG
        if parts[0] != "QPMAG":
            parts = ["QPMAG"] + parts

        # Pad with defaults if segments are missing
        # parts indices:
        # 0 model, 1 size, 2 liner, 3 electrode, 4 body, 5 display,
        # 6 output, 7 power, 8 options
        while len(parts) < 9:
            parts.append("")

        _, size_code, liner_code, electrode_code, body_code, display_code, output_code, power_code, options_code = parts[:9]

        # Apply defaults for any missing segment codes
        size_code = size_code or "4"
        liner_code = liner_code or "R"
        electrode_code = electrode_code or "S"
        body_code = body_code or "F"
        display_code = display_code or "I"
        output_code = output_code or "A"
        power_code = power_code or "V"
        options_code = options_code or "00"

        segments: List[Dict[str, Any]] = []
        adders_total = 0.0

        # Helper to build segment entries
        def add_segment(
            index: int,
            segment_name: str,
            key: str,
            code: str,
            options: Dict[str, Dict[str, Any]],
        ) -> None:
            nonlocal adders_total, segments

            info = options.get(code)
            if info is None:
                description = f"Unknown code {code}"
                adder = 0.0
            else:
                description = info["description"]
                adder = float(info.get("adder", 0.0))

            adders_total += adder

            segments.append(
                {
                    "segment_index": index,
                    "segment_name": segment_name,
                    "key": key,
                    "code": code,
                    "description": description,
                    "adder": adder,
                }
            )

        add_segment(1, "Size", "size", size_code, SIZE_OPTIONS)
        add_segment(2, "Liner material", "liner", liner_code, LINER_OPTIONS)
        add_segment(3, "Electrode material", "electrodes", electrode_code, ELECTRODE_OPTIONS)
        add_segment(4, "Body style", "body", body_code, BODY_OPTIONS)
        add_segment(5, "Display style", "display", display_code, DISPLAY_OPTIONS)
        add_segment(6, "Output signal", "output", output_code, OUTPUT_OPTIONS)
        add_segment(7, "Power supply", "power", power_code, POWER_OPTIONS)
        add_segment(8, "Options", "options", options_code, OPTIONS_OPTIONS)

        final_price = BASE_PRICE + adders_total

        return {
            "model": self.model,
            "base_price": BASE_PRICE,
            "adders_total": adders_total,
            "final_price": final_price,
            "segments": segments,
        }
