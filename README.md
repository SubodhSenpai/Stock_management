# StockSense

Inventory management system. Tracks stock across multiple warehouses through receipts,
delivery orders, internal transfers and stock adjustments, with a full audit trail of
every movement.

Built for the Odoo Hackathon 2026.

## Status

Backend and frontend are both in place: **53 endpoints, 148 backend tests, 22 pages**.

- Database schema and migrations
- Authentication: sign-up, sign-in, rotating refresh tokens, OTP password reset
- Warehouses, locations, products, categories, contacts, reordering rules
- Stock engine: receipts, deliveries, internal transfers, adjustments
- Stock page, move history, dashboard KPIs
- Live updates over WebSocket
- Next.js interface in the Odoo style: list and kanban views, form views with a status
  bar, printable picking slips

To check any of that for yourself, see [Testing](#testing). The test, report, load-test
and smoke-test scripts are all in the repo.

## Stack

| Part | Choice |
|---|---|
| API | FastAPI, Python 3.11+ |
| Database | PostgreSQL 16+ |
| ORM / migrations | SQLAlchemy 2, Alembic |
| Auth | PyJWT + bcrypt, written from scratch |
| Live updates | WebSocket, no third-party service |
| Web | Next.js 15 (App Router), React 19, TypeScript strict |
| Styling | Tailwind CSS 4, themed to match Odoo |
| Client validation | Zod, mirroring the Pydantic rules |
| Lint / format | ruff (includes bandit security rules), ESLint |
| Tests | pytest against a real database; an HTTP smoke test for the web app |
| Load testing | httpx, in `scripts/loadtest.py` |

No third-party auth, email, realtime, state-management, form or component library.
Everything above is either the framework itself or written in the app.

## Setup

You need Python 3.11+, Node 20+ and PostgreSQL running locally.

### Backend

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

### Frontend

In a second terminal, with the API already running:

```bash
cd frontend
npm install
cp .env.example .env.local     # Windows: copy .env.example .env.local
npm run dev
```

Open http://localhost:3000 and sign in with the same demo accounts.

`.env.local` points the browser at the API. The default matches the backend's
`FRONTEND_ORIGIN`; if you change one, change the other, or the browser will drop the
session cookie on a CORS failure.

## Testing

Everything needed to check this project is in the repo. Run it yourself rather than taking
the numbers below on trust.

### 1. The backend test suite

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

### 4. End-to-end smoke test

With both servers running and the database seeded:

```bash
cd frontend
npm run smoke
```

29 checks over real HTTP against both processes: that a signed-out visitor is redirected,
that an anonymous API call returns 401 and no data, that signing in sets both cookies and
that CORS allows them, that all 12 signed-in pages render, and that every list endpoint
returns the shape the pages are built on. Nothing is mocked, so it catches the things that
work in isolation and break in combination.

### 5. Code quality checks

```bash
cd backend
ruff check .            # lint, including bandit security rules
ruff format --check .   # formatting
python -m alembic check # models and migrations still agree

cd ../frontend
npm run typecheck       # tsc --noEmit, strict mode
npm run lint            # ESLint
npm run build           # production build
```

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
frontend/
  src/
    app/           routes: (auth) signed out, (app) signed in
    components/    ui/ primitives, then one folder per area
    lib/
      api/         one module per resource; the only place fetch is called
      config/      the operation, status and navigation tables
      hooks/       useResource, useForm, useAction, useUrlFilters
      validation/  Zod schemas mirroring the Pydantic rules
    providers/     session, realtime, toasts
    types/api.ts   TypeScript mirrors of the API's response models
  scripts/         smoke test
docs/              ER diagram and schema notes
```

Routers call services, services call repositories. Routers never query the database
directly, and services don't know anything about HTTP.

On the frontend the same idea applies: pages compose components, components call the
API modules, and nothing above `lib/api` calls `fetch`. Cookies, token refresh and the
error contract are therefore handled once.

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

## The interface

The app follows Odoo's own conventions, so anyone who has used Odoo already knows where
things are: the plum application bar, a control panel above every list with the search
and the view switcher, list and kanban views of the same records, and a form view on a
white sheet with the status bar in the top right.

**Four document types, one screen.** Receipts, deliveries, transfers and adjustments are
one engine on the backend, so they are one set of components here. What differs between
them — the labels, which locations the user picks, the statuses, whether a quantity is
moved or counted — is a row in `lib/config/operations.ts`. A fifth document type would be
a row, not another copy of the page.

**Buttons come from the server.** `ActionBar` renders exactly the actions in the
document's `allowed_actions`. The state machine is not reimplemented in the client, so
the UI cannot offer something the server would refuse, or hide something it would allow.

**Validation is written once per rule, checked on both sides.** `lib/validation/rules.ts`
mirrors `backend/app/schemas/fields.py` field for field — the same lengths, the same
patterns, the same password rules. The browser copy exists so a typo is caught before a
round trip; the server copy is the one that decides. When the server does reject
something, its `details[].field` paths use the same format the client's own errors do,
so both land on the right input.

**Quantities stay strings.** The API sends `NUMERIC` columns as JSON strings, and they
are kept that way through the form and back. Parsing them into floats would reintroduce
exactly the rounding the database was chosen to avoid.

**Nothing above `lib/api` calls fetch.** Session cookies, the transparent refresh on a
401 and the error contract are handled in one file. The refresh is single-flight: several
requests can fail at once, and rotating the token more than once would look like a stolen
token to the backend, which revokes every session when it sees one reused.

**Every list has four states** — loading skeleton, empty with a call to action, error
with the request id and a retry, and the data itself. Filters live in the URL, so a
filtered list can be shared and survives a refresh.

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
- [Testing](#testing) - how to run the suite, the report, the load test and the smoke
  test yourself

### Scripts

| Script | What it does |
|---|---|
| `backend/scripts/seed.py` | Loads demo data; safe to re-run |
| `backend/scripts/loadtest.py` | Concurrent load test, writes `reports/LOAD-TEST.md` |
| `backend/scripts/create_local_db.sql` | One-time database and role setup |
| `backend/tests/qa_report.py` | The `--qa-report` plugin, writes `reports/TEST-REPORT.md` |
| `frontend/scripts/smoke.mjs` | End-to-end check of both servers; `npm run smoke` |
