from io import BytesIO
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def _format_currency(amount: float, currency: str = "USD") -> str:
    """Format a numeric amount as a currency string."""
    # Simple formatting for now, can be expanded later
    symbol = "$" if currency.upper() == "USD" else ""
    return f"{symbol}{amount:,.2f}" if symbol else f"{amount:,.2f} {currency}"


def generate_quote_pdf(
    model: str,
    part_number: str,
    total_price: float,
    segments: Iterable[Dict[str, Any]],
    currency: str = "USD",
    customer: Optional[Dict[str, Optional[str]]] = None,
) -> bytes:
    """
    Generate a simple quote PDF for the given model and part number.

    Parameters
    ----------
    model:
        Product model code, for example "QPSAH200S" or "QPMAG".
    part_number:
        Fully configured part number string.
    total_price:
        Final quoted price.
    segments:
        Iterable of dicts with keys:
          key, label, code, description, adder
    currency:
        Currency code, defaults to "USD".
    customer:
        Optional dict with keys:
          name (contact name)
          company (company name)

    Returns
    -------
    bytes:
        Raw PDF bytes ready to attach to an email.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)

    width, height = LETTER
    left_margin = 0.9 * inch
    right_margin = 0.9 * inch
    top_margin = height - 0.9 * inch

    y = top_margin

    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(left_margin, y, "QuotePilot Quote")
    y -= 24

    c.setFont("Helvetica", 10)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.drawString(left_margin, y, f"Generated: {generated_at}")
    y -= 16

    # Customer block (optional)
    if customer:
        name = (customer.get("name") or "").strip()
        company = (customer.get("company") or "").strip()

        if name or company:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left_margin, y, "Customer")
            y -= 14

            c.setFont("Helvetica", 10)
            if name:
                c.drawString(left_margin, y, f"Contact: {name}")
                y -= 12
            if company:
                c.drawString(left_margin, y, f"Company: {company}")
                y -= 12

            y -= 6  # small gap after customer block

    # Quote summary block
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y, "Quote summary")
    y -= 14

    c.setFont("Helvetica", 10)
    c.drawString(left_margin, y, f"Model: {model}")
    y -= 12
    c.drawString(left_margin, y, f"Part number: {part_number}")
    y -= 12

    formatted_total = _format_currency(total_price, currency)
    c.drawString(left_margin, y, f"Total price: {formatted_total}")
    y -= 18

    # Segment breakdown table
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y, "Configuration breakdown")
    y -= 16

    # Table headers
    c.setFont("Helvetica-Bold", 9)
    col_label_x = left_margin
    col_code_x = left_margin + 170
    col_desc_x = left_margin + 230
    col_adder_x = width - right_margin - 80

    c.drawString(col_label_x, y, "Segment")
    c.drawString(col_code_x, y, "Code")
    c.drawString(col_desc_x, y, "Description")
    c.drawString(col_adder_x, y, "Adder")
    y -= 10

    c.setLineWidth(0.5)
    c.line(left_margin, y, width - right_margin, y)
    y -= 8

    c.setFont("Helvetica", 9)

    for seg in segments:
        if y < 80:
            # New page if near bottom
            c.showPage()
            y = height - 0.9 * inch

            c.setFont("Helvetica-Bold", 9)
            c.drawString(col_label_x, y, "Segment")
            c.drawString(col_code_x, y, "Code")
            c.drawString(col_desc_x, y, "Description")
            c.drawString(col_adder_x, y, "Adder")
            y -= 10

            c.setLineWidth(0.5)
            c.line(left_margin, y, width - right_margin, y)
            y -= 8

            c.setFont("Helvetica", 9)

        label = str(seg.get("label", ""))
        code = str(seg.get("code", ""))
        desc = str(seg.get("description", ""))
        adder = seg.get("adder", 0.0)

        c.drawString(col_label_x, y, label)
        c.drawString(col_code_x, y, code)
        c.drawString(col_desc_x, y, desc)

        try:
            adder_val = float(adder)
        except (TypeError, ValueError):
            adder_val = 0.0

        if abs(adder_val) > 0.0001:
            c.drawRightString(
                col_adder_x + 70,
                y,
                _format_currency(adder_val, currency),
            )
        else:
            c.drawRightString(col_adder_x + 70, y, "-")

        y -= 12

    # Footer
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        left_margin,
        0.75 * inch,
        "QuotePilot demo. Pricing and configuration are for demonstration purposes only.",
    )

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
