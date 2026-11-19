# Shop API

FastAPI + async SQLAlchemy 2.0 + PostgreSQL. Python 3.12.
Dependencies are managed with pip in a virtual environment (.venv).

## Testing (TDD)
- Tests first. Never write implementation before a failing test exists.
- A test must fail for the right reason (assertion or wrong status),
  not ImportError or a fixture error.
- Never edit, skip, xfail or loosen a test to make it pass.
  If a test is wrong, stop and explain why.
- Test behaviour through the API (client fixture) or service functions;
  don't assert on private internals.
- Use the real test database; mock only external HTTP (respx) and time.
- Done = `bash scripts/check.sh` exits 0.

## Commands
- Activate the environment: `source .venv/bin/activate`
- Install deps: `pip install -r requirements-dev.txt`
- Start test DB: `docker compose -f docker-compose.test.yml up -d`
- Run all checks: `bash scripts/check.sh`
- Run one test file: `pytest tests/api/test_order_cancel.py -q`
- Dev server: `uvicorn app.main:app --reload`

## Architecture
- app/routers/  -> HTTP layer only: parse input, call a service, return a schema
- app/services/ -> business rules; no FastAPI imports here
- app/models/   -> SQLAlchemy models (import new models in app/models/__init__.py)
- app/schemas.py -> Pydantic request/response models
- Errors: raise HTTPException with detail={"code": "UPPER_SNAKE_CASE"}
  for business errors
