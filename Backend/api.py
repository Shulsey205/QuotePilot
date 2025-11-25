from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from Backend.PartNumberEngine.base_engine import (
    ENGINE_REGISTRY,
    get_engine,
    PartNumberError,
)





app = FastAPI(
    title="QuotePilot API",
    description="Quote engine for QuotePilot demo models.",
    version="1.2.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------
# Request models
# -------------------------------------------------------------------


class QuoteRequest(BaseModel):
    model: str
    part_number: str


class NaturalLanguageQuoteRequest(BaseModel):
    """
    Natural language quote request.

    Example:
      {
        "text": "I need a QPMAG with class 150 flanges, everything else standard."
      }
    """

    text: str


# -------------------------------------------------------------------
# Defaults and NL mapping tables
# -------------------------------------------------------------------

# Baseline default part numbers per model (same ones you use in the UI)
DEFAULT_PARTS: Dict[str, str] = {
    "QPSAH200S": "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02",
    "QPMAG": "QPMAG-1-C-SR-316-150-R-4-0-00-00",
}

# Natural-language rules for QPMAG.
# Each rule:
#   - phrases: list of substrings to look for in the text
#   - index:   which segment after the model (1-based)
#   - code:    code to apply when any phrase matches
QPMAG_RULES = [
    # Line size (segment 1)
    {"phrases": [' 1"', " 1 inch", "1 in ", "one inch"], "index": 1, "code": "1"},
    {
        "phrases": [
            ' 2"',
            " 2 inch",
            "2 in ",
            "two inch",
            "2-inch",
            "dn50",
        ],
        "index": 1,
        "code": "2",
    },
    {"phrases": [' 3"', " 3 inch", "3 in ", "three inch", "3-inch"], "index": 1, "code": "3"},
    {"phrases": [' 4"', " 4 inch", "4 in ", "four inch", "4-inch"], "index": 1, "code": "4"},
    {"phrases": [' 6"', " 6 inch", "6 in ", "six inch", "6-inch"], "index": 1, "code": "6"},

    # Body material (segment 2)
    {
        "phrases": ["carbon steel body", "carbon steel construction", "carbon steel"],
        "index": 2,
        "code": "C",
    },
    {
        "phrases": ["304 stainless body", "304 ss body", "304 stainless"],
        "index": 2,
        "code": "S",  # assume S = 304, adjust if needed
    },
    {
        "phrases": [
            "316 stainless body",
            "316 ss body",
            "316 stainless",
            "stainless body",
        ],
        "index": 2,
        "code": "H",  # assume H = 316, adjust if needed
    },

    # Liner (segment 3)
    {
        "phrases": ["soft rubber liner", "rubber liner", "standard rubber"],
        "index": 3,
        "code": "SR",  # default in your engine
    },
    {
        "phrases": ["hard rubber liner", "hard rubber"],
        "index": 3,
        "code": "HR",  # only valid if you add this code in qpmag_engine
    },
    {
    "phrases": ["ptfe liner", "teflon liner", "ptfe lining", "teflon lining"],
    "index": 3,
    "code": "PTFE",  # match the actual liner code in the engine
},


    # Electrodes (segment 4)
    {
        "phrases": ["316 stainless electrodes", "316 ss electrodes", "stainless electrodes"],
        "index": 4,
        "code": "316",
    },
    {
        "phrases": ["hastelloy electrodes", "c276 electrodes", "hastelloy c"],
        "index": 4,
        "code": "H",  # only valid if defined in qpmag_engine
    },
    {
        "phrases": ["titanium electrodes", "ti electrodes"],
        "index": 4,
        "code": "TI",  # only valid if defined in qpmag_engine
    },

    # Process connection / flange rating (segment 5)
    {
        "phrases": ["class 150", "150 lb", "150#", "150-pound", "150 pound"],
        "index": 5,
        "code": "150",
    },
    {
        "phrases": ["class 300", "300 lb", "300#", "300-pound", "300 pound"],
        "index": 5,
        "code": "300",
    },

    # Grounding rings (segment 6)
    {
        "phrases": ["no grounding rings", "no ground rings", "no rings"],
        "index": 6,
        "code": "R",
    },
    {
        "phrases": ["316 grounding rings", "316 ss ground rings", "stainless grounding rings"],
        "index": 6,
        "code": "S",  # only valid if defined
    },
    {
        "phrases": ["hastelloy grounding rings", "c276 grounding rings"],
        "index": 6,
        "code": "H",  # only valid if defined
    },

    # Output signal (segment 7)
    {
        "phrases": ["4-20", "4 to 20", "4-20ma", "4-20 ma", "analog output"],
        "index": 7,
        "code": "4",  # 4–20 mA + pulse in your current table
    },
    # Example: pure pulse output if you ever define it
    {
        "phrases": ["pulse only output", "pulse output only"],
        "index": 7,
        "code": "P",  # only valid if defined
    },

    # Approvals (segment 8)
    {
        "phrases": ["general purpose", "non hazardous", "non-hazardous"],
        "index": 8,
        "code": "0",
    },
    {
        "phrases": ["explosion proof", "explosion-proof", "ex rated", "flameproof"],
        "index": 8,
        "code": "1",  # adjust to your actual approval codes
    },
    {
        "phrases": ["class 1 div 2", "class i div 2", "c1d2", "class one div two"],
        "index": 8,
        "code": "2",
    },
    {
        "phrases": ["csa approval", "canadian approval", "csa rated"],
        "index": 8,
        "code": "3",
    },

    # Cable length (segment 9)
    {
        "phrases": ["integral mount", "integral transmitter", "no remote cable"],
        "index": 9,
        "code": "00",
    },
    {
        "phrases": ["5 meter cable", "5m cable", "five meter remote cable"],
        "index": 9,
        "code": "05",
    },
    {
        "phrases": ["10 meter cable", "10m cable", "ten meter remote cable"],
        "index": 9,
        "code": "10",
    },
    {
        "phrases": ["20 meter cable", "20m cable", "twenty meter remote cable"],
        "index": 9,
        "code": "20",
    },

    # Options (segment 10)
    {
        "phrases": ["no options", "standard options", "no special options"],
        "index": 10,
        "code": "00",
    },
    {
        "phrases": ["remote mount transmitter", "remote mounted transmitter", "remote electronics"],
        "index": 10,
        "code": "RM",  # only valid if defined in qpmag_engine
    },
    {
        "phrases": ["with display", "local display", "integral display", "indicator on the transmitter"],
        "index": 10,
        "code": "DS",  # only valid if defined
    },
    {
        "phrases": ["intrinsically safe", "is barriers", "intrinsic safety"],
        "index": 10,
        "code": "IS",  # only valid if defined
    },
]

# Simple rules for the DP transmitter (QPSAH200S).
QPSAH200S_RULES = [
    # Output signal type (segment 1)
    {"phrases": ["hart"], "index": 1, "code": "A"},
    {"phrases": ["fieldbus"], "index": 1, "code": "B"},
    {"phrases": ["profibus"], "index": 1, "code": "C"},

    # Span range (segment 2)
    {"phrases": ["2 to 40", "2–40"], "index": 2, "code": "L"},
    {"phrases": ["2 to 20", "2–20"], "index": 2, "code": "D"},
    {"phrases": ["20 to 2000", "20–2000"], "index": 2, "code": "F"},
]


# -------------------------------------------------------------------
# Natural language helpers
# -------------------------------------------------------------------


def infer_model_from_text(text: str) -> str:
    """
    Simple model detection from text.

    We will expand this later, but for now:
      - If user mentions QPMAG or "mag meter" → QPMAG
      - If user mentions QPSAH200S or "dp transmitter" → QPSAH200S
    """
    t = text.lower()

    if "qpmag" in t or "mag meter" in t or "magnetic flow" in t:
        return "QPMAG"

    if "qpsah200s" in t or "dp transmitter" in t or "differential pressure" in t:
        return "QPSAH200S"

    raise ValueError("Could not infer model from text. Please mention QPMAG or QPSAH200S.")


def apply_rules(tokens: list[str], rules: list[dict], text: str) -> None:
    """
    Apply a list of NL rules to the token list in-place.
    tokens[0] is model; tokens[1..] are segments.
    """
    t = text.lower()

    for rule in rules:
        seg_index = rule["index"]
        code = rule["code"]
        phrases = rule["phrases"]

        if any(p in t for p in phrases):
            # tokens list: [model, seg1, seg2, ...]
            if 0 < seg_index < len(tokens):
                tokens[seg_index] = code


def build_part_number_from_text(model: str, text: str) -> str:
    """
    Start from the model's default part number and override segments based on text.

    This is where natural-language phrases are mapped into specific segment codes.
    """
    if model not in DEFAULT_PARTS:
        raise ValueError(f"No default part number defined for model [{model}]")

    base = DEFAULT_PARTS[model]
    tokens = base.split("-")  # [model, seg1, seg2, ...]

    if len(tokens) < 2:
        raise ValueError(f"Default part number for [{model}] is malformed: {base}")

    if model == "QPMAG":
        apply_rules(tokens, QPMAG_RULES, text)
    elif model == "QPSAH200S":
        apply_rules(tokens, QPSAH200S_RULES, text)

    return "-".join(tokens)


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {
        "message": "QuotePilot API is running.",
        "ui": "/ui",
        "quote_endpoint": "/quote",
        "nl_quote_endpoint": "/nl_quote",
        "engines": "/engines",
    }


@app.get("/engines")
def list_engines() -> dict:
    """
    Return the list of available models registered in ENGINE_REGISTRY.
    Example: {"models": ["QPSAH200S", "QPMAG"]}
    """
    return {"models": sorted(ENGINE_REGISTRY.keys())}


@app.get("/ui", response_class=HTMLResponse)
def quote_ui() -> HTMLResponse:
    """
    Serve the HTML UI from quote_ui.html in the same folder.
    """
    html_path = Path(__file__).parent / "quote_ui.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="quote_ui.html not found next to api.py")

    html_text = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html_text)


@app.post("/quote")
def quote(req: QuoteRequest):
    """
    Direct part-number quote endpoint.

    Request:
      {
        "model": "QPSAH200S" or "QPMAG",
        "part_number": "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02"
      }
    """
    model = (req.model or "").strip()
    part_number = (req.part_number or "").strip()

    if not model:
        raise HTTPException(status_code=400, detail="Field 'model' is required.")

    if not part_number:
        raise HTTPException(status_code=400, detail="Field 'part_number' is required.")

    try:
        engine = get_engine(model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = engine.quote(part_number)
    except PartNumberError as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(e),
                "segment": e.segment,
                "invalid_code": e.invalid_code,
                "valid_codes": e.valid_codes,
                "model": model,
                "input_part_number": part_number,
            },
        )

    if "ok" not in result:
        result["ok"] = True

    return result


@app.post("/nl_quote")
def nl_quote(req: NaturalLanguageQuoteRequest):
    """
    Natural-language quote endpoint.

    Example:
      {
        "text": "I need a QPMAG with class 150 flanges, everything else standard."
      }
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Field 'text' is required.")

    try:
        model = infer_model_from_text(text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        part_number = build_part_number_from_text(model, text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        engine = get_engine(model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = engine.quote(part_number)
    except PartNumberError as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(e),
                "segment": e.segment,
                "invalid_code": e.invalid_code,
                "valid_codes": e.valid_codes,
                "model": model,
                "generated_part_number": part_number,
                "input_text": text,
            },
        )

    result["ok"] = True
    result["source"] = "natural_language"
    result["generated_part_number"] = part_number
    result["input_text"] = text

    return result
