# Backend/PartNumberEngine/qpmag_engine.py

from typing import Dict, Any, List

from .base_engine import PartNumberEngine, PartNumberError, register_engine


@register_engine("QPMAG")
class QPMAGEngine(PartNumberEngine):
    """
    Quote engine for the QPMAG magnetic flowmeter.

    Part number structure (segments are separated by "-"):

        QPMAG - [1] - [2] - [3] - [4] - [5] - [6] - [7] - [8] - [9]

    1) Line size
    2) Liner material
    3) Electrode material
    4) Process connection
    5) Housing material
    6) Output signal
    7) Power supply
    8) Area classification
    9) Options

    Example baseline configuration:

        QPMAG-04-PT-SS-F1-C-1-1-C-00
    """

    MODEL: str = "QPMAG"

    # Baseline hardware price before adders
    BASE_PRICE: float = 1800.0

    # Baseline default part number (used by UI or callers as a starting point)
    BASELINE_PART_NUMBER: str = "QPMAG-04-PT-SS-F1-C-1-1-C-00"

    # Segment definitions.
    # This mirrors the style used for QPSAH200S: a list of segment dicts in order.
    MASTER_SEGMENTS: List[Dict[str, Any]] = [
        {
            "key": "line_size",
            "label": "Line size",
            "position": 1,
            "codes": {
                "04": {
                    "description": '1" (DN25)',
                    "adder": 0.0,
                },
                "06": {
                    "description": '1.5" (DN40)',
                    "adder": 50.0,
                },
                "08": {
                    "description": '2" (DN50)',
                    "adder": 100.0,
                },
                "10": {
                    "description": '3" (DN80)',
                    "adder": 150.0,
                },
                "12": {
                    "description": '4" (DN100)',
                    "adder": 250.0,
                },
            },
        },
        {
            "key": "liner_material",
            "label": "Liner material",
            "position": 2,
            "codes": {
                "PT": {
                    "description": "PTFE liner",
                    "adder": 0.0,
                },
                "HR": {
                    "description": "Hard rubber liner",
                    "adder": -50.0,
                },
                "PU": {
                    "description": "Polyurethane liner",
                    "adder": -25.0,
                },
                "PP": {
                    "description": "Polypropylene liner",
                    "adder": -25.0,
                },
            },
        },
        {
            "key": "electrode_material",
            "label": "Electrode material",
            "position": 3,
            "codes": {
                "SS": {
                    "description": "316 stainless steel electrodes",
                    "adder": 0.0,
                },
                "HC": {
                    "description": "Hastelloy C electrodes",
                    "adder": 150.0,
                },
                "TI": {
                    "description": "Titanium electrodes",
                    "adder": 200.0,
                },
            },
        },
        {
            "key": "process_connection",
            "label": "Process connection",
            "position": 4,
            "codes": {
                "F1": {
                    "description": "Wafer style, 150 class",
                    "adder": 0.0,
                },
                "F2": {
                    "description": "Flanged, 150 class",
                    "adder": 150.0,
                },
                "F3": {
                    "description": "Flanged, 300 class",
                    "adder": 250.0,
                },
            },
        },
        {
            "key": "housing_material",
            "label": "Transmitter housing material",
            "position": 5,
            "codes": {
                "C": {
                    "description": "Coated aluminum housing",
                    "adder": 0.0,
                },
                "S": {
                    "description": "Stainless steel housing",
                    "adder": 200.0,
                },
            },
        },
        {
            "key": "output_signal",
            "label": "Output signal",
            "position": 6,
            "codes": {
                "1": {
                    "description": "4–20 mA with HART",
                    "adder": 0.0,
                },
                "2": {
                    "description": "4–20 mA with HART + pulse output",
                    "adder": 75.0,
                },
                "3": {
                    "description": "Digital (Modbus/fieldbus style) output",
                    "adder": 100.0,
                },
            },
        },
        {
            "key": "power_supply",
            "label": "Power supply",
            "position": 7,
            "codes": {
                "1": {
                    "description": "24 VDC power",
                    "adder": 0.0,
                },
                "2": {
                    "description": "Universal AC power (85–264 VAC)",
                    "adder": 75.0,
                },
            },
        },
        {
            "key": "area_classification",
            "label": "Area classification / approvals",
            "position": 8,
            "codes": {
                "C": {
                    "description": "General purpose (non-hazardous)",
                    "adder": 0.0,
                },
                "D": {
                    "description": "Division 2 / Zone 2 approvals",
                    "adder": 125.0,
                },
                "E": {
                    "description": "Explosion-proof / flameproof approvals",
                    "adder": 250.0,
                },
            },
        },
        {
            "key": "options",
            "label": "Options",
            "position": 9,
            "codes": {
                "00": {
                    "description": "No extra options",
                    "adder": 0.0,
                },
                "01": {
                    "description": "Grounding rings",
                    "adder": 80.0,
                },
                "02": {
                    "description": "Grounding electrodes",
                    "adder": 100.0,
                },
                "03": {
                    "description": "Grounding rings + grounding electrodes",
                    "adder": 150.0,
                },
            },
        },
    ]

    def quote(self, part_number: str) -> Dict[str, Any]:
        """
        Public entry point for quoting a QPMAG part number.

        This delegates to the generic PartNumberEngine logic, which:
        - Parses and validates the part number against MASTER_SEGMENTS
        - Calculates all adders
        - Returns a structured dict with breakdown and final price

        Raises PartNumberError if any segment code is invalid.
        """
        return super().quote(part_number)
