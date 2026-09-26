# StockSense

Inventory management system. Tracks stock across multiple warehouses through receipts,
delivery orders, internal transfers and stock adjustments, with a full audit trail of
every movement.

Built for the Odoo Hackathon 2026.

## Status

Backend is in progress. Done so far:

- Database schema and migrations
- Authentication (signup, login, OTP password reset)
- Test suite (52 tests)

Next: products and warehouses, then the stock engine, then the frontend.

## Stack

| Part | Choice |
|---|---|
| API | FastAPI, Python 3.11+ |
| Database | PostgreSQL 16+ |
| ORM / migrations | SQLAlchemy 2, Alembic |
| Auth | PyJWT + bcrypt, written from scratch |
| Lint / format | ruff (includes bandit security rules) |
| Tests | pytest, against a real database |

No third-party auth, email or realtime services. Everything is built in the app.

## Setup

You need Python 3.11+ and PostgreSQL running locally.

**1. Install dependencies**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

**2. Create the databases**

```bash
psql -U postgres -h localhost -v app_password=<pick-a-password> -f scripts/create_local_db.sql
```

This creates the `stocksense` role plus the `stocksense` and `stocksense_test` databases.

**3. Configure**

Copy `.env.example` to `.env` and fill it in. Use the password you just picked, and
generate the two secrets with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Leave `SMTP_HOST` empty in development. OTP codes are then written to the server log
instead of being emailed, which is enough to test the reset flow.

**4. Migrate and run**

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs
Health check: http://localhost:8000/api/v1/health

## Tests

```bash
cd backend
python -m pytest
```

The suite runs against `stocksense_test` and rebuilds that schema from the migrations,
so the migrations get tested along with the code. Each test runs in a transaction that
is rolled back afterwards.

Lint and formatting:

```bash
ruff check .
ruff format --check .
```

## How the stock model works

Every stock change is recorded as a **move from one location to another**. Vendors,
customers and inventory adjustments are modelled as virtual locations, which means all
four document types are the same operation underneath:

| Document | From | To |
|---|---|---|
| Receipt | Vendors | a warehouse location |
| Delivery | a warehouse location | Customers |
| Internal transfer | one warehouse location | another |
| Adjustment | Inventory Adjustment | a warehouse location (or the reverse) |

Two tables hold stock:

- `stock_moves` is the ledger. Append-only, with a database trigger that rejects updates
  and deletes, so history cannot be rewritten.
- `stock_quants` is the current balance per product per location, written in the same
  transaction as the move. Reading stock is a primary key lookup instead of summing the
  whole ledger.

Because stock only moves between locations, nothing can appear or disappear without a
ledger row explaining it. The two tables can be reconciled with a single query (see
[docs/ER-DIAGRAM.md](docs/ER-DIAGRAM.md)).

## Where things are

```
backend/
  app/
    core/          config, database, errors, logging, security, tokens, rate limiting
    models/        SQLAlchemy models, one file per area
    schemas/       request and response models (Pydantic)
    repositories/  database queries, no business rules
    services/      business logic, owns transactions
    api/v1/        HTTP endpoints
  alembic/         migrations
  tests/           pytest suite
  scripts/         database setup
docs/              ER diagram and schema notes
```

Routers call services, services call repositories. Routers never query the database
directly, and services don't know anything about HTTP.

## Design notes

**Errors** all come back in the same shape, with a machine-readable code, a message
safe to show a user, per-field details for forms, and a request id that matches the
server log:

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Not enough stock at WH/Stock for 1 product.",
    "details": [{ "field": "lines[0].quantity", "message": "asked 6, free 4" }],
    "request_id": "7f3c9a1e"
  }
}
```

**Validation** happens in three places: Pydantic schemas for shape and format, services
for rules that need the database, and check constraints in the schema as a last line of
defence. The database rules are covered by their own tests.

**Security**: passwords are bcrypt hashed, sessions are JWTs in httpOnly cookies, OTP
codes are stored as HMACs, and all queries are parameterised. Login failures and
password reset requests give identical responses whether or not the account exists.

## Documentation

- [Database design and ER diagram](docs/ER-DIAGRAM.md)
- API reference: run the server and open `/docs`
