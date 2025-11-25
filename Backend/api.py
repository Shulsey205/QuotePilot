from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

# This imports your engine system that we already built.
# It knows how to parse part numbers, validate them, and price them.
from Backend.PartNumberEngine.base_engine import (
    ENGINE_REGISTRY,
    get_engine,
    PartNumberError,
)

# ---------------------------------------------------------
# Create the FastAPI app
# ---------------------------------------------------------

app = FastAPI(
    title="QuotePilot API",
    description="Quote engine for QuotePilot demo models.",
    version="1.2.0",
)

# Allow the browser UI to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Redirect the root (/) to the UI (/ui)
# ---------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    # When someone goes to quotepilothq.com, send them to /ui
    return RedirectResponse(url="/ui", status_code=307)

# ---------------------------------------------------------
# Request models (what the API expects in the request body)
# ---------------------------------------------------------

class QuoteRequest(BaseModel):
    # Used by /quote – exact part-number quoting
    model: str
    part_number: str


class NLQuoteRequest(BaseModel):
    # Used by /nl_quote – natural language quoting
    text: str


# ---------------------------------------------------------
# Helper functions for natural-language quotes
# ---------------------------------------------------------

def detect_model_from_text(text: str) -> str:
    """
    Very simple keyword-based model selection.
    We can make this smarter later.
    """
    t = text.lower()

    # Differential pressure transmitter
    dp_keywords = ["dp", "differential pressure", "pressure transmitter"]
    if any(k in t for k in dp_keywords):
        return "QPSAH200S"

    # Magnetic flow meter
    mag_keywords = ["mag", "magmeter", "mag meter", "magnetic flow", "mag flow"]
    if any(k in t for k in mag_keywords):
        return "QPMAG"

    # Default for now
    return "QPSAH200S"


def build_part_number_from_text(text: str, model: str, engine) -> str:
    """
    For now, start from the engine's default part number.
    Later we will read the text (0–400 in H2O, 150# flanges, etc.)
    and change individual segments.
    """
    # This relies on the engine exposing a default_part_number() method,
    # which we already added earlier in the project.
    part_number = engine.default_part_number()

    # TODO: Add real logic here later to modify segments based on the text.

    return part_number


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@app.post("/quote")
async def quote_endpoint(req: QuoteRequest):
    """
    Exact part-number quote.
    The UI sends model + full part number, we return pricing.
    """
    try:
        engine = get_engine(req.model)
        result = engine.price_part_number(req.part_number)
        return JSONResponse(result)
    except PartNumberError as e:
        # Known configuration error
        return JSONResponse(
            {
                "error": str(e),
                "segment": e.segment,
                "invalid_code": e.invalid_code,
                "valid_codes": e.valid_codes,
            },
            status_code=400,
        )
    except Exception as e:
        # Unexpected error
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/nl_quote")
async def nl_quote_endpoint(req: NLQuoteRequest):
    """
    Natural-language quote.
    Example text: "Quote a DP transmitter ranged 0 to 400 inches of water,
    everything else standard."
    """
    try:
        text = req.text

        # 1) Decide which model to use (DP vs MAG)
        model = detect_model_from_text(text)

        # 2) Get the correct engine
        engine = get_engine(model)

        # 3) Build a part number, starting from defaults
        part_number = build_part_number_from_text(text, model, engine)

        # 4) Price it using the existing engine logic
        pricing = engine.price_part_number(part_number)

        # 5) Return a clean, structured response
        return JSONResponse(
            {
                "model": model,
                "generated_part_number": part_number,
                "pricing": pricing,
            }
        )

    except PartNumberError as e:
        return JSONResponse(
            {
                "error": str(e),
                "segment": e.segment,
                "invalid_code": e.invalid_code,
                "valid_codes": e.valid_codes,
            },
            status_code=400,
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    """
    Serve the HTML UI (quote_ui.html) from the backend folder.
    """
    file_path = Path(__file__).parent / "quote_ui.html"
    if not file_path.exists():
        return HTMLResponse("<h1>UI file not found</h1>", status_code=404)

    return HTMLResponse(file_path.read_text())
