"""FastAPI app: REST API + static frontend for the MSP client-pitch tool."""

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import models, schemas
from .config import DATA_DIR, LOGO_EXTS, find_logo_path, settings
from .database import Base, engine, get_db
from .email_sender import EmailError, send_proposal
from .llm import LLMError, build_system_prompt, stream_chat
from .pdf_generator import render_proposal_pdf
from .services_seed import DEFAULT_SERVICES

# ---------- Init ----------
Base.metadata.create_all(bind=engine)


def _seed_services_if_empty():
    db: Session = next(get_db())
    try:
        if db.query(models.Service).count() == 0:
            for svc in DEFAULT_SERVICES:
                db.add(models.Service(**svc))
            db.commit()
    finally:
        db.close()


def _seed_categories_if_empty():
    """Populate categories from any names already present on services."""
    db: Session = next(get_db())
    try:
        if db.query(models.Category).count() > 0:
            return
        names = {row[0] for row in db.query(models.Service.category).all() if row[0]}
        names.add("General")
        for name in sorted(names):
            db.add(models.Category(name=name))
        db.commit()
    finally:
        db.close()


_seed_services_if_empty()
_seed_categories_if_empty()

app = FastAPI(title="MSP Client Pitch", version="1.0.0")


# ---------- Config ----------
@app.get("/api/config")
def get_config():
    return {
        "company_name": settings.COMPANY_NAME,
        "company_tagline": settings.COMPANY_TAGLINE,
        "company_email": settings.COMPANY_EMAIL,
        "company_phone": settings.COMPANY_PHONE,
        "company_website": settings.COMPANY_WEBSITE,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.ANTHROPIC_MODEL if settings.LLM_PROVIDER == "anthropic" else settings.OLLAMA_MODEL,
        "smtp_configured": bool(settings.SMTP_HOST and settings.SMTP_FROM),
        "has_logo": find_logo_path() is not None,
    }


# ---------- Logo ----------
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB


@app.get("/api/logo")
def get_logo():
    p = find_logo_path()
    if not p:
        raise HTTPException(404, "No logo uploaded")
    return FileResponse(str(p))


@app.post("/api/logo")
async def upload_logo(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in LOGO_EXTS:
        raise HTTPException(400, f"Unsupported file type. Use: {', '.join(LOGO_EXTS)}")
    contents = await file.read()
    if len(contents) > MAX_LOGO_BYTES:
        raise HTTPException(400, "Logo is too large (max 2 MB)")
    if not contents:
        raise HTTPException(400, "Empty file")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Drop any prior logo with a different extension so only one stays on disk
    for old_ext in LOGO_EXTS:
        existing = DATA_DIR / f"logo.{old_ext}"
        if existing.exists():
            existing.unlink()
    target = DATA_DIR / f"logo.{ext}"
    target.write_bytes(contents)
    return {"status": "saved"}


@app.delete("/api/logo", status_code=204)
def delete_logo():
    p = find_logo_path()
    if p:
        p.unlink()
    return Response(status_code=204)


# ---------- Prospects ----------
@app.get("/api/prospects", response_model=List[schemas.ProspectOut])
def list_prospects(db: Session = Depends(get_db)):
    return db.query(models.Prospect).order_by(models.Prospect.updated_at.desc()).all()


@app.post("/api/prospects", response_model=schemas.ProspectOut)
def create_prospect(payload: schemas.ProspectCreate, db: Session = Depends(get_db)):
    p = models.Prospect(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@app.get("/api/prospects/{prospect_id}", response_model=schemas.ProspectOut)
def get_prospect(prospect_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Prospect, prospect_id)
    if not p:
        raise HTTPException(404, "Prospect not found")
    return p


@app.patch("/api/prospects/{prospect_id}", response_model=schemas.ProspectOut)
def update_prospect(prospect_id: int, payload: schemas.ProspectUpdate, db: Session = Depends(get_db)):
    p = db.get(models.Prospect, prospect_id)
    if not p:
        raise HTTPException(404, "Prospect not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return p


@app.delete("/api/prospects/{prospect_id}", status_code=204)
def delete_prospect(prospect_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Prospect, prospect_id)
    if not p:
        raise HTTPException(404, "Prospect not found")
    db.delete(p)
    db.commit()
    return Response(status_code=204)


# ---------- Services catalog ----------
@app.get("/api/services", response_model=List[schemas.ServiceOut])
def list_services(db: Session = Depends(get_db)):
    return db.query(models.Service).order_by(models.Service.category, models.Service.name).all()


@app.post("/api/services", response_model=schemas.ServiceOut)
def create_service(payload: schemas.ServiceCreate, db: Session = Depends(get_db)):
    s = models.Service(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.patch("/api/services/{service_id}", response_model=schemas.ServiceOut)
def update_service(service_id: int, payload: schemas.ServiceUpdate, db: Session = Depends(get_db)):
    s = db.get(models.Service, service_id)
    if not s:
        raise HTTPException(404, "Service not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@app.delete("/api/services/{service_id}", status_code=204)
def delete_service(service_id: int, db: Session = Depends(get_db)):
    s = db.get(models.Service, service_id)
    if not s:
        raise HTTPException(404, "Service not found")
    db.delete(s)
    db.commit()
    return Response(status_code=204)


# ---------- Categories ----------
@app.get("/api/categories", response_model=List[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).order_by(models.Category.name).all()


@app.post("/api/categories", response_model=schemas.CategoryOut)
def create_category(payload: schemas.CategoryCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    if db.query(models.Category).filter_by(name=name).first():
        raise HTTPException(409, "A category with that name already exists")
    cat = models.Category(name=name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@app.patch("/api/categories/{cat_id}", response_model=schemas.CategoryOut)
def update_category(cat_id: int, payload: schemas.CategoryUpdate, db: Session = Depends(get_db)):
    cat = db.get(models.Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    new_name = payload.name.strip()
    if not new_name:
        raise HTTPException(400, "Name is required")
    if new_name != cat.name and db.query(models.Category).filter_by(name=new_name).first():
        raise HTTPException(409, "A category with that name already exists")
    old_name = cat.name
    cat.name = new_name
    if old_name != new_name:
        db.query(models.Service).filter_by(category=old_name).update({"category": new_name})
    db.commit()
    db.refresh(cat)
    return cat


@app.delete("/api/categories/{cat_id}", status_code=204)
def delete_category(cat_id: int, db: Session = Depends(get_db)):
    cat = db.get(models.Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    # Reassign any services in this category to "General" so they're not orphaned.
    db.query(models.Service).filter_by(category=cat.name).update({"category": "General"})
    is_general = cat.name == "General"
    db.delete(cat)
    if is_general or not db.query(models.Category).filter_by(name="General").first():
        db.add(models.Category(name="General"))
    db.commit()
    return Response(status_code=204)


# ---------- Proposal items ----------
@app.get("/api/prospects/{prospect_id}/items", response_model=List[schemas.ProposalItemOut])
def list_items(prospect_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Prospect, prospect_id):
        raise HTTPException(404, "Prospect not found")
    return db.query(models.ProposalItem).filter_by(prospect_id=prospect_id).order_by(models.ProposalItem.id).all()


@app.post("/api/prospects/{prospect_id}/items", response_model=schemas.ProposalItemOut)
def add_item(prospect_id: int, payload: schemas.ProposalItemCreate, db: Session = Depends(get_db)):
    if not db.get(models.Prospect, prospect_id):
        raise HTTPException(404, "Prospect not found")
    item = models.ProposalItem(prospect_id=prospect_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.post("/api/prospects/{prospect_id}/items/from-service/{service_id}", response_model=schemas.ProposalItemOut)
def add_item_from_service(prospect_id: int, service_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Prospect, prospect_id):
        raise HTTPException(404, "Prospect not found")
    svc = db.get(models.Service, service_id)
    if not svc:
        raise HTTPException(404, "Service not found")
    item = models.ProposalItem(
        prospect_id=prospect_id,
        service_id=svc.id,
        name=svc.name,
        description=svc.description,
        quantity=1.0,
        price=svc.default_price,
        price_unit=svc.price_unit,
        billing_cycle=svc.billing_cycle,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/api/prospects/{prospect_id}/items/{item_id}", response_model=schemas.ProposalItemOut)
def update_item(prospect_id: int, item_id: int, payload: schemas.ProposalItemUpdate, db: Session = Depends(get_db)):
    item = db.get(models.ProposalItem, item_id)
    if not item or item.prospect_id != prospect_id:
        raise HTTPException(404, "Item not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/prospects/{prospect_id}/items/{item_id}", status_code=204)
def delete_item(prospect_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.ProposalItem, item_id)
    if not item or item.prospect_id != prospect_id:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


# ---------- Chat ----------
@app.get("/api/prospects/{prospect_id}/messages", response_model=List[schemas.ChatMessageOut])
def list_messages(prospect_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Prospect, prospect_id):
        raise HTTPException(404, "Prospect not found")
    return (
        db.query(models.Message)
        .filter_by(prospect_id=prospect_id)
        .order_by(models.Message.id)
        .all()
    )


@app.delete("/api/prospects/{prospect_id}/messages", status_code=204)
def clear_messages(prospect_id: int, db: Session = Depends(get_db)):
    db.query(models.Message).filter_by(prospect_id=prospect_id).delete()
    db.commit()
    return Response(status_code=204)


@app.post("/api/prospects/{prospect_id}/chat")
async def chat(prospect_id: int, payload: schemas.ChatRequest, db: Session = Depends(get_db)):
    prospect = db.get(models.Prospect, prospect_id)
    if not prospect:
        raise HTTPException(404, "Prospect not found")

    # Save user message
    user_msg = models.Message(prospect_id=prospect_id, role="user", content=payload.message)
    db.add(user_msg)
    db.commit()

    # Build context
    services = db.query(models.Service).filter_by(is_active=1).all()
    history = (
        db.query(models.Message)
        .filter_by(prospect_id=prospect_id)
        .order_by(models.Message.id)
        .all()
    )

    system_prompt = build_system_prompt(
        prospect={
            "company_name": prospect.company_name,
            "contact_name": prospect.contact_name,
            "industry": prospect.industry,
            "headcount": prospect.headcount,
            "notes": prospect.notes,
        },
        services=[
            {
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "default_price": s.default_price,
                "price_unit": s.price_unit,
                "billing_cycle": s.billing_cycle,
            }
            for s in services
        ],
        company={"name": settings.COMPANY_NAME, "tagline": settings.COMPANY_TAGLINE},
    )

    chat_messages = [{"role": m.role, "content": m.content} for m in history if m.role in ("user", "assistant")]

    async def event_stream():
        full = []
        try:
            async for token in stream_chat(chat_messages, system_prompt):
                full.append(token)
                yield token
        except LLMError as e:
            err = f"\n\n[LLM error: {e}]"
            full.append(err)
            yield err
        finally:
            # Save assistant message after stream ends
            content = "".join(full).strip()
            if content:
                db2: Session = next(get_db())
                try:
                    db2.add(models.Message(prospect_id=prospect_id, role="assistant", content=content))
                    db2.commit()
                finally:
                    db2.close()

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")


# ---------- PDF ----------
def _load_proposal_payload(prospect_id: int, db: Session, summary_notes: str = ""):
    prospect = db.get(models.Prospect, prospect_id)
    if not prospect:
        raise HTTPException(404, "Prospect not found")
    items = db.query(models.ProposalItem).filter_by(prospect_id=prospect_id).all()

    # Pull category from the linked Service when available
    enriched = []
    for it in items:
        cat = "Services"
        if it.service_id:
            svc = db.get(models.Service, it.service_id)
            if svc:
                cat = svc.category
        enriched.append({
            "name": it.name,
            "description": it.description,
            "quantity": it.quantity,
            "price": it.price,
            "price_unit": it.price_unit,
            "billing_cycle": it.billing_cycle,
            "notes": it.notes,
            "category": cat,
        })

    # Sort by category for nicer grouping
    enriched.sort(key=lambda x: (x["category"], x["name"]))

    prospect_dict = {
        "company_name": prospect.company_name,
        "contact_name": prospect.contact_name,
        "email": prospect.email,
        "phone": prospect.phone,
        "industry": prospect.industry,
        "headcount": prospect.headcount,
    }
    return prospect_dict, enriched, summary_notes or (prospect.notes or "")


@app.get("/api/prospects/{prospect_id}/proposal.pdf")
def download_proposal(prospect_id: int, db: Session = Depends(get_db)):
    prospect, items, notes = _load_proposal_payload(prospect_id, db)
    pdf_bytes = render_proposal_pdf(prospect, items, notes)
    safe = "".join(c for c in prospect["company_name"] if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
    filename = f"{safe or 'proposal'}_proposal.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Email ----------
@app.post("/api/prospects/{prospect_id}/email")
async def email_proposal(prospect_id: int, payload: schemas.EmailRequest, db: Session = Depends(get_db)):
    prospect, items, notes = _load_proposal_payload(prospect_id, db)
    pdf_bytes = render_proposal_pdf(prospect, items, notes)

    subject = payload.subject or f"Proposal from {settings.COMPANY_NAME} for {prospect['company_name']}"
    body = payload.body or (
        f"Hi {prospect.get('contact_name') or 'there'},\n\n"
        f"Thanks for the conversation. Attached is the proposal we discussed.\n\n"
        f"Let me know if you'd like to make any adjustments — happy to refine it.\n\n"
        f"— {settings.COMPANY_NAME}\n"
    )

    safe = "".join(c for c in prospect["company_name"] if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
    filename = f"{safe or 'proposal'}_proposal.pdf"

    try:
        await send_proposal(
            to=payload.to,
            subject=subject,
            body=body,
            pdf_bytes=pdf_bytes,
            pdf_filename=filename,
        )
    except EmailError as e:
        raise HTTPException(500, str(e))

    return {"status": "sent", "to": payload.to}


# ---------- Static frontend ----------
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/healthz")
def health():
    return {"status": "ok"}
