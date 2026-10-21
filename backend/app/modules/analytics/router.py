import uuid
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_airport_admin
from app.db.models import AgentMessage, AnalyticsEvent, Feedback, User
from app.db.session import get_db

router = APIRouter(prefix="/portal/airports/{airport_id}", tags=["analytics"])


@router.get("/analytics")
def dashboard(airport_id: uuid.UUID, user: User = Depends(require_airport_admin), db: Session = Depends(get_db)):
    msgs = list(db.scalars(select(AgentMessage).where(AgentMessage.airport_id == airport_id)
                           .order_by(AgentMessage.created_at)))
    user_msgs = [m for m in msgs if m.role == "user"]
    assistants = [m for m in msgs if m.role == "assistant"]
    # pair each assistant answer with the preceding user question in the same conversation
    last_q: dict = {}
    unanswered: Counter = Counter()
    asked: Counter = Counter()
    for m in msgs:
        if m.role == "user":
            last_q[m.conversation_id] = m.content
            asked[m.content.lower().strip()[:120]] += 1
        elif m.answered is False and m.conversation_id in last_q:
            unanswered[last_q[m.conversation_id].lower().strip()[:120]] += 1
    helpful = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.airport_id == airport_id,
                                                                         Feedback.helpful.is_(True))) or 0
    not_helpful = db.scalar(select(func.count()).select_from(Feedback).where(
        Feedback.airport_id == airport_id, Feedback.helpful.is_(False), Feedback.wrong_answer.is_(False))) or 0
    wrong = db.scalars(select(Feedback).where(Feedback.airport_id == airport_id, Feedback.wrong_answer.is_(True))
                       .order_by(Feedback.created_at.desc()).limit(50)).all()
    ride_taps = Counter()
    for e in db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.airport_id == airport_id,
                                                    AnalyticsEvent.event_type == "ride_intent")):
        ride_taps[(e.props or {}).get("provider", "unknown")] += 1
    return {
        "questions_total": len(user_msgs),
        "answered_rate": round(sum(1 for m in assistants if m.answered) / len(assistants), 2) if assistants else None,
        "top_questions": [{"question": q, "count": c} for q, c in asked.most_common(10)],
        "unanswered_questions": [{"question": q, "count": c} for q, c in unanswered.most_common(10)],
        "feedback": {"helpful": helpful, "not_helpful": not_helpful, "wrong_answer_reports": len(wrong)},
        "wrong_answer_reports": [{"message_id": str(w.message_id), "comment": w.comment,
                                  "at": w.created_at.isoformat()} for w in wrong],
        "ride_taps": dict(ride_taps),
    }
