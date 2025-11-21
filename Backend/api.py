from typing import List, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

from .PartNumberEngine.registry import get_engine
from .PartNumberEngine.base_engine import PartNumberError


# ==========================================================
#  FastAPI APP + CORS
# ==========================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VERSION = "0.0.1"


# ==========================================================
#  REQUEST / RESPONSE MODELS
# ==========================================================

class QuoteRequest(BaseModel):
    model: str = "QPSAH200S"
    part_number: str


class QuoteResponse(BaseModel):
    ok: bool
    part_number: str
    model: Optional[str] = None
    base_price: Optional[float] = None
    total_adders: Optional[float] = None
    final_price: Optional[float] = None
    segment_breakdown: List[dict] = []

    error_type: Optional[str] = None
    message: Optional[str] = None
    segment: Optional[str] = None
    invalid_code: Optional[str] = None
    valid_codes: Optional[List[str]] = None


# ==========================================================
#  SUPPORT: LOAD UI HTML
# ==========================================================

def _load_ui_html() -> str:
    html_path = Path(__file__).parent / "quote_ui.html"
    return html_path.read_text(encoding="utf-8")


# ==========================================================
#  ROUTES
# ==========================================================

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "QuotePilot API is running"}


@app.get("/version")
def get_version():
    return {"version": VERSION}


@app.post("/quote", response_model=QuoteResponse)
def quote_dp(request: QuoteRequest):
    try:
        engine = get_engine(request.model or "QPSAH200S")
        result = engine.quote(request.part_number)

        return QuoteResponse(
            ok=True,
            part_number=request.part_number,
            model=result.get("model"),
            base_price=result.get("base_price"),
            total_adders=result.get("adders_total"),
            final_price=result.get("final_price"),
            segment_breakdown=result.get("segments", []),
            message="Quote generated successfully",
        )

    except PartNumberError as exc:
        return QuoteResponse(
            ok=False,
            part_number=request.part_number,
            error_type="validation_error",
            message=str(exc),
            segment=exc.segment,
            invalid_code=exc.invalid_code,
            valid_codes=exc.valid_codes,
        )

    except ValueError as exc:
        return QuoteResponse(
            ok=False,
            part_number=request.part_number,
            error_type="unsupported_model",
            message=str(exc),
        )


# ==========================================================
#  UI ROUTES
# ==========================================================

@app.get("/ui", response_class=HTMLResponse)
def quote_ui():
    return HTMLResponse(content=_load_ui_html())


@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse(content=_load_ui_html())
