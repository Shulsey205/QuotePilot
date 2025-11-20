from typing import List, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path

from qp_dpt_engine import quote_dp_part_number



app = FastAPI()


class QuoteRequest(BaseModel):
    part_number: str


class QuoteResponse(BaseModel):
    ok: bool
    part_number: str
    model: Optional[str] = None
    base_price: Optional[float] = None
    total_adders: Optional[float] = None
    final_price: Optional[float] = None
    segment_breakdown: List[dict] = []

    # error details when something is wrong
    error_type: Optional[str] = None
    message: Optional[str] = None
    segment: Optional[str] = None
    invalid_code: Optional[str] = None
    valid_codes: Optional[List[str]] = None


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "QuotePilot API is running"}


@app.post("/quote", response_model=QuoteResponse)
def quote_dp(request: QuoteRequest):
    """
    Take a part number string, run it through the QuotePilot engine,
    and return structured pricing and error info.
    """
    engine_result = quote_dp_part_number(request.part_number)

    # success case
    if engine_result.get("success"):
        return QuoteResponse(
            ok=True,
            part_number=request.part_number,
            model=engine_result.get("model"),
            base_price=engine_result.get("base_price"),
            total_adders=engine_result.get("adders_total"),
            final_price=engine_result.get("final_price"),
            segment_breakdown=engine_result.get("segments", []),
        )

    # error case
    error = engine_result.get("error") or {}

    return QuoteResponse(
        ok=False,
        part_number=request.part_number,
        model=engine_result.get("model"),
        base_price=engine_result.get("base_price"),
        total_adders=engine_result.get("adders_total"),
        final_price=engine_result.get("final_price"),
        segment_breakdown=engine_result.get("segments", []),
        error_type="validation_error",
        message=error.get("message"),
        segment=error.get("segment"),
        invalid_code=error.get("invalid_code"),
        valid_codes=error.get("valid_codes"),
    )
@app.get("/ui", response_class=HTMLResponse)
def quote_ui():
    html_path = Path(__file__).parent / "quote_ui.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
