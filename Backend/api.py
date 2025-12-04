from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from Backend.PartNumberEngine.base_engine import (
    get_engine,
    PartNumberError,
)
from Backend.PartNumberEngine.nl_qpsah200s import (
    interpret_qpsah200s_description,
)
from Backend.PartNumberEngine.nl_qpmag import (
    interpret_qpmag_description,
)

# --------------------------------------------------------------------------------------
# FastAPI app setup
# --------------------------------------------------------------------------------------

app = FastAPI(
    title="QuotePilot API",
    description="Quote engine for QuotePilot demo models.",
    version="1.8.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------------------
# Utility: load HTML files
# --------------------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


def load_html(filename: str) -> str:
    path = BASE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"HTML file not found: {path}")
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------------------

class QuoteRequest(BaseModel):
    model: str
    input_text: str


class AutoQuoteRequest(BaseModel):
    input_text: str


# --------------------------------------------------------------------------------------
# Model detection for one-box endpoint
# --------------------------------------------------------------------------------------

def detect_model_from_text(text: str) -> str:
    """
    Decide which engine to use (QPSAH200S or QPMAG) based on what the user typed.
    Simple rule-based router for the demo.
    """
    if not text or not text.strip():
        raise ValueError("Input text is empty.")

    t = text.strip().lower()

    # Explicit part numbers take priority
    if t.startswith("qpsah200s"):
        return "QPSAH200S"
    if t.startswith("qpmag"):
        return "QPMAG"

    # DP / differential pressure hints
    if "dp transmitter" in t or "differential pressure" in t or "dp xmitter" in t:
        return "QPSAH200S"

    # MAG / flowmeter hints
    if (
        "mag meter" in t
        or "magmeter" in t
        or "magnetic flow" in t
        or "mag flow" in t
        or "flowmeter" in t
    ):
        return "QPMAG"

    # Soft fallback heuristics
    if " dp " in f" {t} ":
        return "QPSAH200S"
    if " mag " in f" {t} ":
        return "QPMAG"

    raise ValueError(
        "Could not determine which model to use from the text. "
        "Try mentioning 'DP transmitter' or 'mag meter', or start with a QPSAH200S/QPMAG part number."
    )


# --------------------------------------------------------------------------------------
# Helpers to normalize engine outputs
# --------------------------------------------------------------------------------------

def _normalize_dp_segments_for_ui(engine: Any, result: Dict[str, Any]) -> None:
    """
    QPSAH200S engine returns segments as a dict keyed by segment name.
    The UI expects a list of segment dicts (like QPMAG uses).

    This function mutates result["segments"] into a list so both models
    look the same to the frontend.
    """
    seg_dict = result.get("segments")
    if not isinstance(seg_dict, dict):
        return

    master = getattr(engine, "master_segments", None)
    if not isinstance(master, dict):
        return

    ordered: List[Dict[str, Any]] = []

    # master is indexed 1..N; keep that order
    for index in sorted(master.keys()):
        seg_def = master[index]
        key = seg_def.get("key")
        label = seg_def.get("name") or seg_def.get("label") or key
        seg_info = seg_dict.get(key, {}) or {}

        ordered.append(
            {
                "key": key,
                "label": label,
                "code": seg_info.get("code", ""),
                "description": seg_info.get("description", ""),
                "adder": float(seg_info.get("adder", 0.0)),
            }
        )

    result["segments"] = ordered


# --------------------------------------------------------------------------------------
# Core engine runner
# --------------------------------------------------------------------------------------

def run_quote_for_model(model_name: str, input_text: str) -> Dict[str, Any]:
    """
    Core logic used by both /quote and /auto-quote.

    QPSAH200S:
        - If input_text looks like a part number (starts with QPSAH200S-), validate/price it.
        - Otherwise, treat input_text as natural-language and use interpret_qpsah200s_description()
          to build a part number, then price that.

    QPMAG:
        - If input_text looks like a part number (starts with QPMAG-), validate/price it.
        - Otherwise, treat input_text as natural-language and use interpret_qpmag_description()
          to build a part number, then price that.
    """
    text = (input_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Input text is empty.")

    # Get engine instance (raises PartNumberError if model is unknown)
    try:
        engine = get_engine(model_name)
    except PartNumberError as e:
        raise HTTPException(status_code=400, detail=e.message)

    upper = text.upper()

    # Decide how to build the part number
    if model_name == "QPSAH200S":
        if upper.startswith("QPSAH200S-"):
            part_number = upper
        else:
            nl_result = interpret_qpsah200s_description(text)
            if not nl_result.get("success", True):
                raise HTTPException(
                    status_code=400,
                    detail="Could not interpret description for QPSAH200S.",
                )
            part_number = nl_result.get("part_number", "").strip()
            if not part_number:
                raise HTTPException(
                    status_code=400,
                    detail="Natural-language interpreter did not return a part number for QPSAH200S.",
                )
    elif model_name == "QPMAG":
        if upper.startswith("QPMAG-"):
            part_number = upper
        else:
            nl_result = interpret_qpmag_description(text)
            if not nl_result.get("success", True):
                raise HTTPException(
                    status_code=400,
                    detail="Could not interpret description for QPMAG.",
                )
            part_number = nl_result.get("part_number", "").strip()
            if not part_number:
                raise HTTPException(
                    status_code=400,
                    detail="Natural-language interpreter did not return a part number for QPMAG.",
                )
    else:
        # Fallback for any future models: treat text as a part number
        part_number = upper

    # Run the engine
    try:
        result = engine.quote(part_number)
    except PartNumberError as e:
        # Build a detailed error string for the UI
        detail = e.message
        extras = []
        if e.segment:
            extras.append(f"Segment: {e.segment}")
        if e.invalid_code:
            extras.append(f"Invalid code: {e.invalid_code}")
        if e.valid_codes:
            extras.append("Valid codes: " + ", ".join(e.valid_codes))
        if extras:
            detail = detail + " | " + " | ".join(extras)
        raise HTTPException(status_code=400, detail=detail)

    # Normalize DP segments so UI can render a table just like MAG
    if model_name == "QPSAH200S":
        _normalize_dp_segments_for_ui(engine, result)

    return result


# --------------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def homepage():
    html = load_html("homepage.html")
    return HTMLResponse(content=html)


@app.get("/ui", response_class=HTMLResponse)
def ui_page():
    html = load_html("quote_ui.html")
    return HTMLResponse(content=html)


@app.post("/quote")
def quote_item(request: QuoteRequest):
    model_name = request.model.strip().upper()
    try:
        result = run_quote_for_model(model_name, request.input_text)
    except HTTPException:
        # Let FastAPI handle HTTPException responses
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "model": model_name,
        "result": result,
    }


@app.post("/auto-quote")
def auto_quote_item(request: AutoQuoteRequest):
    try:
        model_name = detect_model_from_text(request.input_text)
        result = run_quote_for_model(model_name, request.input_text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "model": model_name,
        "result": result,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
