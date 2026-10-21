"""All ORM models. Tables carrying airport_id are tenant-scoped: every query MUST filter by it."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, EmbeddingType, IdMixin, UTCDateTime, utcnow

DateTime = UTCDateTime


def fk(target: str, **kw: Any):
    return mapped_column(Uuid, ForeignKey(target, ondelete=kw.pop("ondelete", "CASCADE")), **kw)


# ---------- identity & tenancy ----------
class User(IdMixin, Base):
    __tablename__ = "users"
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="en")
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    roles: Mapped[list["UserRole"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    @property
    def role_names(self) -> list[str]:
        return [r.role for r in self.roles]


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[uuid.UUID] = fk("users.id", primary_key=True)
    role: Mapped[str] = mapped_column(String(32), primary_key=True)  # super_admin|airport_admin|passenger


class RefreshToken(IdMixin, Base):
    __tablename__ = "refresh_tokens"
    user_id: Mapped[uuid.UUID] = fk("users.id", index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mfa: Mapped[bool] = mapped_column(Boolean, default=False)


class Airport(IdMixin, Base):
    __tablename__ = "airports"
    iata: Mapped[str | None] = mapped_column(String(3), index=True, nullable=True)
    icao: Mapped[str | None] = mapped_column(String(4), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str] = mapped_column(String(2), index=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    tz: Mapped[str] = mapped_column(String(64), default="UTC")
    ourairports_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="basic")  # basic|onboarding|verified|suspended
    current_published_version: Mapped[int] = mapped_column(Integer, default=0)
    template_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_review_reminder_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AirportAdmin(IdMixin, Base):
    __tablename__ = "airport_admins"
    __table_args__ = (UniqueConstraint("user_id", "airport_id"),)
    user_id: Mapped[uuid.UUID] = fk("users.id", index=True)
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)


class Invitation(IdMixin, Base):
    __tablename__ = "invitations"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    email: Mapped[str] = mapped_column(String(255))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class Terminal(IdMixin, Base):
    __tablename__ = "terminals"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(10))
    opening_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)


# ---------- onboarding ----------
class QuestionnaireTemplate(IdMixin, Base):
    __tablename__ = "questionnaire_templates"
    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)  # null = global default
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sections: Mapped[list["Section"]] = relationship(
        order_by="Section.order", cascade="all, delete-orphan", lazy="selectin"
    )


class Section(IdMixin, Base):
    __tablename__ = "sections"
    template_id: Mapped[uuid.UUID] = fk("questionnaire_templates.id", index=True)
    key: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    order: Mapped[int] = mapped_column(Integer, default=0)
    questions: Mapped[list["Question"]] = relationship(
        order_by="Question.order", cascade="all, delete-orphan", lazy="selectin"
    )


class Question(IdMixin, Base):
    __tablename__ = "questions"
    section_id: Mapped[uuid.UUID] = fk("sections.id", index=True)
    key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(16))  # text|yesno|number|select|multiselect|time|link
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[list | None] = mapped_column(JSON, nullable=True)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    default_value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    journey: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {flow, scope, order, title}
    order: Mapped[int] = mapped_column(Integer, default=0)


class Answer(IdMixin, Base):
    """Versioned: each edit inserts a new row; the newest version_no per (airport, question) is current."""

    __tablename__ = "answers"
    __table_args__ = (Index("ix_answers_lookup", "airport_id", "question_id", "version_no"),)
    airport_id: Mapped[uuid.UUID] = fk("airports.id")
    question_id: Mapped[uuid.UUID] = fk("questions.id")
    value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    author_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OnboardingProgress(IdMixin, Base):
    __tablename__ = "onboarding_progress"
    __table_args__ = (UniqueConstraint("airport_id"),)
    airport_id: Mapped[uuid.UUID] = fk("airports.id")
    last_section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completeness_pct: Mapped[int] = mapped_column(Integer, default=0)
    went_live_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PublishVersion(IdMixin, Base):
    __tablename__ = "publish_versions"
    __table_args__ = (UniqueConstraint("airport_id", "version_no"),)
    airport_id: Mapped[uuid.UUID] = fk("airports.id")
    version_no: Mapped[int] = mapped_column(Integer)
    published_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


# ---------- generated, versioned content ----------
class JourneyStep(IdMixin, Base):
    __tablename__ = "journey_steps"
    airport_id: Mapped[uuid.UUID] = fk("airports.id")
    version_no: Mapped[int] = mapped_column(Integer)
    flow: Mapped[str] = mapped_column(String(16))  # departure|arrival|transit
    scope: Mapped[str] = mapped_column(String(16))  # domestic|international|both
    order: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text, default="")
    documents: Mapped[list | None] = mapped_column(JSON, nullable=True)
    typical_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tips: Mapped[list | None] = mapped_column(JSON, nullable=True)
    prohibited_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_keys: Mapped[list | None] = mapped_column(JSON, nullable=True)
    __table_args__ = (Index("ix_journey_lookup", "airport_id", "version_no", "flow"),)


class MapNode(IdMixin, Base):
    """version_no == 0 is the editable draft; published copies carry the publish version."""

    __tablename__ = "map_nodes"
    airport_id: Mapped[uuid.UUID] = fk("airports.id")
    version_no: Mapped[int] = mapped_column(Integer, default=0)
    flow: Mapped[str] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(16))
    order: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(100))
    walking_minutes: Mapped[int] = mapped_column(Integer, default=0)  # to next node
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (Index("ix_map_lookup", "airport_id", "version_no", "flow", "scope"),)


class MapEdge(IdMixin, Base):
    __tablename__ = "map_edges"
    airport_id: Mapped[uuid.UUID] = fk("airports.id")
    version_no: Mapped[int] = mapped_column(Integer)
    from_node: Mapped[uuid.UUID] = mapped_column(Uuid)
    to_node: Mapped[uuid.UUID] = mapped_column(Uuid)
    walking_minutes: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class FaqEntry(IdMixin, Base):
    __tablename__ = "faq_entries"
    airport_id: Mapped[uuid.UUID] = fk("airports.id")
    version_no: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    section_key: Mapped[str | None] = mapped_column(String(50), nullable=True)


class KnowledgeDocument(IdMixin, Base):
    __tablename__ = "knowledge_documents"
    airport_id: Mapped[uuid.UUID] = fk("airports.id")
    version_no: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(32))  # answer|pickup_point|support|notice|faq
    source_ref: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))


class KnowledgeChunk(IdMixin, Base):
    __tablename__ = "knowledge_chunks"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    document_id: Mapped[uuid.UUID] = fk("knowledge_documents.id", index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {title, source_type, source_ref}


class Notice(IdMixin, Base):
    __tablename__ = "notices"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info|warning|critical
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ---------- rides & support ----------
class PickupPoint(IdMixin, Base):
    __tablename__ = "pickup_points"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    terminal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zone_name: Mapped[str] = mapped_column(String(150))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    walking_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(10), default="pickup")  # pickup|dropoff


class RideProvider(IdMixin, Base):
    __tablename__ = "ride_providers"
    __table_args__ = (UniqueConstraint("airport_id", "provider_key"),)
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    provider_key: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # e.g. {"info": "...", "phone": "..."}
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class SavedPlace(IdMixin, Base):
    __tablename__ = "saved_places"
    user_id: Mapped[uuid.UUID] = fk("users.id", index=True)
    kind: Mapped[str] = mapped_column(String(10), default="saved")  # home|hotel|work|saved|recent
    label: Mapped[str] = mapped_column(String(100))
    nickname: Mapped[str] = mapped_column(String(150))
    formatted_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)


class SupportChannel(IdMixin, Base):
    __tablename__ = "support_channels"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    type: Mapped[str] = mapped_column(String(16))  # phone|whatsapp|email
    value: Mapped[str] = mapped_column(String(255))
    hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"days":[0-6],"open":"08:00","close":"20:00"}
    out_of_hours_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmergencyContact(IdMixin, Base):
    __tablename__ = "emergency_contacts"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    label: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(50))


# ---------- passenger data ----------
class Ticket(IdMixin, Base):
    __tablename__ = "tickets"
    user_id: Mapped[uuid.UUID] = fk("users.id", index=True)
    airport_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("airports.id"), nullable=True)
    flight_number: Mapped[str] = mapped_column(String(10))
    flight_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    origin: Mapped[str | None] = mapped_column(String(3), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(3), nullable=True)
    pnr_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    passenger_name_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_bcbp_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    pnr_bidx: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    seat: Mapped[str | None] = mapped_column(String(5), nullable=True)
    gate: Mapped[str | None] = mapped_column(String(10), nullable=True)
    terminal: Mapped[str | None] = mapped_column(String(10), nullable=True)
    boarding_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    baggage_allowance: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # scan|manual
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FlightCache(IdMixin, Base):
    __tablename__ = "flights_cache"
    __table_args__ = (UniqueConstraint("airport_id", "flight_key"),)
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    flight_key: Mapped[str] = mapped_column(String(80))
    payload: Mapped[Any] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(IdMixin, Base):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID] = fk("users.id", index=True)
    type: Mapped[str] = mapped_column(String(24))  # gate_change|delay|boarding|ride_reminder
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)


class DeviceToken(IdMixin, Base):
    __tablename__ = "device_tokens"
    user_id: Mapped[uuid.UUID] = fk("users.id", index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True)
    platform: Mapped[str] = mapped_column(String(10), default="expo")


class NotificationPref(Base):
    __tablename__ = "notification_prefs"
    user_id: Mapped[uuid.UUID] = fk("users.id", primary_key=True)
    gate_change: Mapped[bool] = mapped_column(Boolean, default=True)
    delay: Mapped[bool] = mapped_column(Boolean, default=True)
    boarding: Mapped[bool] = mapped_column(Boolean, default=True)
    ride_reminder: Mapped[bool] = mapped_column(Boolean, default=True)


class Consent(IdMixin, Base):
    __tablename__ = "consents"
    __table_args__ = (UniqueConstraint("user_id", "type"),)
    user_id: Mapped[uuid.UUID] = fk("users.id", index=True)
    type: Mapped[str] = mapped_column(String(32))  # analytics
    granted: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------- agent ----------
class AgentConversation(IdMixin, Base):
    __tablename__ = "agent_conversations"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    lang: Mapped[str] = mapped_column(String(10), default="en")


class AgentMessage(IdMixin, Base):
    __tablename__ = "agent_messages"
    conversation_id: Mapped[uuid.UUID] = fk("agent_conversations.id", index=True)
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)  # PII-redacted
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Feedback(IdMixin, Base):
    __tablename__ = "feedback"
    airport_id: Mapped[uuid.UUID] = fk("airports.id", index=True)
    message_id: Mapped[uuid.UUID] = fk("agent_messages.id")
    helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    wrong_answer: Mapped[bool] = mapped_column(Boolean, default=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------- ops ----------
class AnalyticsEvent(IdMixin, Base):
    __tablename__ = "analytics_events"
    airport_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    props: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    session_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    airport_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    before: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    after: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
