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
    version="1.5.0",
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
    # Baseline DP transmitter configuration we’ve been using
    "QPSAH200S": "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02",
    # We’ll add a real baseline for QPMAG later when NL support is ready
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
        # All engines now expose price_part_number() which wraps quote()
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

    Rules (for now):
    - If we see words that look like a mag meter / flow meter, return QPMAG.
    - Otherwise default to QPSAH200S.
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

    # Default for anything that looks like a transmitter / dp / differential
    return "QPSAH200S"


def infer_span_code_from_text(text: str) -> str | None:
    """
    Look for numeric ranges in the text and decide which span code to use
    for QPSAH200S.

    Rule for the demo:
      - If any number > 400 -> use H (400–1000 inWC)
      - Otherwise -> use M (0–400 inWC)

    If we can't find any numbers at all, return None and keep the default.
    """
    numbers = [int(n) for n in re.findall(r"\d+", text)]
    if not numbers:
        return None

    max_val = max(numbers)
    if max_val > 400:
        return "H"
    return "M"


def build_qpsah200s_from_text(text: str, default_part: str) -> tuple[str, Dict[str, str]]:
    """
    Starting from the default QPSAH200S part number, adjust specific segments
    based on keywords in the natural-language text.

    Segments we allow NL to change:
      - Output signal type (segment 1: A/B/C)
      - Span range        (segment 2: M/H)
      - Wetted parts      (segment 3: G/A/D)
      - Housing           (segment 5: C/B/A)
      - Display           (segment 8: 1/0)
      - Area class        (segment 10: 1/2/3/4)
      - Optional feature  (segment 11: 02/01/03/04)

    Everything else stays at default for this demo.
    """
    parts = default_part.split("-")
    if len(parts) != 12:
        raise HTTPException(
            status_code=500,
            detail=f"Default part number for QPSAH200S is malformed: '{default_part}'.",
        )

    t = text.lower()
    applied: Dict[str, str] = {}

    # 1) Output signal type (segment index 1)
    # A = HART, B = Fieldbus, C = Profibus
    if "fieldbus" in t:
        parts[1] = "B"
        applied["output_signal_type"] = "B"
    elif "profibus" in t:
        parts[1] = "C"
        applied["output_signal_type"] = "C"
    elif "hart" in t:
        parts[1] = "A"
        applied["output_signal_type"] = "A"

    # 2) Span range (segment index 2: M/H)
    span_code = infer_span_code_from_text(text)
    if span_code:
        parts[2] = span_code
        applied["span_range"] = span_code

    # 3) Wetted parts material (segment index 3)
    # G = 316 SS, A = Hastelloy, D = Titanium
    if "titanium" in t:
        parts[3] = "D"
        applied["wetted_parts"] = "D"
    elif "hastelloy" in t:
        parts[3] = "A"
        applied["wetted_parts"] = "A"
    elif "316" in t and ("wetted" in t or "ss" in t or "stainless" in t):
        parts[3] = "G"
        applied["wetted_parts"] = "G"

    # 5) Housing material (segment index 5)
    # C = 316 SS housing, B = corrosion resistant aluminum, A = cast aluminum
    if "316 housing" in t or ("316" in t and "housing" in t):
        parts[5] = "C"
        applied["housing"] = "C"
    elif "corrosion resistant" in t and "aluminum" in t:
        parts[5] = "B"
        applied["housing"] = "B"
    elif "aluminum housing" in t:
        parts[5] = "A"
        applied["housing"] = "A"

    # 8) Display (segment index 8)
    # 1 = with display, 0 = without display
    if "no display" in t or "without display" in t:
        parts[8] = "0"
        applied["display"] = "0"
    elif "with display" in t:
        parts[8] = "1"
        applied["display"] = "1"

    # 10) Area classification (segment index 10)
    # 1 = general purpose, 2 = explosion proof, 3 = Class I Div 2, 4 = Canadian
    if "explosion proof" in t:
        parts[10] = "2"
        applied["area_class"] = "2"
    elif "class i div 2" in t or "class 1 div 2" in t:
        parts[10] = "3"
        applied["area_class"] = "3"
    elif "canadian" in t:
        parts[10] = "4"
        applied["area_class"] = "4"
    elif "general purpose" in t:
        parts[10] = "1"
        applied["area_class"] = "1"

    # 11) Optional features (segment index 11)
    # 02 = memory card, 01 = signal cable, 03 = high corrosion coating, 04 = unlimited updates
    if "memory card" in t:
        parts[11] = "02"
        applied["optional_feature"] = "02"
    elif "signal cable" in t:
        parts[11] = "01"
        applied["optional_feature"] = "01"
    elif "high corrosion" in t or "corrosion coating" in t:
        parts[11] = "03"
        applied["optional_feature"] = "03"
    elif "software updates" in t or "firmware updates" in t:
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

    Request body:
    {
        "model": "QPSAH200S",
        "part_number": "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02"
    }
    """
    return run_quote(request.model, request.part_number)


@app.post("/nl_quote")
async def nl_quote(request: NLQuoteRequest):
    """
    Natural-language quote.

    Request body:
    {
        "text": "Quote a DP transmitter 0–150 inches of water, explosion proof, no display, Hastelloy wetted parts."
    }

    Behavior:
      - Detects model (QPSAH200S vs QPMAG). For now, only QPSAH200S is supported.
      - Starts from the default QPSAH200S part number.
      - Adjusts specific segments based on the text:
          * Output signal (HART / Fieldbus / Profibus)
          * Span range (M vs H)
          * Wetted parts (316 SS / Hastelloy / Titanium)
          * Housing (316 SS vs aluminum options)
          * Display (with / without)
          * Area classification (general / explosion proof / Class I Div 2 / Canadian)
          * Optional feature (memory card, signal cable, corrosion coating, updates)
      - Returns the generated part number and full pricing.
    """
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Request text is empty.")

    detected_model = infer_model_from_text(text)

    # For now, NL quoting is only wired up for QPSAH200S.
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

    # Build a QPSAH200S part number from the text by tweaking segments.
    generated_part, applied = build_qpsah200s_from_text(text, default_part)

    result = run_quote(detected_model, generated_part)

    # If run_quote returned a JSONResponse (error), just pass it through.
    if isinstance(result, JSONResponse):
        return result

    # Attach some extra context for the UI
    return {
        "ok": True,
        "model": detected_model,
        "request_text": text,
        "generated_part_number": generated_part,
        "applied_options": applied,
        "pricing": result["pricing"],
    }
