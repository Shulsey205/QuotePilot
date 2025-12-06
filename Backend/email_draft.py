from typing import Any, Dict
import base64

import httpx

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


def _pdf_to_attachment(name: str, pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Build a Microsoft Graph fileAttachment object from raw PDF bytes.
    """
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",

        "name": name,
        "contentType": "application/pdf",
        "isInline": False,
        "contentBytes": base64.b64encode(pdf_bytes).decode("utf-8"),
    }


async def create_outlook_draft_with_quote(
    access_token: str,
    subject: str,
    body_html: str,
    pdf_bytes: bytes,
    pdf_filename: str = "quote.pdf",
) -> Dict[str, Any]:
    """
    Create an Outlook draft in the signed-in user's mailbox with the quote PDF attached.

    We intentionally do NOT set any recipients yet. The user will add To/CC in Outlook,
    taking advantage of auto-complete.
    """
    message = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": body_html,
        },
        # Empty recipients for now; user picks them in Outlook
        "toRecipients": [],
        "ccRecipients": [],
        "attachments": [
            _pdf_to_attachment(pdf_filename, pdf_bytes),
        ],
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE_URL}/me/messages",
            headers=headers,
            json=message,
            timeout=15.0,
        )

    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(
            f"Graph create draft failed ({resp.status_code}): {resp.text}"
        )

    return resp.json()
