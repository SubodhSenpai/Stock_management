# StockSense API

Base path `/api/v1`. All requests and responses are JSON.

Interactive documentation is generated from the code and served by the running app:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI schema: http://localhost:8000/openapi.json

This page covers the conventions those pages do not explain: how sessions work, what the
errors mean, and how paging behaves.

## Authentication

Sessions use two httpOnly cookies, so no script on the page can read either token.

| Cookie | Lifetime | Sent to | Purpose |
|---|---|---|---|
| `access_token` | 15 minutes | every endpoint | Proves who you are |
| `refresh_token` | 7 days | `/api/v1/auth/*` only | Gets a new access token |

The access token is a JWT carrying the user id, its purpose and an expiry. The refresh
token is a random opaque value; only its hash is stored, so a database leak cannot be used
to resume sessions.

**Refresh tokens rotate.** Each call to `/auth/refresh` revokes the token presented and
issues a new one. Presenting a token that was already used means it was copied, so every
session for that user is revoked and both parties must sign in again.

Typical flow:

```
POST /auth/login          -> sets both cookies
GET  /auth/me             -> 200 while the access token is valid
                             401 once it expires (after 15 minutes)
POST /auth/refresh        -> new access token, rotated refresh token
POST /auth/logout         -> revokes the refresh token and clears both cookies
```

A client can simply call `/auth/refresh` whenever a request returns 401, then retry once.

**Every endpoint except the following requires a session**, and returns 401 with no data
otherwise: `/health`, `/auth/signup`, `/auth/login`, `/auth/logout`, `/auth/refresh`,
`/auth/forgot-password`, `/auth/verify-otp`, `/auth/reset-password`.

### Roles

| Capability | Manager | Staff |
|---|:-:|:-:|
| Read everything | yes | yes |
| Receipts, deliveries, transfers, adjustments | yes | yes |
| Create or change products, categories, reorder rules | yes | no |
| Create or change warehouses and locations | yes | no |

Forbidden actions return 403. The UI hides them as well, but the server is what enforces it.

### Rate limits

| Endpoint | Limit |
|---|---|
| `POST /auth/login` | 5 per minute per IP and login id; a success resets the counter |
| `POST /auth/forgot-password` | 3 per 5 minutes per IP and email |

Exceeding a limit returns 429 with `TOO_MANY_REQUESTS`.

## Errors

Every failure uses the same shape, so a client needs one error handler.

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Not enough stock at WH/Stock to validate WH/OUT/0003.",
    "details": [
      { "field": "lines.7", "message": "[DESK001] Desk: asked 6, free 4" }
    ],
    "request_id": "7f3c9a1e"
  }
}
```

`message` is safe to show a user. `details` maps problems onto form fields. `request_id`
also comes back in the `X-Request-ID` header and appears in the server log, so a bug report
can be traced to the exact request.

| Status | Code | Meaning |
|---|---|---|
| 400 | `OTP_INVALID`, `OTP_EXPIRED` | Password reset code rejected |
| 401 | `INVALID_CREDENTIALS` | Sign-in failed |
| 401 | `NOT_AUTHENTICATED` | No session, or it expired: refresh and retry |
| 403 | `FORBIDDEN` | Signed in, but the role does not allow this |
| 404 | `NOT_FOUND` | No such record |
| 409 | `DUPLICATE` | A unique value is already taken |
| 409 | `INVALID_TRANSITION` | That action is not legal from the current status |
| 409 | `INSUFFICIENT_STOCK` | Not enough free stock; `details` lists the short lines |
| 409 | `IN_USE` | Cannot archive or delete something still referenced |
| 422 | `VALIDATION_ERROR` | Request body or query failed validation |
| 422 | `INVALID_LOCATION` | Location is wrong for this document type |
| 422 | `INVALID_QUANTITY` | For example a fraction of a countable unit |
| 422 | `PRODUCT_INACTIVE` | The product is archived |
| 422 | `BELOW_RESERVED` | A count below what is already reserved |
| 429 | `TOO_MANY_REQUESTS` | Rate limited |
| 500 | `INTERNAL_ERROR` | Unexpected; details are logged, never returned |

## Paging

Most list endpoints take `page` (from 1) and `page_size` (1 to 100, default 20):

```json
{ "items": [], "total": 57, "page": 1, "page_size": 20 }
```

**The ledger is different.** `GET /moves` uses a cursor, because the ledger only grows and
an offset would get slower with every page:

```json
{ "items": [], "next_cursor": "MjAyNi0wOS0yNlQxMDoxNTowMFp8NDI" }
```

Pass the value back as `?cursor=`. A null `next_cursor` means the last page.

## Endpoints

### Sessions and profile

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/signup` | Creates the account and signs in |
| POST | `/auth/login` | Rate limited |
| POST | `/auth/refresh` | Rotates the refresh token |
| POST | `/auth/logout` | Revokes this session |
| POST | `/auth/logout-all` | Revokes every session for the user |
| GET | `/auth/me` | The signed-in user |
| POST | `/auth/forgot-password` | Emails a 6-digit code; always answers the same way |
| POST | `/auth/verify-otp` | Exchanges the code for a short-lived reset token |
| POST | `/auth/reset-password` | Sets the password and ends all sessions |
| GET | `/users/me` | Profile |
| PATCH | `/users/me` | Update name or email |
| POST | `/users/me/password` | Change password; signs other sessions out |

### Master data

| Method | Path | Role |
|---|---|---|
| GET, POST | `/warehouses` | read: any, write: manager |
| GET, PATCH, DELETE | `/warehouses/{id}` | write: manager (DELETE archives) |
| GET, POST | `/locations` | read: any, write: manager |
| PATCH, DELETE | `/locations/{id}` | manager |
| GET, POST | `/products` | read: any, write: manager |
| GET, PATCH, DELETE | `/products/{id}` | write: manager (DELETE archives) |
| GET | `/products/{id}/stock` | Per-location breakdown |
| GET, POST | `/categories`, `/reorder-rules` | read: any, write: manager |
| GET | `/uoms` | Units of measure |
| GET, POST | `/partners` | Vendors and customers |

`GET /products` accepts `q` (name or SKU), `category_id`, `warehouse_id` and
`include_archived`. `POST /products` accepts an optional `initial_stock`, which is recorded
as an adjustment document so the ledger still explains those units.

### Operations

| Method | Path | Notes |
|---|---|---|
| GET | `/operations` | Filters: `type`, `status` (repeatable), `warehouse_id`, `location_id`, `partner_id`, `q`, `late` |
| POST | `/operations` | Creates a draft and assigns the reference |
| GET | `/operations/{id}` | Includes per-line availability and `allowed_actions` |
| PATCH | `/operations/{id}` | Drafts only; `lines` replaces the whole set |
| POST | `/operations/{id}/confirm` | Draft to Ready, or Waiting if stock is short |
| POST | `/operations/{id}/check-availability` | Retry a waiting document |
| POST | `/operations/{id}/validate` | Moves the stock and writes the ledger |
| POST | `/operations/{id}/cancel` | Releases any reservation |

**State changes are commands, not a field.** There is no way to set `status` directly, so
illegal jumps such as draft straight to done cannot be expressed.

Each response carries `allowed_actions`, listing exactly which of the above are legal right
now. A client should render its buttons from that list rather than reimplementing the rules.

```
draft ──confirm──> ready ──validate──> done
  │                  ▲
  │                  │ check-availability
  └──confirm──> waiting
(any open state) ──cancel──> canceled
```

Adjustments skip confirm: they go straight from draft to done on validate.

Lines come back with `available_quantity` and `is_available`, which is what lets the UI
mark a line that cannot currently be filled.

### Stock

| Method | Path | Notes |
|---|---|---|
| GET | `/stock` | On hand, reserved and free per product per location |
| POST | `/stock/adjust` | Set a counted quantity; creates and applies an adjustment |
| GET | `/moves` | The ledger, cursor-paginated, newest first |

`free_to_use` is on hand minus reserved. Each move carries `direction` of `in`, `out` or
`internal`, which drives the row colour.

### Dashboard

| Method | Path | Notes |
|---|---|---|
| GET | `/dashboard/summary` | Stock counts plus a card per document type |
| GET | `/dashboard/low-stock` | Items at or below their reorder level |

Card definitions: `late` is open and scheduled before today, `upcoming` is open and
scheduled after today, `to_process` is Ready, `waiting` is waiting on stock.

### Live updates

Connect a WebSocket to `/api/v1/ws` with the session cookie. Events carry identifiers only;
the client refetches over REST, which keeps permission checks in one place.

```json
{ "type": "operation.changed", "operations": [ { "id": 12, "status": "ready" } ] }
{ "type": "stock.changed", "product_ids": [7], "location_ids": [3] }
```

## Validation

Three layers, each catching what the one before it cannot:

1. **Schemas** check shape, type, length, range and format, and reject unknown fields so a
   caller cannot set something the endpoint never offered.
2. **Services** check rules that need the database, such as whether a contact may act as a
   vendor, or whether enough stock is free.
3. **The database** enforces the invariants that must hold no matter what: stock cannot go
   negative, reserved cannot exceed on hand, a line cannot be executed twice, and the
   ledger cannot be edited or deleted.

Layer 3 is not a formality. It is covered by its own tests, which try to break each rule
directly against the database.
