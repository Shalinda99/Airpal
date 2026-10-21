import os
import tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["ENV"] = "test"
os.environ["REDIS_URL"] = ""
os.environ["FLIGHT_PROVIDER"] = "mock"
os.environ["ROUTING_PROVIDER"] = "haversine"
os.environ["LLM_PROVIDER"] = "extractive"

import pyotp  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import crypto  # noqa: E402
from app.core.cache import cache_clear  # noqa: E402
from app.core.security import hash_password, new_totp_secret  # noqa: E402
from app.db import models  # noqa: E402, F401
from app.db.base import Base  # noqa: E402
from app.db.models import Airport, AirportAdmin, User, UserRole  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    cache_clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


def make_airport(db, iata="CMB", **kw):
    ap = Airport(iata=iata, icao="VCBI", name=f"{iata} Airport", city="X", country="LK", lat=7.18, lon=79.88,
                 tz="Asia/Colombo", status="onboarding", **kw)
    db.add(ap)
    db.commit()
    return ap


def make_admin(db, client, airport, email="admin@x.com", role="airport_admin"):
    user = User(email=email, password_hash=hash_password("Password123!"))
    user.roles.append(UserRole(role=role))
    secret = new_totp_secret()
    user.totp_secret_enc = crypto.encrypt(secret)
    user.totp_enabled = True
    db.add(user)
    db.flush()
    if airport:
        db.add(AirportAdmin(user_id=user.id, airport_id=airport.id))
    db.commit()
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!",
                                                 "otp": pyotp.TOTP(secret).now()})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def guest_headers(client):
    r = client.post("/api/v1/auth/guest")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
