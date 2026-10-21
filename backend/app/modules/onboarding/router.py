import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.audit import audit
from app.core.deps import get_airport_or_404, require_airport_admin
from app.db.base import utcnow
from app.db.models import (
    Airport,
    AuditLog,
    EmergencyContact,
    Notice,
    OnboardingProgress,
    PickupPoint,
    PublishVersion,
    Question,
    RideProvider,
    SupportChannel,
    Terminal,
    User,
)
from app.db.session import get_db
from app.modules.onboarding import service

router = APIRouter(prefix="/portal/airports/{airport_id}", tags=["portal"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


class AnswersIn(BaseModel):
    answers: dict[str, Any]  # question key -> value
    section: str | None = None


@router.get("/wizard")
def wizard(airport_id: uuid.UUID, user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    state = service.wizard_state(db, airport)
    state["review_due"] = bool(airport.last_verified_at and
                               (utcnow() - airport.last_verified_at).days >= 90)
    return state


def _questions_by_key(db: Session, airport: Airport) -> dict[str, Question]:
    tpl = service.resolve_template(db, airport)
    return {qn.key: qn for sec in tpl.sections for qn in sec.questions}


@router.put("/answers")
def autosave(airport_id: uuid.UUID, body: AnswersIn, user: User = Depends(require_airport_admin),
             db: Session = Depends(get_db)):
    """Auto-save draft answers (wizard). Does not change what passengers see until publish."""
    airport = get_airport_or_404(db, airport_id)
    qs = _questions_by_key(db, airport)
    for key, value in body.answers.items():
        if key not in qs:
            raise HTTPException(422, f"Unknown question '{key}'")
        service.save_answer(db, airport.id, qs[key], value, user.id)
    prog = db.scalar(select(OnboardingProgress).where(OnboardingProgress.airport_id == airport.id))
    if not prog:
        prog = OnboardingProgress(airport_id=airport.id)
        db.add(prog)
    if body.section:
        prog.last_section = body.section
    if airport.status == "basic":
        airport.status = "onboarding"
    db.commit()
    return service.wizard_state(db, airport)


@router.post("/answers/accept-defaults")
def accept_defaults(airport_id: uuid.UUID, user: User = Depends(require_airport_admin),
                    db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    answers = service.latest_answers(db, airport.id)
    for qn in _questions_by_key(db, airport).values():
        if qn.default_value is not None and (qn.id not in answers or service.is_blank(answers[qn.id].value)):
            service.save_answer(db, airport.id, qn, qn.default_value, user.id)
    db.commit()
    return service.wizard_state(db, airport)


@router.put("/answers/{question_key}")
def update_center_edit(airport_id: uuid.UUID, question_key: str, body: dict, request: Request,
                       user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
    """Update Center: versioned edit; when live, regenerates passenger-facing content and writes audit log."""
    airport = get_airport_or_404(db, airport_id)
    qs = _questions_by_key(db, airport)
    if question_key not in qs:
        raise HTTPException(404, "Unknown question")
    cur = service.latest_answers(db, airport.id).get(qs[question_key].id)
    before = cur.value if cur else None
    ans = service.save_answer(db, airport.id, qs[question_key], body.get("value"), user.id)
    if qs[question_key].required and service.is_blank(ans.value):
        raise HTTPException(422, "Required answer cannot be empty")
    audit(db, user.id, "answer.update", "answer", question_key, airport.id, before, ans.value, _ip(request))
    db.commit()
    result: dict[str, Any] = {"key": question_key, "version": ans.version_no, "republished": False}
    if airport.status == "verified":
        result |= service.publish(db, airport, user.id, _ip(request)) | {"republished": True}
    return result


class VerifyIn(BaseModel):
    section: str


@router.post("/verify-section")
def verify_section(airport_id: uuid.UUID, body: VerifyIn, request: Request,
                   user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    sec = next((s for s in service.resolve_template(db, airport).sections if s.key == body.section), None)
    if not sec:
        raise HTTPException(404, "Unknown section")
    answers = service.latest_answers(db, airport.id)
    for qn in sec.questions:
        if qn.id in answers:
            answers[qn.id].verified_at = utcnow()
    airport.last_verified_at = utcnow()
    audit(db, user.id, "section.verify", "section", body.section, airport.id, ip=_ip(request))
    db.commit()
    return {"section": body.section, "verified_at": airport.last_verified_at.isoformat()}


@router.post("/publish")
def publish(airport_id: uuid.UUID, request: Request, user: User = Depends(require_airport_admin),
            db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    if airport.status == "suspended":
        raise HTTPException(403, "Airport suspended")
    return service.publish(db, airport, user.id, _ip(request))


@router.get("/versions")
def versions(airport_id: uuid.UUID, user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(PublishVersion).where(PublishVersion.airport_id == airport_id)
                      .order_by(PublishVersion.version_no.desc()))
    return [{"version": v.version_no, "published_at": v.created_at.isoformat(), "by": str(v.published_by)}
            for v in rows]


@router.get("/audit-log")
def audit_log(airport_id: uuid.UUID, user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.airport_id == airport_id)
                      .order_by(AuditLog.created_at.desc()).limit(200))
    return [{"at": r.created_at.isoformat(), "actor": str(r.actor_id), "action": r.action, "entity": r.entity,
             "entity_id": r.entity_id, "before": r.before, "after": r.after} for r in rows]


class AgentTestIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


@router.post("/agent-test")
def agent_test(airport_id: uuid.UUID, body: AgentTestIn, user: User = Depends(require_airport_admin),
               db: Session = Depends(get_db)):
    """Test the agent against the CURRENT DRAFT-published content (preview sandbox, not persisted)."""
    from app.modules.agent import service as agent_service

    airport = get_airport_or_404(db, airport_id)
    return agent_service.answer(db, airport, body.question, user=None, persist=False)


@router.post("/preview")
def preview(airport_id: uuid.UUID, user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
    """Passenger-experience preview from current draft answers (nothing is stored)."""
    from app.modules.journey.preview import build_preview

    return build_preview(db, get_airport_or_404(db, airport_id))


# ---------- structured data CRUD ----------
class PickupIn(BaseModel):
    terminal: str | None = None
    level: str | None = None
    zone_name: str = Field(min_length=1, max_length=150)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    walking_instructions: str | None = None
    notes: str | None = None
    kind: str = Field("pickup", pattern="^(pickup|dropoff)$")


class ProviderIn(BaseModel):
    provider_key: str = Field(pattern="^(uber|bolt|pickme|grab|taxi_desk|shuttle|public_transport)$")
    enabled: bool = True
    config: dict | None = None
    display_order: int = 0


class SupportIn(BaseModel):
    type: str = Field(pattern="^(phone|whatsapp|email)$")
    value: str = Field(min_length=3, max_length=255)
    hours: dict | None = None
    out_of_hours_message: str | None = None


class TerminalIn(BaseModel):
    name: str
    code: str = Field(max_length=10)
    opening_hours: dict | None = None


class EmergencyIn(BaseModel):
    label: str
    phone: str


class NoticeIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2)
    severity: str = Field("info", pattern="^(info|warning|critical)$")
    is_urgent: bool = False
    starts_at: datetime | None = None
    ends_at: datetime | None = None


def _dump(row, fields: list[str]) -> dict:
    out = {f: getattr(row, f) for f in fields}
    out["id"] = str(row.id)
    return out


def _crud(path: str, model, schema, fields: list[str], audit_name: str):
    @router.get(path, name=f"list_{audit_name}")
    def list_(airport_id: uuid.UUID, user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(model).where(model.airport_id == airport_id).order_by(model.created_at))
        return [_dump(r, fields) for r in rows]

    @router.post(path, status_code=201, name=f"create_{audit_name}")
    def create(airport_id: uuid.UUID, body: schema, request: Request,
               user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
        row = model(airport_id=airport_id, **body.model_dump(exclude_none=True))
        db.add(row)
        db.flush()
        audit(db, user.id, f"{audit_name}.create", audit_name, row.id, airport_id, after=body.model_dump(mode="json"),
              ip=_ip(request))
        db.commit()
        return _dump(row, fields)

    @router.put(path + "/{item_id}", name=f"update_{audit_name}")
    def update(airport_id: uuid.UUID, item_id: uuid.UUID, body: schema, request: Request,
               user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
        row = db.scalar(select(model).where(model.id == item_id, model.airport_id == airport_id))
        if not row:
            raise HTTPException(404, "Not found")
        before = _dump(row, fields)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        audit(db, user.id, f"{audit_name}.update", audit_name, row.id, airport_id, before,
              body.model_dump(mode="json"), _ip(request))
        db.commit()
        return _dump(row, fields)

    @router.delete(path + "/{item_id}", status_code=204, name=f"delete_{audit_name}")
    def delete(airport_id: uuid.UUID, item_id: uuid.UUID, request: Request,
               user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
        row = db.scalar(select(model).where(model.id == item_id, model.airport_id == airport_id))
        if not row:
            raise HTTPException(404, "Not found")
        audit(db, user.id, f"{audit_name}.delete", audit_name, row.id, airport_id, _dump(row, fields),
              ip=_ip(request))
        db.delete(row)
        db.commit()


_crud("/pickup-points", PickupPoint, PickupIn,
      ["terminal", "level", "zone_name", "lat", "lon", "walking_instructions", "notes", "kind"], "pickup_point")
_crud("/ride-providers", RideProvider, ProviderIn, ["provider_key", "enabled", "config", "display_order"],
      "ride_provider")
_crud("/support-channels", SupportChannel, SupportIn, ["type", "value", "hours", "out_of_hours_message"],
      "support_channel")
_crud("/terminals", Terminal, TerminalIn, ["name", "code", "opening_hours"], "terminal")
_crud("/emergency-contacts", EmergencyContact, EmergencyIn, ["label", "phone"], "emergency_contact")
_crud("/notices", Notice, NoticeIn, ["title", "body", "severity", "is_urgent", "starts_at", "ends_at"], "notice")
