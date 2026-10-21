from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Airport, JourneyStep
from app.modules.journey.router import serialize_step
from app.modules.onboarding import service


def build_preview(db: Session, airport: Airport) -> dict:
    """Generate journey from current draft answers inside a transaction that is rolled back."""
    tpl = service.resolve_template(db, airport)
    answers = service.latest_answers(db, airport.id)
    qa = [(qn, sec, answers[qn.id].value if qn.id in answers else None) for sec in tpl.sections
          for qn in sec.questions]
    service.generate_journey(db, airport, -1, qa)
    db.flush()
    steps = list(db.scalars(select(JourneyStep).where(JourneyStep.airport_id == airport.id,
                                                      JourneyStep.version_no == -1)
                            .order_by(JourneyStep.flow, JourneyStep.order)))
    out = [serialize_step(s) for s in steps]
    db.rollback()
    return {"steps": out, "completeness": service.wizard_state(db, airport)["completeness_pct"]}
