# StockSense

Inventory management system. Tracks stock across multiple warehouses through receipts,
delivery orders, internal transfers and stock adjustments, with a full audit trail of
every movement.

Built for the Odoo Hackathon 2026.

## Status

Backend is complete: **53 endpoints, 148 tests**. Frontend is next.

- Database schema and migrations
- Authentication: sign-up, sign-in, rotating refresh tokens, OTP password reset
- Warehouses, locations, products, categories, contacts, reordering rules
- Stock engine: receipts, deliveries, internal transfers, adjustments
- Stock page, move history, dashboard KPIs
- Live updates over WebSocket

To check any of that for yourself, see [Testing the backend](#testing-the-backend). The
test, report and load-test scripts are all in the repo.

## Stack

| Part | Choice |
|---|---|
| API | FastAPI, Python 3.11+ |
| Database | PostgreSQL 16+ |
| ORM / migrations | SQLAlchemy 2, Alembic |
| Auth | PyJWT + bcrypt, written from scratch |
| Live updates | WebSocket, no third-party service |
| Lint / format | ruff (includes bandit security rules) |
| Tests | pytest, against a real database |
| Load testing | httpx, in `scripts/loadtest.py` |

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

**4. Migrate, seed and run**

```bash
python -m alembic upgrade head
python -m scripts.seed
python -m uvicorn app.main:app --reload
```

The seed script loads demo data and can be re-run safely. Sign in with `manager1` /
`Manager@123`, or `staff001` / `Staff@1234` to see the warehouse staff view.

API docs: http://localhost:8000/docs
Health check: http://localhost:8000/api/v1/health

## Testing the backend

Everything needed to check this project is in the repo. Run it yourself rather than taking
the numbers below on trust.

### 1. The test suite

```bash
cd backend
python -m pytest
```

148 tests, about 45 seconds. They run against the `stocksense_test` database, which is
rebuilt from the migrations on each run, so the migrations are covered too. Most tests run
inside a transaction that is rolled back; the concurrency tests commit deliberately and
clear up after themselves.

| Area | Cases | What it covers |
|---|---:|---|
| Inventory engine | 35 | Reservation, waiting to ready, transfers, adjustments, state machine |
| Authentication | 34 | Sign-up, sign-in, the OTP reset flow, profile |
| Security | 29 | Auth on every route, refresh tokens, injection, error leakage |
| REST API | 27 | Permissions, error contract, filters, cursor paging |
| Database integrity | 18 | Constraints and the append-only ledger trigger |
| Concurrency | 5 | Overselling, double validation, reference races |

Useful subsets:

```bash
python -m pytest tests/test_security.py -v      # every route rejects anonymous callers
python -m pytest tests/test_concurrency.py -v   # real threads competing for stock
python -m pytest -k "waiting" -v                # one behaviour across the suite
```

### 2. A readable test report

```bash
python -m pytest --qa-report
```

Writes `backend/reports/TEST-REPORT.md`: every case with its scenario, why it matters, and
the actual result, grouped by area.

### 3. Load and concurrency test

Start the server and seed the database first, then:

```bash
python -m scripts.loadtest --users 50 --requests 20
```

It signs in 50 clients, fires 1000 concurrent reads, then has all 50 compete for the *same*
product to show the locking holds. Results go to `backend/reports/LOAD-TEST.md`.

Add `--skip-rate-limit-check` to re-run immediately; otherwise the last step deliberately
trips the login limiter, which blocks sign-ins for a minute.

Measured on one developer machine:

| Setup | Throughput | p50 | p95 | Failures |
|---|---:|---:|---:|---:|
| 1 user (baseline) | - | 8-20ms | 140ms | 0 |
| 50 users, 1 worker | 85 req/s | ~560ms | ~870ms | 0 |
| 50 users, 4 workers | 144 req/s | ~220ms | ~680ms | 0 |
| 30 users, 4 workers | 246 req/s | ~100ms | ~250ms | 0 |

Individual queries take 8-20ms, so the figures under load are queueing rather than slow
queries: a single Python process becomes CPU-bound. The API keeps no state between
requests, so throughput scales by adding workers:

```bash
python -m uvicorn app.main:app --workers 4
```

### 4. Code quality checks

```bash
ruff check .            # lint, including bandit security rules
ruff format --check .   # formatting
python -m alembic check # models and migrations still agree
```

All four commands are also run by CI on every push.

**Reports are not committed.** `backend/reports/` is git-ignored, because both files are
regenerated on every run and the load numbers depend on the machine. The scripts that
produce them are in the repo, so anyone can reproduce the results.

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

**Sessions** use two httpOnly cookies: a 15-minute access token and a 7-day refresh token
scoped to the auth endpoints. Refresh tokens rotate on every use and only their hash is
stored. Presenting one that was already used means it was copied, so every session for
that user is revoked.

**Security**: passwords are bcrypt hashed, all queries are parameterised, OTP codes are
stored as HMACs, and unknown request fields are rejected. Login failures and password
reset requests answer identically whether or not the account exists. A test walks every
route in the app and fails if any of them answers without a session.

## Notable behaviour

**Reserving stock.** Confirming a delivery or transfer sets stock aside, which is what
makes "free to use" different from "on hand". Reservation is all or nothing: if any line
is short, nothing is reserved, the document goes to Waiting and the UI marks the lines
that cannot be filled.

**Waiting documents free themselves.** When a receipt is validated, any waiting document
that needs those products at that location is re-checked, oldest schedule date first. If
it can now be filled it becomes Ready without anyone touching it.

**State changes are commands.** `POST /operations/{id}/validate`, not a status field the
client sets. Illegal jumps like draft straight to done cannot even be expressed, and each
response carries `allowed_actions` so the UI renders buttons without repeating the rules.

**Concurrency.** Stock rows are locked in a fixed order before being read or changed, so
two people validating at once cannot oversell, and cannot deadlock. Validating the same
document twice is refused by the state machine, and a unique constraint on the ledger
makes it impossible even if that check were bypassed.

## Documentation

- [API reference](docs/API.md) - sessions, errors, paging and the endpoint list
- [Database design and ER diagram](docs/ER-DIAGRAM.md)
- Interactive API docs: run the server and open `/docs`
- [Testing the backend](#testing-the-backend) - how to run the suite, the report and the
  load test yourself

### Scripts

| Script | What it does |
|---|---|
| `backend/scripts/seed.py` | Loads demo data; safe to re-run |
| `backend/scripts/loadtest.py` | Concurrent load test, writes `reports/LOAD-TEST.md` |
| `backend/scripts/create_local_db.sql` | One-time database and role setup |
| `backend/tests/qa_report.py` | The `--qa-report` plugin, writes `reports/TEST-REPORT.md` |
