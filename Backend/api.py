from pathlib import Path
from typing import Dict, Any
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from Backend.PartNumberEngine.base_engine import (
    ENGINE_REGISTRY,
    get_engine,
    PartNumberError,
)


# --------------------------------------------------------------------------------------
# FastAPI app setup
# --------------------------------------------------------------------------------------

app = FastAPI(
    title="QuotePilot API",
    description="Quote engine for QuotePilot demo models.",
    version="1.7.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
UI_PATH = BASE_DIR / "quote_ui.html"

# Baseline default part numbers for demo quoting
DEFAULT_PART_NUMBERS: Dict[str, str] = {
    # QPSAH200S baseline
    "QPSAH200S": "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02",
    # QPMAG defaults can be added later
}


# --------------------------------------------------------------------------------------
# Pydantic models
# --------------------------------------------------------------------------------------


class QuoteRequest(BaseModel):
    model: str
    part_number: str


class NLQuoteRequest(BaseModel):
    text: str


# --------------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------------


def run_quote(model: str, part_number: str):
    """Common helper to run the pricing engine and format errors."""
    model = model.strip().upper()
    part_number = part_number.strip()

    if model not in ENGINE_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{model}'. Available models: {', '.join(ENGINE_REGISTRY.keys())}",
        )

    engine = get_engine(model)

    try:
        pricing = engine.price_part_number(part_number)
    except PartNumberError as exc:
        # Return a structured error object the UI can display cleanly
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(exc),
                "model": model,
                "part_number": part_number,
                "segment": getattr(exc, "segment", None),
                "invalid_code": getattr(exc, "invalid_code", None),
                "valid_codes": getattr(exc, "valid_codes", None),
            },
        )

    return {
        "ok": True,
        "model": model,
        "part_number": part_number,
        "pricing": pricing,
    }


def infer_model_from_text(text: str) -> str:
    """
    Very simple natural-language model selector.

    If we see mag/flow meter language, pick QPMAG.
    Everything else defaults to QPSAH200S.
    """
    t = text.lower()

    mag_keywords = [
        "mag",
        "magmeter",
        "mag meter",
        "magnetic flow",
        "electromagnetic",
        "flow meter",
        "flowmeter",
    ]

    if any(k in t for k in mag_keywords):
        return "QPMAG"

    return "QPSAH200S"


def infer_span_code_from_text(text: str) -> str | None:
    """
    Look for numeric ranges in the text and decide which span code to use.

    Rule for this demo:
      - If any number > 400 → H (400–1000 inWC)
      - Otherwise (any numbers at all) → M (0–400 inWC)

    If there are no numbers at all, return None and keep the default.
    """
    numbers = [int(n) for n in re.findall(r"\d+", text)]
    if not numbers:
        return None

    max_val = max(numbers)
    if max_val > 400:
        return "H"
    return "M"


def normalize(text: str) -> str:
    """Lowercase and collapse spaces for simpler keyword checks."""
    t = text.lower()
    t = re.sub(r"\s+", " ", t)
    return t


def build_qpsah200s_from_text(text: str, default_part: str) -> tuple[str, Dict[str, str]]:
    """
    Starting from the default QPSAH200S part number, adjust segments based on text.

    Segments controlled by natural language in this demo:

      1  Output signal type        A/B/C
      2  Span range                M/H
      3  Wetted parts material     G/A/D
      4  Process connection        3/2/1
      5  Housing material          C/B/A
      6  Installation orientation  3/1/2/4
      7  Electrical connection     1/2/3
      8  Display                   1/0
      9  Mounting bracket          C/A/B
      10 Area classification       1/2/3/4
      11 Optional features         02/01/03/04

    If a feature is not mentioned in the text, it stays at the default.
    """
    parts = default_part.split("-")
    if len(parts) != 12:
        raise HTTPException(
            status_code=500,
            detail=f"Default part number for QPSAH200S is malformed: '{default_part}'.",
        )

    t = normalize(text)
    applied: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # 1) Output signal type (segment 1)
    #     A = HART 4–20 mA
    #     B = Fieldbus
    #     C = Profibus
    # ------------------------------------------------------------------
    if "fieldbus" in t or "foundation fieldbus" in t:
        parts[1] = "B"
        applied["output_signal_type"] = "B"
    elif "profibus" in t:
        parts[1] = "C"
        applied["output_signal_type"] = "C"
    elif "hart" in t or "4-20" in t or "4 to 20" in t or "4 – 20" in t or "analog output" in t:
        parts[1] = "A"
        applied["output_signal_type"] = "A"

    # ------------------------------------------------------------------
    # 2) Span range (segment 2)  M/H
    # ------------------------------------------------------------------
    span_code = infer_span_code_from_text(text)
    if span_code:
        parts[2] = span_code
        applied["span_range"] = span_code

    # ------------------------------------------------------------------
    # 3) Wetted parts material (segment 3)
    #     G = 316 SS
    #     A = Hastelloy
    #     D = Titanium
    # ------------------------------------------------------------------
    if "titanium" in t:
        parts[3] = "D"
        applied["wetted_parts"] = "D"
    elif "hastelloy" in t or "c-276" in t or "c276" in t:
        parts[3] = "A"
        applied["wetted_parts"] = "A"
    elif "316" in t and ("wetted" in t or "ss" in t or "stainless" in t):
        parts[3] = "G"
        applied["wetted_parts"] = "G"

    # ------------------------------------------------------------------
    # 4) Process connection (segment 4)
    #     3 = 1/2 in NPT female
    #     2 = 1/4 in NPT female
    #     1 = no process connection
    # ------------------------------------------------------------------
    if "no process connection" in t or "remote seal only" in t or "direct mount not required" in t:
        parts[4] = "1"
        applied["process_connection"] = "1"
    elif (
        "1/4 npt" in t
        or "1/4\" npt" in t
        or "quarter inch npt" in t
        or "1/4 in npt" in t
    ):
        parts[4] = "2"
        applied["process_connection"] = "2"
    elif (
        "1/2 npt" in t
        or "1/2\" npt" in t
        or "half inch npt" in t
        or "1/2 in npt" in t
        or "half in npt" in t
    ):
        parts[4] = "3"
        applied["process_connection"] = "3"

    # ------------------------------------------------------------------
    # 5) Housing material (segment 5)
    #     C = 316 SS housing
    #     B = corrosion resistant aluminum
    #     A = cast aluminum
    # ------------------------------------------------------------------
    if "316 housing" in t or ("316" in t and "housing" in t) or "stainless housing" in t:
        parts[5] = "C"
        applied["housing"] = "C"
    elif "corrosion resistant aluminum" in t or "epoxy coated aluminum" in t or "coated aluminum housing" in t:
        parts[5] = "B"
        applied["housing"] = "B"
    elif "aluminum housing" in t or "cast aluminum housing" in t:
        parts[5] = "A"
        applied["housing"] = "A"

    # ------------------------------------------------------------------
    # 6) Installation orientation (segment 6)
    #     3 = universal flange
    #     1 = horizontal
    #     2 = vertical
    #     4 = vertical, left side high pressure
    # ------------------------------------------------------------------
    if "horizontal mount" in t or "horizontal installation" in t:
        parts[6] = "1"
        applied["installation_orientation"] = "1"
    elif "vertical mount" in t or "vertical installation" in t:
        # If we explicitly see "left side high" treat as code 4
        if "left side high" in t or "left high pressure" in t:
            parts[6] = "4"
            applied["installation_orientation"] = "4"
        else:
            parts[6] = "2"
            applied["installation_orientation"] = "2"
    elif "universal mount" in t or "any orientation" in t:
        parts[6] = "3"
        applied["installation_orientation"] = "3"
    elif "left side high" in t or "left high pressure" in t:
        # vertical with left side high pressure
        parts[6] = "4"
        applied["installation_orientation"] = "4"

    # ------------------------------------------------------------------
    # 7) Electrical connection (segment 7)
    #     1 = 1/2 in NPT female
    #     2 = G 1/2 female
    #     3 = 1/4 in NPT female
    # ------------------------------------------------------------------
    if (
        "g 1/2" in t
        or "g1/2" in t
        or "pg13.5" in t
        or "metric gland" in t
        or "iso g 1/2" in t
    ):
        parts[7] = "2"
        applied["electrical_connection"] = "2"
    elif (
        "1/4 npt conduit" in t
        or "1/4\" npt conduit" in t
        or ("1/4 npt" in t and "electrical" in t)
    ):
        parts[7] = "3"
        applied["electrical_connection"] = "3"
    elif (
        "1/2 npt conduit" in t
        or "1/2\" npt conduit" in t
        or ("1/2 npt" in t and "electrical" in t)
        or "1/2 in npt conduit" in t
        or "half inch npt conduit" in t
    ):
        parts[7] = "1"
        applied["electrical_connection"] = "1"

    # ------------------------------------------------------------------
    # 8) Display (segment 8)
    #     1 = with display
    #     0 = without display
    # ------------------------------------------------------------------
    if "no display" in t or "without display" in t or "blind transmitter" in t:
        parts[8] = "0"
        applied["display"] = "0"
    elif "with display" in t or "digital display" in t or "local indicator" in t or "lcd" in t:
        parts[8] = "1"
        applied["display"] = "1"

    # ------------------------------------------------------------------
    # 9) Mounting bracket (segment 9)
    #     C = universal bracket
    #     A = 304 SS bracket
    #     B = 316 SS bracket
    # ------------------------------------------------------------------
    if "316 bracket" in t or ("316 stainless" in t and "bracket" in t):
        parts[9] = "B"
        applied["mounting_bracket"] = "B"
    elif "304 bracket" in t or ("304 stainless" in t and "bracket" in t):
        parts[9] = "A"
        applied["mounting_bracket"] = "A"
    elif "universal bracket" in t or "standard bracket" in t or "pipe and wall bracket" in t:
        parts[9] = "C"
        applied["mounting_bracket"] = "C"

    # ------------------------------------------------------------------
    # 10) Area classification (segment 10)
    #      1 = general purpose
    #      2 = explosion proof
    #      3 = Class I Div 2
    #      4 = Canadian
    # ------------------------------------------------------------------
    if "explosion proof" in t or "xp rated" in t or "flameproof" in t:
        parts[10] = "2"
        applied["area_class"] = "2"
    elif "class i div 2" in t or "class 1 div 2" in t or "c1d2" in t or "cid2" in t:
        parts[10] = "3"
        applied["area_class"] = "3"
    elif "canadian" in t or "csa" in t:
        parts[10] = "4"
        applied["area_class"] = "4"
    elif "general purpose" in t or "non hazardous" in t or "non-hazardous" in t:
        parts[10] = "1"
        applied["area_class"] = "1"

    # ------------------------------------------------------------------
    # 11) Optional features (segment 11)
    #      02 = memory card
    #      01 = signal cable
    #      03 = high corrosion coating
    #      04 = unlimited software updates
    # ------------------------------------------------------------------
    if "memory card" in t or "data logging" in t or "data logger" in t:
        parts[11] = "02"
        applied["optional_feature"] = "02"
    elif "signal cable" in t or ("cable" in t and "signal" in t):
        parts[11] = "01"
        applied["optional_feature"] = "01"
    elif "high corrosion" in t or "corrosion coating" in t or "coated for corrosion" in t:
        parts[11] = "03"
        applied["optional_feature"] = "03"
    elif "software updates" in t or "firmware updates" in t or "lifetime updates" in t:
        parts[11] = "04"
        applied["optional_feature"] = "04"

    generated_part = "-".join(parts)
    return generated_part, applied


# --------------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root():
    """Redirect bare / to the UI."""
    return RedirectResponse(url="/ui", status_code=307)


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def ui():
    """Serve the demo UI HTML."""
    if not UI_PATH.exists():
        raise HTTPException(
            status_code=500, detail="quote_ui.html not found on server."
        )
    html = UI_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/health")
async def health():
    """Simple health check for Railway / uptime monitoring."""
    return {"status": "ok"}


@app.post("/quote")
async def quote(request: QuoteRequest):
    """
    Exact part-number quote.

    Body:
    {
        "model": "QPSAH200S",
        "part_number": "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02"
    }
    """
    return run_quote(request.model, request.part_number)


@app.post("/nl_quote")
async def nl_quote(request: NLQuoteRequest):
    """
    Natural-language quote for QPSAH200S.

    Example:
      "DP transmitter 650 inches water, explosion proof, Hastelloy wetted parts,
       1/2 NPT process, G 1/2 electrical, blind transmitter, 316 bracket,
       high corrosion coating."

    Flow:
      - Detect model (QPSAH200S vs QPMAG). Only QPSAH200S is implemented.
      - Start from the default QPSAH200S configuration.
      - Adjust all supported segments based on the text.
      - Return generated part number, applied options, and full pricing.
    """
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Request text is empty.")

    detected_model = infer_model_from_text(text)

    if detected_model != "QPSAH200S":
        return {
            "ok": False,
            "error": "Natural-language quoting is currently implemented for the QPSAH200S transmitter only.",
            "detected_model": detected_model,
        }

    default_part = DEFAULT_PART_NUMBERS.get(detected_model)
    if not default_part:
        raise HTTPException(
            status_code=500,
            detail=f"No default part number configured for model '{detected_model}'.",
        )

    generated_part, applied = build_qpsah200s_from_text(text, default_part)

    result = run_quote(detected_model, generated_part)
    if isinstance(result, JSONResponse):
        return result

    return {
        "ok": True,
        "model": detected_model,
        "request_text": text,
        "generated_part_number": generated_part,
        "applied_options": applied,
        "pricing": result["pricing"],
    }
