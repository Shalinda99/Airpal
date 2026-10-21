import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_airport_or_404, get_optional_user, user_rate_limit
from app.db.models import AgentMessage, Feedback, User
from app.db.session import get_db
from app.modules.agent import service

router = APIRouter(tags=["agent"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    conversation_id: uuid.UUID | None = None
    lang: str = Field("en", max_length=10)


@router.post("/airports/{airport_id}/agent/chat")
def chat(airport_id: uuid.UUID, body: ChatIn, db: Session = Depends(get_db),
         user: User | None = Depends(get_optional_user)):
    airport = get_airport_or_404(db, airport_id)
    if not user:
        raise HTTPException(401, "Sign in (guest sessions are fine) to use the agent")
    user_rate_limit("agent", str(user.id), settings.agent_rate_per_minute)
    return service.answer(db, airport, body.message, user, body.lang, body.conversation_id)


class FeedbackIn(BaseModel):
    helpful: bool | None = None
    comment: str | None = Field(None, max_length=1000)


def _msg(db: Session, message_id: uuid.UUID, user: User) -> AgentMessage:
    from app.db.models import AgentConversation

    msg = db.get(AgentMessage, message_id)
    conv = db.get(AgentConversation, msg.conversation_id) if msg else None
    if not msg or msg.role != "assistant" or not conv or conv.user_id != user.id:
        raise HTTPException(404, "Message not found")
    return msg


@router.post("/agent/messages/{message_id}/feedback", status_code=201)
def feedback(message_id: uuid.UUID, body: FeedbackIn, db: Session = Depends(get_db),
             user: User | None = Depends(get_optional_user)):
    if not user:
        raise HTTPException(401, "Not authenticated")
    msg = _msg(db, message_id, user)
    db.add(Feedback(airport_id=msg.airport_id, message_id=msg.id, helpful=body.helpful,
                    comment=body.comment, wrong_answer=False))
    db.commit()
    return {"ok": True}


@router.post("/agent/messages/{message_id}/report", status_code=201)
def report(message_id: uuid.UUID, body: FeedbackIn, db: Session = Depends(get_db),
           user: User | None = Depends(get_optional_user)):
    if not user:
        raise HTTPException(401, "Not authenticated")
    msg = _msg(db, message_id, user)
    db.add(Feedback(airport_id=msg.airport_id, message_id=msg.id, helpful=False, wrong_answer=True,
                    comment=body.comment))
    db.commit()
    return {"ok": True}

