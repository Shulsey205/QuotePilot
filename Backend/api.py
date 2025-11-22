from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from PartNumberEngine.base_engine import (
    get_engine,
    ENGINE_REGISTRY,
    PartNumberError,
)


app = FastAPI(
    title="QuotePilot API",
    description="Quote engine for QuotePilot demo models.",
    version="1.0.0",
)


# CORS so you can hit it from localhost, future frontends, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuoteRequest(BaseModel):
    model: str
    part_number: str


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {
        "message": "QuotePilot API is running.",
        "ui": "/ui",
        "quote_endpoint": "/quote",
        "engines": "/engines",
    }


@app.get("/engines")
def list_engines() -> dict:
    """
    Return the list of available models registered in ENGINE_REGISTRY.
    Example response: {"models": ["QPSAH200S", "QPMAG"]}
    """
    return {"models": sorted(ENGINE_REGISTRY.keys())}


@app.get("/ui", response_class=HTMLResponse)
def quote_ui() -> HTMLResponse:
    """
    Serve the simple HTML UI from quote_ui.html in the same folder.
    """
    html_path = Path(__file__).parent / "quote_ui.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="quote_ui.html not found next to api.py")

    html_text = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html_text)


@app.post("/quote")
def quote(req: QuoteRequest):
    """
    Accepts JSON:
      {
        "model": "QPSAH200S" or "QPMAG",
        "part_number": "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02"
      }
    Returns either a successful quote or a structured error.
    """
    model = (req.model or "").strip()
    part_number = (req.part_number or "").strip()

    if not model:
        raise HTTPException(status_code=400, detail="Field 'model' is required.")

    if not part_number:
        raise HTTPException(status_code=400, detail="Field 'part_number' is required.")

    # Look up engine
    try:
        engine = get_engine(model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Call engine and handle PartNumberError cleanly
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

    # Ensure ok flag is present
    if "ok" not in result:
        result["ok"] = True

    return result
