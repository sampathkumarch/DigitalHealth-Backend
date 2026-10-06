# Health Backend

Python API built with [FastAPI](https://fastapi.tiangolo.com/).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs

## Test

```bash
pytest
```

## How we work

Architecture, tickets, and branch names are in [CONTRIBUTING.md](CONTRIBUTING.md). `master` is the only long-lived branch.
