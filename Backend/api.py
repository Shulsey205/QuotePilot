from pathlib import Path
from typing import Any, Dict, List, Optional
from io import BytesIO
import os
import logging

import httpx
import msal
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from pydantic import BaseModel
from dotenv import load_dotenv

from Backend.PartNumberEngine.base_engine import (
    get_engine,
    PartNumberError,
)
from Backend.PartNumberEngine.nl_qpsah200s import interpret_qpsah200s_description
from Backend.PartNumberEngine.nl_qpmag import interpret_qpmag_description
from Backend.pdf_generator import generate_quote_pdf
from Backend.email_draft import create_outlook_draft_with_quote


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quotepilot")


# ---------------------------------------------------------------------------
# Environment / Azure config
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# Load .env from project root (QuotePilot/.env)
load_dotenv(BASE_DIR.parent / ".env")

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_REDIRECT_URI = os.getenv("AZURE_REDIRECT_URI", "http://localhost:8000/auth/redirect")

# For personal Microsoft accounts, the authority should be "consumers"
AZURE_AUTHORITY = "https://login.microsoftonline.com/consumers"

# Scopes we will use with Microsoft Graph (User profile + mail access)
AZURE_SCOPES = ["User.Read", "Mail.ReadWrite"]

if not AZURE_CLIENT_ID or not AZURE_CLIENT_SECRET:
    logger.warning("Azure AD credentials are not fully configured.")


# Global MSAL application and in-memory state/token storage (OK for dev)
msal_app: Optional[msal.ConfidentialClientApplication] = None
auth_flows: Dict[str, Dict[str, Any]] = {}
current_tokens: Optional[Dict[str, Any]] = None


def _get_msal_app() -> msal.ConfidentialClientApplication:
    global msal_app
    if msal_app is None:
        if not AZURE_CLIENT_ID or not AZURE_CLIENT_SECRET:
            raise RuntimeError("Azure AD credentials are not configured.")
        msal_app = msal.ConfidentialClientApplication(
            AZURE_CLIENT_ID,
            authority=AZURE_AUTHORITY,
            client_credential=AZURE_CLIENT_SECRET,
        )
    return msal_app


# ---------------------------------------------------------------------------
# FastAPI app setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="QuotePilot API",
    description="Quote engine for QuotePilot demo models with Outlook integration.",
    version="1.7.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # safe for demo; tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QuoteSegment(BaseModel):
    key: str
    label: str
    code: str
    description: str
    adder: float


class QuotePayload(BaseModel):
    model: str
    part_number: str
    total_price: float
    currency: str = "USD"
    segments: List[QuoteSegment]


class QuoteRequest(BaseModel):
    model: str
    part_number: Optional[str] = None


class AutoQuoteRequest(BaseModel):
    description: str


class QuoteResponse(BaseModel):
    model: str
    part_number: str
    base_price: float
    total_adders: float
    total_price: float
    currency: str = "USD"
    segments: List[QuoteSegment]


class CreateDraftRequest(BaseModel):
    """
    Payload for /create-outlook-draft.
    For now this is just the quote data; later we can extend with customer fields.
    """
    quote: QuotePayload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_html(filename: str) -> str:
    path = BASE_DIR / filename
    if not path.exists():
        return f"<html><body><h1>{filename} not found</h1></body></html>"
    return path.read_text(encoding="utf-8")


def _normalize_segments(pricing_segments: Any) -> List[QuoteSegment]:
    """
    Accept segments from different engine shapes and normalize to List[QuoteSegment].

    Supports:
      1) List[dict] like:
         [{"key": "...", "label": "...", "code": "...", "description": "...", "adder": 0.0}, ...]

      2) Dict[str, dict] like:
         {
           "span_range": {
             "code": "M",
             "description": "...",
             "adder": 0.0,
             "default": True
           },
           ...
         }
    """
    normalized: List[QuoteSegment] = []

    if pricing_segments is None:
        return normalized

    # Case 1: dict keyed by segment key
    if isinstance(pricing_segments, dict):
        for seg_key, seg_val in pricing_segments.items():
            if not isinstance(seg_val, dict):
                continue
            seg_dict = {
                "key": seg_val.get("key", seg_key),
                "label": seg_val.get("label")
                or seg_val.get("name")
                or seg_key.replace("_", " ").title(),
                "code": seg_val.get("code", ""),
                "description": seg_val.get("description", ""),
                "adder": float(seg_val.get("adder", 0.0)),
            }
            normalized.append(QuoteSegment(**seg_dict))
        return normalized

    # Case 2: list of dicts
    if isinstance(pricing_segments, list):
        for seg in pricing_segments:
            if not isinstance(seg, dict):
                continue
            seg_dict = {
                "key": seg.get("key") or seg.get("segment_key") or "",
                "label": seg.get("label")
                or seg.get("name")
                or (seg.get("key") or "").replace("_", " ").title(),
                "code": seg.get("code", ""),
                "description": seg.get("description", ""),
                "adder": float(seg.get("adder", 0.0)),
            }
            normalized.append(QuoteSegment(**seg_dict))
        return normalized

    return normalized


def _build_quote_response(pricing: Dict[str, Any]) -> QuoteResponse:
    """
    Convert engine pricing dict into the standardized QuoteResponse model.
    """
    segments = _normalize_segments(pricing.get("segments"))

    total_price = pricing.get("total_price")
    if total_price is None:
        total_price = pricing.get("final_price")

    if total_price is None:
        base = float(pricing.get("base_price", 0.0))
        adders = float(pricing.get("total_adders", 0.0))
        total_price = base + adders

    return QuoteResponse(
        model=pricing["model"],
        part_number=pricing["part_number"],
        base_price=float(pricing.get("base_price", 0.0)),
        total_adders=float(pricing.get("total_adders", 0.0)),
        total_price=float(total_price),
        currency=pricing.get("currency", "USD"),
        segments=segments,
    )


def _get_access_token() -> str:
    """
    Get the current access token from memory.
    """
    if not current_tokens or "access_token" not in current_tokens:
        logger.info("Attempt to use Outlook without valid token.")
        raise HTTPException(status_code=401, detail="Not authenticated with Microsoft. Please sign in.")
    return current_tokens["access_token"]


def _build_default_email_subject(quote: QuotePayload) -> str:
    return f"Quote for {quote.model} {quote.part_number}"


def _build_default_email_body_html(quote: QuotePayload) -> str:
    return f"""
    <p>Hi,</p>
    <p>Attached is your QuotePilot quote.</p>
    <p>
      <strong>Model:</strong> {quote.model}<br/>
      <strong>Part number:</strong> {quote.part_number}<br/>
      <strong>Total price:</strong> {quote.total_price:.2f} {quote.currency}
    </p>
    <p>Sent via QuotePilot.</p>
    """


# ---------------------------------------------------------------------------
# Routes: basic
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    homepage_path = BASE_DIR / "homepage.html"
    if homepage_path.exists():
        return HTMLResponse(homepage_path.read_text(encoding="utf-8"))
    return HTMLResponse("<html><body><h1>QuotePilot API is running.</h1></body></html>")


@app.get("/ui", response_class=HTMLResponse)
async def quote_ui() -> HTMLResponse:
    return HTMLResponse(_load_html("quote_ui.html"))


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes: quoting
# ---------------------------------------------------------------------------

@app.post("/quote", response_model=QuoteResponse)
async def quote(request: QuoteRequest) -> QuoteResponse:
    """
    Price a specific model and part number.
    If part_number is omitted, the engine's baseline configuration is used.
    """
    model = request.model.strip()
    engine = get_engine(model)

    part_number = request.part_number.strip() if request.part_number else None
    if not part_number:
        try:
            part_number = engine.BASELINE_PART_NUMBER  # type: ignore[attr-defined]
            if not part_number:
                raise AttributeError
        except AttributeError:
            raise HTTPException(
                status_code=400,
                detail="Engine does not define a baseline part number.",
            )

    logger.info("QUOTE request: model=%s part_number=%s", model, part_number)

    try:
        pricing = engine.price_part_number(part_number)
    except PartNumberError as exc:
        logger.info(
            "QUOTE PartNumberError: model=%s part_number=%s segment=%s invalid=%s",
            model,
            part_number,
            getattr(exc, "segment", None),
            getattr(exc, "invalid_code", None),
        )
        error_payload = {
            "message": str(exc),
            "error_type": "part_number_error",
        }
        for field in ("segment", "invalid_code", "valid_codes"):
            if hasattr(exc, field):
                error_payload[field] = getattr(exc, field)
        raise HTTPException(status_code=422, detail=error_payload) from exc

    return _build_quote_response(pricing)


@app.post("/auto-quote", response_model=QuoteResponse)
async def auto_quote(request: AutoQuoteRequest) -> QuoteResponse:
    """
    Natural-language quote endpoint.
    Decides which model to use and returns a fully priced configuration.
    """
    description = request.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="Description is required.")

    lower_desc = description.lower()

    if "flow" in lower_desc or "mag" in lower_desc or "magmeter" in lower_desc:
        logger.info("AUTO-QUOTE: routing to QPMAG based on description.")
        nl_result = interpret_qpmag_description(description)
        model = nl_result.get("model", "QPMAG")
    else:
        logger.info("AUTO-QUOTE: routing to QPSAH200S based on description.")
        nl_result = interpret_qpsah200s_description(description)
        model = nl_result.get("model", "QPSAH200S")

    part_number = nl_result.get("part_number")
    if not part_number:
        logger.error("AUTO-QUOTE NL failed to produce part number. nl_result=%s", nl_result)
        raise HTTPException(
            status_code=500,
            detail="Natural-language interpreter did not return a part number.",
        )

    logger.info(
        "AUTO-QUOTE NL result: model=%s part_number=%s", model, part_number
    )

    engine = get_engine(model)
    try:
        pricing = engine.price_part_number(part_number)
    except PartNumberError as exc:
        logger.info(
            "AUTO-QUOTE PartNumberError: model=%s part_number=%s segment=%s invalid=%s",
            model,
            part_number,
            getattr(exc, "segment", None),
            getattr(exc, "invalid_code", None),
        )
        error_payload = {
            "message": str(exc),
            "error_type": "part_number_error",
        }
        for field in ("segment", "invalid_code", "valid_codes"):
            if hasattr(exc, field):
                error_payload[field] = getattr(exc, field)
        raise HTTPException(status_code=422, detail=error_payload) from exc

    if "currency" in nl_result:
        pricing["currency"] = nl_result["currency"]

    return _build_quote_response(pricing)


# ---------------------------------------------------------------------------
# Phase 2: test PDF generation
# ---------------------------------------------------------------------------

@app.get("/test-pdf")
async def test_pdf():
    sample_segments = [
        {
            "key": "span_range",
            "label": "Span range",
            "code": "M",
            "description": "0–400 inWC",
            "adder": 0.0,
        },
        {
            "key": "wetted_material",
            "label": "Wetted material",
            "code": "M",
            "description": "316 stainless steel",
            "adder": 150.0,
        },
        {
            "key": "housing",
            "label": "Housing",
            "code": "G",
            "description": "General purpose aluminum housing",
            "adder": 0.0,
        },
    ]

    pdf_bytes = generate_quote_pdf(
        model="QPSAH200S",
        part_number="QPSAH200S-M-M-G-3-C-3-1-1-C-1-M",
        total_price=1425.0,
        segments=sample_segments,
        currency="USD",
        customer={
            "name": "John Smith",
            "company": "Acme Chemical Plant",
        },
    )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="test_quote.pdf"'
        },
    )


# ---------------------------------------------------------------------------
# Phase 3: Microsoft auth + /me test
# ---------------------------------------------------------------------------

@app.get("/auth/login")
async def auth_login() -> RedirectResponse:
    app_msal = _get_msal_app()
    flow = app_msal.initiate_auth_code_flow(
        scopes=AZURE_SCOPES,
        redirect_uri=AZURE_REDIRECT_URI,
    )
    state = flow.get("state")
    if not state:
        raise HTTPException(status_code=500, detail="Auth flow did not return a state.")
    auth_flows[state] = flow
    logger.info("AUTH: starting login flow with state=%s", state)
    return RedirectResponse(url=flow["auth_uri"])


@app.get("/auth/redirect")
async def auth_redirect(request: Request) -> HTMLResponse:
    global current_tokens

    params = dict(request.query_params)
    state = params.get("state")

    if not state or state not in auth_flows:
        logger.warning("AUTH redirect with invalid/missing state=%s", state)
        raise HTTPException(status_code=400, detail="Invalid or missing auth state.")

    flow = auth_flows.pop(state)

    app_msal = _get_msal_app()
    result = app_msal.acquire_token_by_auth_code_flow(flow, params)

    if "error" in result:
        error = result.get("error")
        desc = result.get("error_description")
        logger.error("AUTH error from Microsoft: %s - %s", error, desc)
        raise HTTPException(
            status_code=400,
            detail=f"Error from Microsoft identity platform: {error} - {desc}",
        )

    current_tokens = result
    username = result.get("id_token_claims", {}).get("preferred_username", "Microsoft account")
    logger.info("AUTH success for user=%s", username)

    html = f"""
    <html>
      <body>
        <h2>Signed in successfully</h2>
        <p>Signed in as: {username}</p>
        <p>You can now call <code>/me</code> or continue using the QuotePilot UI.</p>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/me")
async def graph_me() -> JSONResponse:
    access_token = _get_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )

    if resp.status_code != 200:
        logger.error("Graph /me call failed: status=%s body=%s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Graph /me call failed: {resp.text}",
        )

    logger.info("Graph /me call succeeded.")
    return JSONResponse(resp.json())


# ---------------------------------------------------------------------------
# Phase 4: create Outlook draft with quote PDF attached
# ---------------------------------------------------------------------------

@app.post("/create-outlook-draft")
async def create_outlook_draft(request: CreateDraftRequest) -> JSONResponse:
    access_token = _get_access_token()
    quote = request.quote

    segments_for_pdf = [seg.dict() for seg in quote.segments]

    logger.info(
        "OUTLOOK draft requested for model=%s part_number=%s total_price=%s",
        quote.model,
        quote.part_number,
        quote.total_price,
    )

    pdf_bytes = generate_quote_pdf(
        model=quote.model,
        part_number=quote.part_number,
        total_price=quote.total_price,
        segments=segments_for_pdf,
        currency=quote.currency,
        customer=None,
    )

    subject = _build_default_email_subject(quote)
    body_html = _build_default_email_body_html(quote)
    pdf_filename = f"{quote.part_number}.pdf"

    try:
        draft = await create_outlook_draft_with_quote(
            access_token=access_token,
            subject=subject,
            body_html=body_html,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
        )
    except Exception as exc:
        logger.exception("Failed to create Outlook draft for part_number=%s", quote.part_number)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create Outlook draft: {exc}",
        ) from exc

    logger.info(
        "OUTLOOK draft created: id=%s internet_id=%s",
        draft.get("id"),
        draft.get("internetMessageId"),
    )

    return JSONResponse(
        {
            "status": "ok",
            "draft_id": draft.get("id"),
            "internet_message_id": draft.get("internetMessageId"),
            "web_link": draft.get("webLink"),
        }
    )
