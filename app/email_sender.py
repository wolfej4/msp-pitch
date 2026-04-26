"""Send proposal PDFs via SMTP."""

from email.message import EmailMessage

import aiosmtplib

from .config import settings


class EmailError(Exception):
    pass


async def send_proposal(
    to: str,
    subject: str,
    body: str,
    pdf_bytes: bytes,
    pdf_filename: str = "proposal.pdf",
) -> None:
    if not settings.SMTP_HOST:
        raise EmailError("SMTP_HOST is not configured.")
    if not settings.SMTP_FROM:
        raise EmailError("SMTP_FROM is not configured.")

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=pdf_filename,
    )

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASS or None,
            start_tls=settings.SMTP_TLS,
        )
    except Exception as e:  # noqa: BLE001
        raise EmailError(f"SMTP send failed: {e}") from e
