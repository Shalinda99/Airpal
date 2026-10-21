import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.common.audit import audit
from app.core.config import settings
from app.core.deps import get_airport_or_404, require_super_admin
from app.core.security import new_opaque_token, sha256
from app.db.base import utcnow
from app.db.models import (
    AgentConversation,
    Airport,
    AnalyticsEvent,
    Invitation,
    Question,
    QuestionnaireTemplate,
    Section,
    Ticket,
    User,
)
from app.db.session import get_db
from app.modules.airports.router import serialize
from app.modules.onboarding.service import ensure_default_template

router = APIRouter(prefix="/admin", tags=["admin"])
log = __import__("logging").getLogger(__name__)


@router.get("/airports")
def list_airports(q: str = "", status: str | None = None, limit: int = 50, user: User = Depends(require_super_admin),
                  db: Session = Depends(get_db)):
    stmt = select(Airport)
    if status:
        stmt = stmt.where(Airport.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Airport.iata == q.upper(), Airport.icao == q.upper(), Airport.name.ilike(like)))
    return [serialize(a) for a in db.scalars(stmt.order_by(Airport.name).limit(min(limit, 200)))]


class ApproveIn(BaseModel):
    admin_email: EmailStr
    template_id: uuid.UUID | None = None


@router.post("/airports/{airport_id}/approve")
def approve(airport_id: uuid.UUID, body: ApproveIn, request: Request, user: User = Depends(require_super_admin),
            db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    if airport.status == "suspended":
        raise HTTPException(409, "Airport is suspended")
    if airport.status == "basic":
        airport.status = "onboarding"
    if body.template_id:
        if not db.get(QuestionnaireTemplate, body.template_id):
            raise HTTPException(404, "Template not found")
        airport.template_id = body.template_id
    token = new_opaque_token()
    db.add(Invitation(airport_id=airport.id, email=body.admin_email.lower(), token_hash=sha256(token),
                      expires_at=utcnow() + timedelta(days=7), invited_by=user.id))
    audit(db, user.id, "airport.approve", "airport", airport.id, airport.id,
          after={"admin_email": body.admin_email}, ip=request.client.host if request.client else None)
    db.commit()
    url = f"{settings.portal_url}/accept-invite/{token}"
    log.info("Invitation created for %s (deliver by email: extension point)", body.admin_email)
    out: dict[str, Any] = {"status": airport.status, "invited": body.admin_email}
    if not settings.is_prod:
        out["invite_url"] = url
    return out


@router.post("/airports/{airport_id}/suspend")
def suspend(airport_id: uuid.UUID, user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    before = airport.status
    airport.status = "suspended"
    audit(db, user.id, "airport.suspend", "airport", airport.id, airport.id, {"status": before}, {"status": "suspended"})
    db.commit()
    return {"status": airport.status}


@router.post("/airports/{airport_id}/reinstate")
def reinstate(airport_id: uuid.UUID, user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    airport.status = "verified" if airport.current_published_version else "onboarding"
    audit(db, user.id, "airport.reinstate", "airport", airport.id, airport.id)
    db.commit()
    return {"status": airport.status}


# ---------- templates ----------
def _tpl(t: QuestionnaireTemplate) -> dict:
    return {
        "id": str(t.id), "name": t.name, "country": t.country, "region": t.region, "version": t.version,
        "is_active": t.is_active,
        "sections": [{"id": str(s.id), "key": s.key, "title": s.title, "questions": [
            {"id": str(q.id), "key": q.key, "label": q.label, "type": q.type, "required": q.required,
             "help_text": q.help_text, "examples": q.examples, "options": q.options,
             "default_value": q.default_value} for q in s.questions]} for s in t.sections],
    }


@router.get("/templates")
def templates(user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    ensure_default_template(db)
    rows = db.scalars(select(QuestionnaireTemplate).order_by(QuestionnaireTemplate.created_at))
    return [{"id": str(t.id), "name": t.name, "country": t.country, "region": t.region, "version": t.version,
             "is_active": t.is_active} for t in rows]


@router.get("/templates/{template_id}")
def template_detail(template_id: uuid.UUID, user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    t = db.get(QuestionnaireTemplate, template_id)
    if not t:
        raise HTTPException(404, "Not found")
    return _tpl(t)


class CloneIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    country: str | None = Field(None, min_length=2, max_length=2)
    region: str | None = None


@router.post("/templates/{template_id}/clone", status_code=201)
def clone_template(template_id: uuid.UUID, body: CloneIn, user: User = Depends(require_super_admin),
                   db: Session = Depends(get_db)):
    src = db.get(QuestionnaireTemplate, template_id)
    if not src:
        raise HTTPException(404, "Not found")
    new = QuestionnaireTemplate(name=body.name, country=body.country.upper() if body.country else None,
                                region=body.region)
    for s in src.sections:
        ns = Section(key=s.key, title=s.title, order=s.order)
        for q in s.questions:
            ns.questions.append(Question(key=q.key, label=q.label, type=q.type, required=q.required,
                                         help_text=q.help_text, examples=q.examples, options=q.options,
                                         default_value=q.default_value, journey=q.journey, order=q.order))
        new.sections.append(ns)
    db.add(new)
    audit(db, user.id, "template.clone", "template", template_id, after=body.model_dump())
    db.commit()
    return _tpl(new)


class QuestionPatch(BaseModel):
    label: str | None = None
    required: bool | None = None
    help_text: str | None = None
    examples: list | None = None
    options: list | None = None
    default_value: Any | None = None


@router.patch("/templates/questions/{question_id}")
def patch_question(question_id: uuid.UUID, body: QuestionPatch, user: User = Depends(require_super_admin),
                   db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(q, k, v)
    audit(db, user.id, "template.question.update", "question", question_id, after=body.model_dump(exclude_unset=True))
    db.commit()
    return {"ok": True}


class QuestionCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,60}$")
    label: str
    type: str = Field(pattern="^(text|yesno|number|select|multiselect|time|link)$")
    required: bool = False
    help_text: str | None = None
    options: list | None = None
    default_value: Any | None = None


@router.post("/templates/sections/{section_id}/questions", status_code=201)
def add_question(section_id: uuid.UUID, body: QuestionCreate, user: User = Depends(require_super_admin),
                 db: Session = Depends(get_db)):
    sec = db.get(Section, section_id)
    if not sec:
        raise HTTPException(404, "Not found")
    q = Question(section_id=sec.id, order=len(sec.questions), **body.model_dump())
    db.add(q)
    audit(db, user.id, "template.question.create", "question", body.key)
    db.commit()
    return {"id": str(q.id)}


@router.get("/usage")
def usage(user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    by_status = dict(db.execute(select(Airport.status, func.count()).group_by(Airport.status)).all())
    events = dict(db.execute(select(AnalyticsEvent.event_type, func.count()).group_by(AnalyticsEvent.event_type)).all())
    return {
        "users": count(User, User.deleted_at.is_(None)), "guests": count(User, User.is_guest.is_(True)),
        "airports_by_status": by_status, "tickets": count(Ticket), "agent_conversations": count(AgentConversation),
        "events": events,
    }
