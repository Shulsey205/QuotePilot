BASE_MODEL = "QPSAH200S"
BASE_PRICE = 1000


# Segment pricing tables


OUTPUT_TYPE = {
    "A": {"desc": "Hart communication with four to twenty milliamp analog signal", "adder": 0},
    "B": {"desc": "Fieldbus digital communication", "adder": 150},
    "C": {"desc": "Profibus digital communication", "adder": 150},
}

SPAN_RANGE = {
    "D": {"desc": "Two to twenty inches of water column", "adder": 150},
    "F": {"desc": "Twenty to two thousand inches of water column", "adder": 200},
    "L": {"desc": "Two to forty inches of water column", "adder": 100},
    "M": {"desc": "Four to four hundred inches of water column", "adder": 0},  # baseline
}

WETTED_MATERIAL = {
    "A": {"desc": "Hastelloy wetted parts", "adder": 200},
    "B": {"desc": "Cover flange material wetted parts", "adder": 50},
    "D": {"desc": "Titanium wetted parts", "adder": 300},
    "G": {"desc": "Three sixteen stainless steel wetted parts", "adder": 0},  # baseline
}

PROCESS_CONNECTION = {
    "1": {"desc": "No process connection", "adder": 0},
    "2": {"desc": "Quarter inch NPT female process connection", "adder": 0},
    "3": {"desc": "Half inch NPT female process connection", "adder": 0},  # baseline
}

HOUSING_MATERIAL = {
    "A": {"desc": "Cast aluminum housing", "adder": 0},
    "B": {"desc": "Cast aluminum alloy with corrosion resistance", "adder": 100},
    "C": {"desc": "Three sixteen stainless steel housing", "adder": 0},  # baseline
}

INSTALLATION = {
    "1": {"desc": "Horizontal installation", "adder": 0},
    "2": {"desc": "Vertical installation", "adder": 0},
    "3": {"desc": "Universal flange installation", "adder": 0},  # baseline
    "4": {"desc": "Vertical installation with left side high pressure", "adder": 50},
}

ELECTRICAL_CONNECTION = {
    "1": {"desc": "One half inch NPT female electrical connection", "adder": 0},  # baseline
    "2": {"desc": "G one half inch female electrical connection", "adder": 50},
    "3": {"desc": "One quarter inch NPT female electrical connection", "adder": 0},
}

DISPLAY = {
    "1": {"desc": "With display", "adder": 0},  # baseline
    "0": {"desc": "Without display", "adder": 0},
}

MOUNTING_BRACKET = {
    "A": {"desc": "Three zero four mounting bracket", "adder": 0},
    "B": {"desc": "Three one six mounting bracket", "adder": 50},
    "C": {"desc": "Universal mounting bracket", "adder": 0},  # baseline
}

AREA_CLASS = {
    "1": {"desc": "General purpose area classification", "adder": 0},  # baseline
    "2": {"desc": "Explosion proof area classification", "adder": 200},
    "3": {"desc": "Class one division two area classification", "adder": 150},
    "4": {"desc": "Canadian specifications area classification", "adder": 100},
}

OPTIONAL_FEATURES = {
    "01": {"desc": "Signal cable", "adder": 50},
    "02": {"desc": "Memory card", "adder": 0},  # baseline
    "03": {"desc": "High corrosion resistance coating", "adder": 150},
    "04": {"desc": "Unlimited software updates", "adder": 200},
}


SEGMENT_DEFS = [
    {
        "name": "Output signal type",
        "key": "output_type",
        "table": OUTPUT_TYPE,
    },
    {
        "name": "Span range",
        "key": "span_range",
        "table": SPAN_RANGE,
    },
    {
        "name": "Wetted parts material",
        "key": "wetted_material",
        "table": WETTED_MATERIAL,
    },
    {
        "name": "Process connection",
        "key": "process_connection",
        "table": PROCESS_CONNECTION,
    },
    {
        "name": "Housing material",
        "key": "housing_material",
        "table": HOUSING_MATERIAL,
    },
    {
        "name": "Installation orientation",
        "key": "installation",
        "table": INSTALLATION,
    },
    {
        "name": "Electrical connection",
        "key": "electrical_connection",
        "table": ELECTRICAL_CONNECTION,
    },
    {
        "name": "Display",
        "key": "display",
        "table": DISPLAY,
    },
    {
        "name": "Mounting bracket",
        "key": "mounting_bracket",
        "table": MOUNTING_BRACKET,
    },
    {
        "name": "Area classification",
        "key": "area_class",
        "table": AREA_CLASS,
    },
    {
        "name": "Optional features",
        "key": "optional_features",
        "table": OPTIONAL_FEATURES,
    },
]


class PartNumberError(ValueError):
    def __init__(self, message, segment_name=None, invalid_code=None, valid_codes=None):
        super().__init__(message)
        self.segment_name = segment_name
        self.invalid_code = invalid_code
        self.valid_codes = valid_codes or []



def suggest_valid_codes(bad_code: str, table: dict) -> list:
    """
    Given an invalid code and a table of valid options,
    return a list of suggested valid codes.
    Suggestions are simple for now: just the full list of valid keys.
    Later we can add fuzzy matching.
    """
    return list(table.keys())


def parse_part_number(part_number: str) -> dict:
    """
    Parse a QPSAH200S QuotePilot part number into its segments and metadata.
    """
    raw = part_number.strip().upper()
    parts = raw.split("-")

    if len(parts) != 12:
        raise PartNumberError(f"Expected 12 segments including model, got {len(parts)} from [{raw}]")

    model = parts[0]
    if model != BASE_MODEL:
        raise PartNumberError(f"Unsupported model [{model}], expected [{BASE_MODEL}]")

    segment_values = parts[1:]

    segments = []
    for i, seg_def in enumerate(SEGMENT_DEFS):
        code = segment_values[i]
        table = seg_def["table"]

        # Handle optional features which use two digits
        if seg_def["key"] == "optional_features":
            code = code.zfill(2)

        if code not in table:
            suggestions = suggest_valid_codes(code, table)
            suggestion_text = ", ".join(suggestions)
            raise PartNumberError(
                f"Invalid code [{code}] for segment [{seg_def['name']}]. "
                f"Valid options are: {suggestion_text}",
                segment_name=seg_def["name"],
                invalid_code=code,
                valid_codes=suggestions,
            )

        entry = table[code]
        segments.append(
            {
                "segment_index": i + 1,
                "segment_name": seg_def["name"],
                "key": seg_def["key"],
                "code": code,
                "description": entry["desc"],
                "adder": entry["adder"],
            }
        )

    return {
        "model": model,
        "base_price": BASE_PRICE,
        "segments": segments,
    }



def price_part_number(part_number: str) -> dict:
    """
    Calculate total price and provide a breakdown for a QuotePilot DP transmitter.
    """
    parsed = parse_part_number(part_number)
    segments = parsed["segments"]

    adders_total = sum(seg["adder"] for seg in segments)
    final_price = parsed["base_price"] + adders_total

    return {
        "model": parsed["model"],
        "base_price": parsed["base_price"],
        "adders_total": adders_total,
        "final_price": final_price,
        "segments": segments,
    }


def pretty_print_pricing(result: dict) -> None:
    """
    Print a human readable breakdown of the pricing result.
    """
    print(f"Model: {result['model']}")
    print(f"Base price: {result['base_price']}")
    print()

    print("Segment breakdown:")
    for seg in result["segments"]:
        line = (
            f"  Segment {seg['segment_index']} {seg['segment_name']}: "
            f"{seg['code']}  {seg['description']}  Adder: {seg['adder']}"
        )
        print(line)

    print()
    print(f"Total adders: {result['adders_total']}")
    print(f"Final price: {result['final_price']}")

def quote_dp_part_number(part_number: str) -> dict:
    """
    Clean entry point for software use.

    Takes a raw part number string, runs it through the existing
    pricing logic, and always returns a structured dictionary.

    It never prints and never raises PartNumberError.
    """

    try:
        pricing_data = price_part_number(part_number)

        return {
            "success": True,
            "error": None,
            "model": pricing_data["model"],
            "base_price": pricing_data["base_price"],
            "adders_total": pricing_data["adders_total"],  # fixed key here
            "final_price": pricing_data["final_price"],
            "segments": pricing_data["segments"],
        }

    except PartNumberError as e:
        error_payload = {
            "message": str(e),
            "segment": getattr(e, "segment_name", None),
            "invalid_code": getattr(e, "invalid_code", None),
            "valid_codes": getattr(e, "valid_codes", []),
        }

        return {
            "success": False,
            "error": error_payload,
            "model": None,
            "base_price": None,
            "adders_total": None,
            "final_price": None,
            "segments": [],
        }



if __name__ == "__main__":
    print("QuotePilot DP Transmitter engine ready.")
    print("Enter a QPSAH200S part number to price.")
    print("Press Enter with nothing typed to use the baseline configuration.")
    print("Type q to quit.")
    print()

    while True:
        raw = input("Part number: ").strip()

        if raw.lower() in ("q", "quit", "exit"):
            print("Exiting QuotePilot engine.")
            break

        # If the user just hits Enter, use the baseline configuration
        if raw == "":
            raw = "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02"

        try:
            pricing = price_part_number(raw)
            pretty_print_pricing(pricing)
            print()
        except PartNumberError as e:
            print(f"Error: {e}")
            print("Please try again.")
            print()
