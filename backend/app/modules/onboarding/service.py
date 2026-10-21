import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.audit import audit
from app.db.base import utcnow
from app.db.models import (
    Airport,
    Answer,
    FaqEntry,
    JourneyStep,
    KnowledgeChunk,
    KnowledgeDocument,
    MapEdge,
    MapNode,
    OnboardingProgress,
    PickupPoint,
    PublishVersion,
    Question,
    QuestionnaireTemplate,
    Section,
    SupportChannel,
)
from app.integrations.embeddings import embed_texts
from app.modules.onboarding.default_template import DEFAULT_TEMPLATE, STRUCTURAL_REQUIREMENTS
from app.modules.onboarding.map_defaults import DEFAULT_MAPS

# ---------- template resolution ----------


def ensure_default_template(db: Session) -> QuestionnaireTemplate:
    tpl = db.scalar(select(QuestionnaireTemplate).where(QuestionnaireTemplate.country.is_(None),
                                                        QuestionnaireTemplate.is_active.is_(True)))
    if tpl:
        return tpl
    tpl = QuestionnaireTemplate(name=DEFAULT_TEMPLATE["name"])
    for si, s in enumerate(DEFAULT_TEMPLATE["sections"]):
        sec = Section(key=s["key"], title=s["title"], order=si)
        for qi, qd in enumerate(s["questions"]):
            sec.questions.append(Question(order=qi, **qd))
        tpl.sections.append(sec)
    db.add(tpl)
    db.commit()
    return tpl


def resolve_template(db: Session, airport: Airport) -> QuestionnaireTemplate:
    if airport.template_id:
        t = db.get(QuestionnaireTemplate, airport.template_id)
        if t:
            return t
    t = db.scalar(select(QuestionnaireTemplate).where(QuestionnaireTemplate.country == airport.country,
                                                      QuestionnaireTemplate.is_active.is_(True)))
    return t or ensure_default_template(db)


# ---------- answers ----------


def latest_answers(db: Session, airport_id: uuid.UUID) -> dict[uuid.UUID, Answer]:
    sub = (select(Answer.question_id, func.max(Answer.version_no).label("v"))
           .where(Answer.airport_id == airport_id).group_by(Answer.question_id).subquery())
    rows = db.scalars(select(Answer).join(sub, (Answer.question_id == sub.c.question_id)
                                          & (Answer.version_no == sub.c.v)).where(Answer.airport_id == airport_id))
    return {a.question_id: a for a in rows}


def is_blank(v: Any) -> bool:
    return v is None or v == "" or v == []


def validate_value(question: Question, value: Any) -> Any:
    if is_blank(value):
        return None
    t = question.type
    try:
        if t == "number":
            return float(value) if "." in str(value) else int(value)
        if t == "yesno":
            if isinstance(value, bool):
                return value
            if str(value).lower() in ("yes", "true", "1"):
                return True
            if str(value).lower() in ("no", "false", "0"):
                return False
            raise ValueError
        if t == "select":
            if question.options and value not in question.options:
                raise ValueError
            return str(value)
        if t == "multiselect":
            if not isinstance(value, list) or (question.options and any(v not in question.options for v in value)):
                raise ValueError
            return value
        if t == "time":
            hh, mm = str(value).split(":")
            if not (0 <= int(hh) < 24 and 0 <= int(mm) < 60):
                raise ValueError
            return f"{int(hh):02d}:{int(mm):02d}"
        if t == "link":
            if not str(value).startswith(("http://", "https://")):
                raise ValueError
            return str(value)[:500]
        return str(value)[:4000]
    except (ValueError, TypeError):
        raise HTTPException(422, f"Invalid value for '{question.key}' (expected {t})") from None


def save_answer(db: Session, airport_id: uuid.UUID, question: Question, value: Any, author: uuid.UUID | None,
                verify: bool = False) -> Answer:
    value = validate_value(question, value)
    cur = db.scalar(select(Answer).where(Answer.airport_id == airport_id, Answer.question_id == question.id)
                    .order_by(Answer.version_no.desc()).limit(1))
    if cur and cur.value == value and not verify:
        return cur
    ans = Answer(airport_id=airport_id, question_id=question.id, value=value,
                 version_no=(cur.version_no + 1) if cur else 1, author_id=author,
                 verified_at=utcnow())
    db.add(ans)
    return ans


def format_value(question: Question, value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


# ---------- wizard view & completeness ----------


def structural_counts(db: Session, airport_id: uuid.UUID) -> dict[str, int]:
    return {
        "pickup_points": db.scalar(select(func.count()).select_from(PickupPoint).where(
            PickupPoint.airport_id == airport_id)) or 0,
        "support_channels": db.scalar(select(func.count()).select_from(SupportChannel).where(
            SupportChannel.airport_id == airport_id)) or 0,
    }


def wizard_state(db: Session, airport: Airport) -> dict:
    tpl = resolve_template(db, airport)
    answers = latest_answers(db, airport.id)
    counts = structural_counts(db, airport.id)
    sections, req_total, req_done = [], 0, 0
    for sec in tpl.sections:
        s_total = s_done = 0
        qs = []
        for qn in sec.questions:
            ans = answers.get(qn.id)
            saved = ans is not None and not is_blank(ans.value)
            if qn.required:
                s_total += 1
                s_done += 1 if saved else 0
            qs.append({
                "id": str(qn.id), "key": qn.key, "label": qn.label, "type": qn.type, "required": qn.required,
                "help_text": qn.help_text, "examples": qn.examples, "options": qn.options,
                "default_value": qn.default_value,
                "value": ans.value if saved else None, "saved": saved,
                "version": ans.version_no if ans else 0,
                "verified_at": ans.verified_at.isoformat() if ans and ans.verified_at else None,
            })
        struct = STRUCTURAL_REQUIREMENTS.get(sec.key)
        struct_ok = True
        if struct:
            s_total += 1
            struct_ok = counts[struct] > 0
            s_done += 1 if struct_ok else 0
        req_total += s_total
        req_done += s_done
        sections.append({
            "key": sec.key, "title": sec.title, "questions": qs, "required_total": s_total,
            "required_done": s_done, "complete": s_done == s_total,
            "structural": {"kind": struct, "ok": struct_ok} if struct else None,
        })
    pct = int(round(100 * req_done / req_total)) if req_total else 100
    prog = db.scalar(select(OnboardingProgress).where(OnboardingProgress.airport_id == airport.id))
    if not prog:
        prog = OnboardingProgress(airport_id=airport.id)
        db.add(prog)
    prog.completeness_pct = pct
    db.commit()
    return {
        "airport_id": str(airport.id), "status": airport.status,
        "completeness_pct": pct, "can_publish": req_done == req_total,
        "published_version": airport.current_published_version,
        "last_section": prog.last_section, "sections": sections,
        "missing": [s["key"] for s in sections if not s["complete"]],
    }


# ---------- publish / content generation ----------


def _chunk(text: str, size: int = 700) -> list[str]:
    if len(text) <= size:
        return [text]
    parts, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > size and cur:
            parts.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        parts.append(cur)
    return parts


def _lines(value: Any) -> list[str]:
    return [ln.strip(" -•\t") for ln in str(value).splitlines() if ln.strip()]


def generate_journey(db: Session, airport: Airport, version: int, qa: list[tuple[Question, Section, Any]]) -> None:
    steps: dict[tuple[str, str, str], dict] = {}
    for qn, _sec, value in qa:
        jm = qn.journey
        if not jm or is_blank(value):
            continue
        key = (jm["flow"], jm["scope"], jm["title"])
        st = steps.setdefault(key, {"order": jm["order"], "instr": [], "docs": [], "tips": [], "prohibited": [],
                                    "minutes": None, "keys": []})
        role = jm.get("role", "text")
        st["keys"].append(qn.key)
        if role == "text":
            text = format_value(qn, value)
            st["instr"].append(text if qn.type != "yesno" else f"{qn.label}: {text}")
        elif role == "minutes":
            st["minutes"] = int(value)
        elif role == "documents":
            st["docs"] += _lines(value)
        elif role == "prohibited":
            st["prohibited"] += _lines(value)
        elif role == "tip":
            st["tips"].append(f"{qn.label}: {format_value(qn, value)}" if qn.type == "number" else str(value))
    for (flow, scope, title), st in steps.items():
        db.add(JourneyStep(airport_id=airport.id, version_no=version, flow=flow, scope=scope, order=st["order"],
                           title=title, instructions="\n\n".join(st["instr"]), documents=st["docs"] or None,
                           typical_minutes=st["minutes"], tips=st["tips"] or None,
                           prohibited_items=st["prohibited"] or None, source_keys=st["keys"]))


def publish_map(db: Session, airport: Airport, version: int) -> None:
    for (flow, scope), defaults in DEFAULT_MAPS.items():
        draft = list(db.scalars(select(MapNode).where(MapNode.airport_id == airport.id, MapNode.version_no == 0,
                                                      MapNode.flow == flow, MapNode.scope == scope)
                                .order_by(MapNode.order)))
        rows = [(n.type, n.label, n.walking_minutes, n.notes) for n in draft] or defaults
        prev = None
        for i, (typ, label, mins, notes) in enumerate(rows):
            node = MapNode(airport_id=airport.id, version_no=version, flow=flow, scope=scope, order=i, type=typ,
                           label=label, walking_minutes=mins, notes=notes)
            db.add(node)
            db.flush()
            if prev:
                db.add(MapEdge(airport_id=airport.id, version_no=version, from_node=prev.id, to_node=node.id,
                               walking_minutes=prev.walking_minutes, notes=prev.notes))
            prev = node


def generate_knowledge(db: Session, airport: Airport, version: int, qa: list[tuple[Question, Section, Any]]) -> int:
    docs: list[tuple[str, str, str, str]] = []  # (source_type, ref, title, text)
    for qn, sec, value in qa:
        if is_blank(value):
            continue
        text = f"{sec.title} - {qn.label}\n{format_value(qn, value)}"
        docs.append(("answer", qn.key, qn.label, text))
        db.add(FaqEntry(airport_id=airport.id, version_no=version, question=qn.label,
                        answer=format_value(qn, value), section_key=sec.key))
    for p in db.scalars(select(PickupPoint).where(PickupPoint.airport_id == airport.id)):
        docs.append(("pickup_point", str(p.id), f"Ride {p.kind} point: {p.zone_name}",
                     f"Ride {p.kind} point '{p.zone_name}' ({p.terminal or 'airport'}, level {p.level or 'n/a'}). "
                     f"{p.walking_instructions or ''} {p.notes or ''}".strip()))
    for c in db.scalars(select(SupportChannel).where(SupportChannel.airport_id == airport.id)):
        docs.append(("support", str(c.id), f"Customer care ({c.type})", f"Customer care via {c.type}: {c.value}. "
                     f"{c.out_of_hours_message or ''}"))
    texts: list[str] = []
    metas: list[tuple[KnowledgeDocument, dict]] = []
    for stype, ref, title, text in docs:
        doc = KnowledgeDocument(airport_id=airport.id, version_no=version, source_type=stype, source_ref=ref,
                                title=title)
        db.add(doc)
        db.flush()
        for part in _chunk(text):
            texts.append(part)
            metas.append((doc, {"title": title, "source_type": stype, "source_ref": ref}))
    for i in range(0, len(texts), 64):
        vecs = embed_texts(texts[i:i + 64])
        for (doc, meta), text, vec in zip(metas[i:i + 64], texts[i:i + 64], vecs, strict=True):
            db.add(KnowledgeChunk(airport_id=airport.id, document_id=doc.id, version_no=version, content=text,
                                  embedding=vec, meta=meta))
    return len(texts)


def publish(db: Session, airport: Airport, actor: uuid.UUID | None, ip: str | None = None) -> dict:
    state = wizard_state(db, airport)
    if not state["can_publish"]:
        raise HTTPException(409, {"error": "incomplete", "missing_sections": state["missing"]})
    tpl = resolve_template(db, airport)
    answers = latest_answers(db, airport.id)
    qa = [(qn, sec, answers[qn.id].value if qn.id in answers else None) for sec in tpl.sections
          for qn in sec.questions]
    version = airport.current_published_version + 1
    generate_journey(db, airport, version, qa)
    publish_map(db, airport, version)
    chunks = generate_knowledge(db, airport, version, qa)
    snapshot = {qn.key: v for qn, _s, v in qa if not is_blank(v)}
    db.add(PublishVersion(airport_id=airport.id, version_no=version, published_by=actor, snapshot=snapshot))
    before = {"version": airport.current_published_version, "status": airport.status}
    airport.current_published_version = version
    airport.status = "verified"
    airport.last_verified_at = utcnow()
    prog = db.scalar(select(OnboardingProgress).where(OnboardingProgress.airport_id == airport.id))
    if prog and not prog.went_live_at:
        prog.went_live_at = utcnow()
    audit(db, actor, "airport.publish", "airport", airport.id, airport.id, before,
          {"version": version, "status": "verified"}, ip)
    db.commit()
    return {"version": version, "chunks": chunks, "status": airport.status}
