from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from Backend.PartNumberEngine.base_engine import (
    ENGINE_REGISTRY,
    get_engine,
    PartNumberError,
)
from Backend.PartNumberEngine.nl_qpsah200s import (
    interpret_qpsah200s_description,
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
    allow_origins=["*"],  # OK for demo; tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------------------
# Pydantic models
# --------------------------------------------------------------------------------------


class QuoteRequest(BaseModel):
    model: str
    part_number: Optional[str] = None
    description: Optional[str] = None


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _load_ui_html() -> str:
    """
    Load the quote_ui.html file that lives next to this api module.

    Make sure quote_ui.html is in the same folder as this api.py.
    """
    ui_path = Path(__file__).with_name("quote_ui.html")
    if not ui_path.exists():
        return "<html><body><h1>QuotePilot UI not found</h1></body></html>"
    return ui_path.read_text(encoding="utf-8")


def _handle_part_number_error(
    model: str,
    part_number: str,
    exc: PartNumberError,
) -> JSONResponse:
    """
    Convert a PartNumberError into a structured JSON error.
    """
    error_payload: Dict[str, Any] = {
        "success": False,
        "model": model,
        "part_number": part_number,
        "errors": [
            {
                "message": str(exc),
                "segment": getattr(exc, "segment", None),
                "invalid_code": getattr(exc, "invalid_code", None),
                "valid_codes": getattr(exc, "valid_codes", None),
            }
        ],
    }
    return JSONResponse(status_code=422, content=error_payload)


# --------------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root_redirect():
    """
    Redirect bare / to the UI.
    """
    return RedirectResponse(url="/ui", status_code=302)


@app.get("/ui", response_class=HTMLResponse)
async def ui():
    """
    Serve the simple HTML UI.
    """
    return HTMLResponse(content=_load_ui_html())


@app.get("/health")
async def health():
    """
    Basic healthcheck so you can see if the app is alive.
    """
    return {"status": "ok"}


@app.get("/models")
async def list_models():
    """
    List available engine models registered in ENGINE_REGISTRY.
    """
    return {
        "models": sorted(list(ENGINE_REGISTRY.keys())),
    }


@app.post("/quote")
async def quote(request: QuoteRequest):
    """
    Main quote endpoint.

    Behavior:
    - You must provide a model.
    - You can provide either:
        - part_number directly, or
        - description (plain English) for QPSAH200S.
    - For QPSAH200S + description, we:
        1) Interpret the description into a full part number
        2) Run the engine for pricing and validation
        3) Return both the NL interpretation and pricing breakdown
    """
    model = request.model.strip() if request.model else ""
    if not model:
        raise HTTPException(
            status_code=400, detail="Field 'model' is required."
        )

    if model not in ENGINE_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{model}'. Available: {sorted(list(ENGINE_REGISTRY.keys()))}",
        )

    engine = get_engine(model)

    part_number: Optional[str] = request.part_number.strip() if request.part_number else None
    description: Optional[str] = request.description.strip() if request.description else None

    nl_info: Optional[Dict[str, Any]] = None

    # ----------------------------------------------------------------------------------
    # Natural-language route (QPSAH200S only, for now)
    # ----------------------------------------------------------------------------------
    if description and not part_number:
        if model != "QPSAH200S":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Natural-language description is currently only "
                    "supported for model 'QPSAH200S'. Please provide "
                    "a part_number for other models."
                ),
            )

        nl_result = interpret_qpsah200s_description(description)

        # If NL interpreter itself fails (once we add errors), return that cleanly.
        if not nl_result.get("success", False):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "source": "natural_language",
                    "model": model,
                    "description": description,
                    "errors": nl_result.get("errors", []),
                    "segments": nl_result.get("segments", {}),
                },
            )

        part_number = nl_result.get("part_number")
        if not part_number:
            raise HTTPException(
                status_code=500,
                detail="NL interpreter did not produce a part number.",
            )

        nl_info = {
            "description": description,
            "interpreter": nl_result,
        }

    # ----------------------------------------------------------------------------------
    # Direct part-number route
    # ----------------------------------------------------------------------------------
    if not part_number:
        raise HTTPException(
            status_code=400,
            detail="You must provide either 'part_number' or 'description'.",
        )

    try:
        # All engines implement a common 'quote' interface.
        engine_result: Dict[str, Any] = engine.quote(part_number)
    except PartNumberError as exc:
        return _handle_part_number_error(model=model, part_number=part_number, exc=exc)

    # ----------------------------------------------------------------------------------
    # Merge results
    # ----------------------------------------------------------------------------------
    response: Dict[str, Any] = dict(engine_result)

    # Ensure model and part_number fields are present and consistent
    response.setdefault("model", model)
    response.setdefault("part_number", part_number)

    # Attach NL info when applicable
    if nl_info is not None:
        response["natural_language"] = nl_info

        # Optionally surface NL segments as a top-level field
        # without overwriting any engine-calculated segments.
        interpreter_segments = nl_info["interpreter"].get("segments", {})
        response.setdefault("nl_segments", interpreter_segments)

    response.setdefault("success", True)

    return response
