# Airpal backend

FastAPI + PostgreSQL (pgvector) + Redis + Celery. API under `/api/v1`, docs at `/docs`.

## Run

```bash
cp .env.example .env            # set DATA_ENCRYPTION_KEY, JWT_SECRET for anything non-local
docker compose -f ../docker-compose.yml up -d db redis
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.import_airports          # OurAirports -> "basic" airports
.venv/bin/python -m scripts.create_super_admin you@x.com 'LongPassword123'
.venv/bin/python -m scripts.seed_demo                # optional: published demo airport (CMB)
.venv/bin/uvicorn app.main:app --reload
.venv/bin/celery -A app.workers.celery_app worker -B -l info   # background jobs
.venv/bin/python -m pytest
```

## Key behaviours

- **Tenancy**: every portal route is `/portal/airports/{airport_id}/...` guarded by `require_airport_admin` (membership + 2FA). Tenant tables carry `airport_id`; all queries filter on it.
- **Onboarding**: Super Admin approves airport -> invite -> admin sets password, enables 2FA -> wizard (autosave) -> publish. Publish requires all required answers plus pickup point and support channel, then generates journey steps, map flow, FAQ and embedded knowledge chunks as a new immutable version. Editing while live republishes.
- **Agent**: retrieval is restricted to the airport's current published version; tools add live flight/weather/ticket/ride/support data; unanswerable questions return "I'm not sure" plus customer-care options. Messages are PII-redacted.
- **Providers** (swap via env): flights (`mock`, `aerodatabox`), routing (`osrm`, `google`, `haversine`), LLM (`extractive` needs no key, `anthropic`), embeddings (`hash`, `openai`).
- **Rides**: Uber via deep links (no API approval). `UberRidesApiProvider` is the extension point for in-app booking. Bolt/PickMe/Grab are link stubs.
- **Privacy**: PNR, passenger name and raw boarding pass are AES-GCM encrypted; `DELETE /me` erases personal data; analytics only with consent; retention job purges old tickets/messages.
- Email delivery (verification, invitations, review reminders) is logged, not sent: wire an SMTP/provider in `approve` and `review_reminders`. In non-prod, invite and verify tokens are returned in responses.
