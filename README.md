# Health Backend

Python API built with [FastAPI](https://fastapi.tiangolo.com/).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
alembic upgrade head
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
celery -A app.worker.celery_app worker --loglevel=info
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs
- Liveness: `GET /health`
- Database and Redis: `GET /ready`

WhatsApp, email, and S3 stay idle until the keys in `.env` are filled in. Until then, login codes are stored on `otp_challenges` and profile photos are written under `var/uploads`. Set `OTP_STORE_PLAINTEXT=false` and `OTP_EXPOSE_IN_RESPONSE=false` outside local development.

Accounts are split across `users`, `roles`, `user_profiles`, `user_conditions`, `user_diagnoses`, `disease_categories`, `diseases`, `files`, `otp_challenges`, and `refresh_tokens`. Business routes are under `/api/v1`.

Signed-in members can search `GET /api/v1/diseases` and `GET /api/v1/disease-categories`, then save their own selections with `GET`, `POST`, `PUT`, and `DELETE /api/v1/me/diagnoses`. A typed name that is not in the catalog is stored on that user's diagnosis row and is not added to `diseases`. Creating or changing catalog rows requires `users.role_id` pointing at the `admin` role. Signup still assigns `member`.

## Test

```bash
pytest
```

## How we work

Architecture, tickets, and branch names are in [CONTRIBUTING.md](CONTRIBUTING.md). `master` is the only long-lived branch.
