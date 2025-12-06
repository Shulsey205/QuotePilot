from pathlib import Path
from typing import Any, Dict, List, Optional
from io import BytesIO
import os

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


# ------------------------------------------------------------------------------
# Environment / Azure config
# ------------------------------------------------------------------------------

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
    print("WARNING: Azure AD credentials are not fully configured.")


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


# ------------------------------------------------------------------------------
# FastAPI app setup
# ------------------------------------------------------------------------------

app = FastAPI(
    title="QuotePilot API",
    description="Quote engine for QuotePilot demo models with Outlook integration.",
    version="1.6.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # safe for demo; tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------------------------

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


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _load_html(filename: str) -> str:
    path = BASE_DIR / filename
    if not path.exists():
        return f"<html><body><h1>{filename} not found</h1></body></html>"
    return path.read_text(encoding="utf-8")


def _build_quote_response(pricing: Dict[str, Any]) -> QuoteResponse:
    segments = [QuoteSegment(**seg) for seg in pricing.get("segments", [])]

    return QuoteResponse(
        model=pricing["model"],
        part_number=pricing["part_number"],
        base_price=pricing["base_price"],
        total_adders=pricing["total_adders"],
        total_price=pricing["total_price"],
        currency=pricing.get("currency", "USD"),
        segments=segments,
    )


def _get_access_token() -> str:
    """
    Get the current access token from memory.

    For development only: we keep a single user's token in memory.
    """
    if not current_tokens or "access_token" not in current_tokens:
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


# ------------------------------------------------------------------------------
# Routes: basic
# ------------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """
    Serve the homepage. Falls back to a simple message if homepage.html is missing.
    """
    homepage_path = BASE_DIR / "homepage.html"
    if homepage_path.exists():
        return HTMLResponse(homepage_path.read_text(encoding="utf-8"))
    return HTMLResponse("<html><body><h1>QuotePilot API is running.</h1></body></html>")


@app.get("/ui", response_class=HTMLResponse)
async def quote_ui() -> HTMLResponse:
    """
    Serve the main quote UI.
    """
    return HTMLResponse(_load_html("quote_ui.html"))


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


# ------------------------------------------------------------------------------
# Routes: quoting
# ------------------------------------------------------------------------------

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
            part_number = engine.get_baseline_part_number()
        except AttributeError:
            raise HTTPException(
                status_code=400,
                detail="Engine does not define a baseline part number.",
            )

    try:
        pricing = engine.price_part_number(part_number)
    except PartNumberError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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

    # Simple model selection heuristic: flow and mag go to QPMAG, otherwise DP
    if "flow" in lower_desc or "mag" in lower_desc or "magmeter" in lower_desc:
        nl_result = interpret_qpmag_description(description)
        model = nl_result.get("model", "QPMAG")
    else:
        nl_result = interpret_qpsah200s_description(description)
        model = nl_result.get("model", "QPSAH200S")

    engine = get_engine(model)

    part_number = nl_result.get("part_number")
    if not part_number:
        raise HTTPException(
            status_code=500,
            detail="Natural-language interpreter did not return a part number.",
        )

    try:
        pricing = engine.price_part_number(part_number)
    except PartNumberError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # If NL layer returned a currency, keep it
    if "currency" in nl_result:
        pricing["currency"] = nl_result["currency"]

    return _build_quote_response(pricing)


# ------------------------------------------------------------------------------
# Phase 2: test PDF generation
# ------------------------------------------------------------------------------

@app.get("/test-pdf")
async def test_pdf():
    """
    Temporary endpoint to verify server-side PDF generation.

    Returns a simple quote PDF built from hardcoded sample data.
    """
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


# ------------------------------------------------------------------------------
# Phase 3: Microsoft auth + /me test
# ------------------------------------------------------------------------------

@app.get("/auth/login")
async def auth_login() -> RedirectResponse:
    """
    Start the Microsoft login flow.
    Redirects the user to the Microsoft sign-in page.
    """
    app_msal = _get_msal_app()
    flow = app_msal.initiate_auth_code_flow(
        scopes=AZURE_SCOPES,
        redirect_uri=AZURE_REDIRECT_URI,
    )
    state = flow.get("state")
    if not state:
        raise HTTPException(status_code=500, detail="Auth flow did not return a state.")
    auth_flows[state] = flow
    return RedirectResponse(url=flow["auth_uri"])


@app.get("/auth/redirect")
async def auth_redirect(request: Request) -> HTMLResponse:
    """
    Redirect URI endpoint that Microsoft calls after login.
    Exchanges the auth code for tokens and stores them in memory.
    """
    global current_tokens

    params = dict(request.query_params)
    state = params.get("state")

    if not state or state not in auth_flows:
        raise HTTPException(status_code=400, detail="Invalid or missing auth state.")

    flow = auth_flows.pop(state)

    app_msal = _get_msal_app()
    result = app_msal.acquire_token_by_auth_code_flow(flow, params)

    if "error" in result:
        error = result.get("error")
        desc = result.get("error_description")
        raise HTTPException(
            status_code=400,
            detail=f"Error from Microsoft identity platform: {error} - {desc}",
        )

    current_tokens = result

    username = result.get("id_token_claims", {}).get("preferred_username", "Microsoft account")
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
    """
    Simple test endpoint that calls Microsoft Graph /me using the stored access token.
    """
    access_token = _get_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Graph /me call failed: {resp.text}",
        )

    return JSONResponse(resp.json())


# ------------------------------------------------------------------------------
# Phase 4: create Outlook draft with quote PDF attached
# ------------------------------------------------------------------------------

@app.post("/create-outlook-draft")
async def create_outlook_draft(request: CreateDraftRequest) -> JSONResponse:
    """
    Create an Outlook draft in the signed-in user's mailbox with the quote PDF attached.

    We do NOT require a recipient address. The draft will appear in Outlook with
    no To/CC so the user can start typing and use Outlook's auto-complete.
    """
    access_token = _get_access_token()
    quote = request.quote

    # Prepare data for PDF generation
    segments_for_pdf = [seg.dict() for seg in quote.segments]

    pdf_bytes = generate_quote_pdf(
        model=quote.model,
        part_number=quote.part_number,
        total_price=quote.total_price,
        segments=segments_for_pdf,
        currency=quote.currency,
        customer=None,  # we'll wire in customer info later
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create Outlook draft: {exc}",
        ) from exc

    return JSONResponse(
        {
            "status": "ok",
            "draft_id": draft.get("id"),
            "internet_message_id": draft.get("internetMessageId"),
            "web_link": draft.get("webLink"),
        }
    )
