"""Seed a demo airport (Colombo CMB) with a fully answered questionnaire, published. python -m scripts.seed_demo"""

from sqlalchemy import select

from app.db.models import Airport, PickupPoint, RideProvider, SupportChannel
from app.db.session import SessionLocal
from app.modules.onboarding import service

ANSWERS = {
    "terminals": "Terminal 1: all international and domestic flights.",
    "opening_hours": "Open 24 hours",
    "languages": ["en", "si", "ta"],
    "checkin_hours": "Check-in opens 3 hours before departure and closes 60 minutes before departure.",
    "bag_drop_cutoff": 60,
    "queue_checkin_minutes": 15,
    "security_rules": "All passengers and hand luggage are screened. Remove laptops and belts.",
    "liquids_rule": "Liquids in containers up to 100ml, all in one transparent 1 litre bag.",
    "prohibited_items": "Sharp objects\nFirearms\nFlammable liquids",
    "queue_security_minutes": 20,
    "emigration_process": "Present passport and boarding pass at the emigration counters.",
    "boarding_close_minutes": 15,
    "immigration_process": "Present passport, arrival card and visa/ETA at the immigration counters.",
    "immigration_minutes": 25,
    "baggage_claim": "Baggage belts are shown on the arrivals screens after landing.",
    "baggage_minutes": 25,
    "lost_baggage": "Report missing bags to your airline's baggage desk before leaving the hall.",
    "customs_rules": "Declare goods above the duty free allowance at the red channel.",
    "transit_rules": "Transit passengers stay airside and follow signs to the transfer desk.",
    "wifi": "Free Wi-Fi: connect to 'Airport-Free' and accept terms.",
    "accessibility": "Wheelchair assistance can be arranged through your airline at least 48 hours before travel.",
    "gate_walking_times": "A1-A10: 8\nB1-B12: 12",
    "ground_overview": "Taxis, ride-hailing and airport buses are available outside arrivals.",
    "rideshare_notes": "Ride-hailing pickup is at the Car Park B, level 1.",
    "emergency_number": "117",
}


def main() -> None:
    with SessionLocal() as db:
        service.ensure_default_template(db)
        ap = db.scalar(select(Airport).where(Airport.iata == "CMB"))
        if not ap:
            ap = Airport(iata="CMB", icao="VCBI", name="Bandaranaike International Airport", city="Colombo",
                         country="LK", lat=7.1808, lon=79.8841, tz="Asia/Colombo", status="onboarding")
            db.add(ap)
            db.flush()
        qs = {q.key: q for s in service.resolve_template(db, ap).sections for q in s.questions}
        for k, v in ANSWERS.items():
            service.save_answer(db, ap.id, qs[k], v, None)
        if not db.scalar(select(PickupPoint).where(PickupPoint.airport_id == ap.id)):
            db.add(PickupPoint(airport_id=ap.id, terminal="T1", level="1", zone_name="Car Park B", lat=7.1795,
                               lon=79.8870, walking_instructions="Exit arrivals, turn right, follow the Ride signs."))
            db.add(RideProvider(airport_id=ap.id, provider_key="uber", display_order=0))
            db.add(RideProvider(airport_id=ap.id, provider_key="taxi_desk", display_order=1,
                                config={"info": "Official taxi desk in the arrivals hall, fixed prices."}))
            db.add(SupportChannel(airport_id=ap.id, type="phone", value="+94 11 2 264 444",
                                  hours={"days": [0, 1, 2, 3, 4, 5, 6], "open": "08:00", "close": "20:00"},
                                  out_of_hours_message="Customer care is closed. Call again from 08:00."))
        db.commit()
        print(service.publish(db, ap, None), ap.id)


if __name__ == "__main__":
    main()
