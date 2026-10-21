# Airpal

Multi-airport passenger platform: FastAPI backend (`backend/`) and Expo React Native app (`mobile/`).

## Quick start (local)

```bash
docker compose up -d db redis                 # Postgres+pgvector, Redis
cd backend
cp .env.example .env
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed_demo         # published demo airport (CMB) with mock flights
.venv/bin/uvicorn app.main:app --reload       # http://localhost:8000/docs

cd ../mobile
cp .env.example .env                          # EXPO_PUBLIC_API_URL (Android emulator: http://10.0.2.2:8000/api/v1)
npm install
npm run typecheck && npm test
npx expo start
```

Push notifications, camera scanning and the Uber deep link need a physical device or a development build (`eas build --profile development`).

## Production checklist

- **Secrets**: set `ENV=prod`, a strong `JWT_SECRET`, `DATA_ENCRYPTION_KEY`, `BLIND_INDEX_KEY` (the API refuses to start with the dev defaults). Never commit `.env`.
- **Infra**: managed Postgres with the `vector` extension, managed Redis, TLS in front of the API (reverse proxy / load balancer). Run `alembic upgrade head` on deploy. Run one `worker` (Celery with beat) for flight refresh, notifications, reminders and retention.
- **Providers**: `FLIGHT_PROVIDER=aerodatabox` + key, `LLM_PROVIDER=anthropic` + key, `EMBEDDING_PROVIDER=openai` + key (changing the embedding provider or `EMBEDDING_DIM` requires republishing airports to re-embed), `ROUTING_PROVIDER=google|osrm` (the public OSRM demo server is not for production load).
- **Email**: invitations, email verification and review reminders are only logged. Plug a provider into `admin.approve`, `auth.register` and `workers.tasks.review_reminders` before launch.
- **Mobile**: set the EAS project id in `mobile/app.json`, API URLs in `mobile/eas.json`, then `eas build --profile production`. Store listings need a privacy policy covering camera, location, notifications and the data described below.
- **Privacy**: boarding-pass fields are encrypted at rest, tickets and old chat/analytics rows are purged by the retention job, analytics are consent-gated, `DELETE /me` erases an account.
- **Not included**: the airport admin web portal (all of its APIs exist under `/portal/...` and `/admin/...`), localisation of the app UI, and an on-device map (the "map flow" is a step-by-step route).
- CI is in `.github/workflows/ci.yml` (ruff + pytest, typecheck + jest). Commit `mobile/package-lock.json` after the first `npm install`, since CI uses `npm ci`.
