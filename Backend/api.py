from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
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
    version="1.4.0",
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
# Models
# --------------------------------------------------------------------------------------

class QuoteRequest(BaseModel):
    model: str
    input_text: str

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
    engine = get_engine(model_name)

    if engine is None:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")

    try:
        result = engine.process(request.input_text)
    except PartNumberError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "message": e.message,
                    "segment": e.segment,
                    "invalid_code": e.invalid_code,
                    "valid_codes": e.valid_codes,
                },
            },
        )
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
