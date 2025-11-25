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


# --------------------------------------------------------------------------------------
# FastAPI app setup
# --------------------------------------------------------------------------------------

app = FastAPI(
    title="QuotePilot API",
    description="Quote engine for QuotePilot demo models.",
    version="1.3.0",
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
        "text": "Quote a differential pressure transmitter ranged 0 to 400 inches of water, everything else standard."
    }

    For now:
    - Automatically chooses a model from the text (QPSAH200S or QPMAG).
    - Actually runs pricing only for QPSAH200S using our default configuration.
    - If QPMAG is detected, returns a friendly message that NL flow for mag is not implemented yet.
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

    result = run_quote(detected_model, default_part)

    # If run_quote returned a JSONResponse (error), just pass it through.
    if isinstance(result, JSONResponse):
        return result

    # Attach some extra context for the UI
    return {
        "ok": True,
        "model": detected_model,
        "request_text": text,
        "generated_part_number": default_part,
        "pricing": result["pricing"],
    }
