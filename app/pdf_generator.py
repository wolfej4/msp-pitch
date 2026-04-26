"""Generate a PDF proposal from a prospect + their proposal items + chat summary."""

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from .config import settings

TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _format_price(price: float, unit: str, cycle: str) -> str:
    parts = [f"${price:,.2f}"]
    if unit != "flat":
        parts.append(unit.replace("_", " "))
    parts.append(f"/ {cycle.replace('_', '-')}")
    return " ".join(parts)


def _line_total(item: Dict) -> float:
    return float(item["quantity"]) * float(item["price"])


def _grouped_totals(items: List[Dict]) -> Dict[str, float]:
    """Sum monthly, annual, one-time separately so the proposal is clear."""
    totals = {"monthly": 0.0, "annual": 0.0, "one_time": 0.0}
    for it in items:
        cycle = it.get("billing_cycle", "monthly")
        totals[cycle] = totals.get(cycle, 0.0) + _line_total(it)
    return totals


def render_proposal_pdf(
    prospect: Dict,
    items: List[Dict],
    summary_notes: str = "",
) -> bytes:
    template = _env.get_template("proposal.html")
    totals = _grouped_totals(items)

    # Annualize for headline
    annualized = totals["monthly"] * 12 + totals["annual"] + totals["one_time"]

    html_str = template.render(
        company={
            "name": settings.COMPANY_NAME,
            "tagline": settings.COMPANY_TAGLINE,
            "email": settings.COMPANY_EMAIL,
            "phone": settings.COMPANY_PHONE,
            "website": settings.COMPANY_WEBSITE,
        },
        prospect=prospect,
        items=[
            {
                **it,
                "line_total": _line_total(it),
                "price_display": _format_price(it["price"], it["price_unit"], it["billing_cycle"]),
            }
            for it in items
        ],
        totals=totals,
        annualized_first_year=annualized,
        summary_notes=summary_notes,
        generated_on=datetime.now().strftime("%B %d, %Y"),
    )

    buf = BytesIO()
    HTML(string=html_str).write_pdf(target=buf)
    return buf.getvalue()
