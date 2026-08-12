# 🎟️ High-Concurrency Flash Sale API

A production-hardened REST API for high-traffic ticketing "flash sale" events. Built with **FastAPI** and **PostgreSQL**, the system uses **pessimistic row-level locking** to guarantee zero overselling under genuinely concurrent load — proven three separate ways: an automated test suite, a standalone async load-testing script, and live, manual two-browser-tab verification.

A companion **React frontend** consumes this API end-to-end (auth, browsing, purchasing, order history, admin management): **[flash-sale-frontend](https://github.com/ayushk-codes/flash-sale-frontend)**.

---

## 🚀 Architectural Highlights

- **Concurrency Management** — `SELECT FOR UPDATE` row-level locking on the event being purchased ensures that under simultaneous purchase requests, exactly as many succeed as there are tickets available — never more.
- **Database Migrations** — Alembic manages every schema change as a versioned, reversible migration; no destructive `create_all()` in production.
- **Stateless Authentication** — JWT-based sessions with Bcrypt password hashing, strength-validated passwords, and rate-limited login to resist brute-force attempts.
- **Historical Data Integrity** — Order records snapshot the event's name and price at the exact moment of purchase, so order history remains permanently accurate even if the underlying event is later deleted (`ON DELETE SET NULL`).
- **API Versioning** — all routes live under `/api/v1/`, allowing future breaking changes without disrupting existing clients.
- **Environment-Driven Configuration** — connection pool sizing, rate limits, background-task delays, and CORS origins are all configurable via environment variables with safe, production-appropriate defaults — never hardcoded.
- **Automated Test Suite** — 11 tests across 4 files (auth, events/RBAC, orders, concurrency), running against an isolated test database with full parity to production (same PostgreSQL engine, same synchronous driver).
- **Real-Time Inventory Updates** — a WebSocket channel per event broadcasts the live ticket count to every connected client the instant a purchase commits, so concurrent buyers see availability change as it happens — no polling, no manual refresh.
- **Containerized Infrastructure** — Docker + Docker Compose for identical local and deployed environments, running as a non-root user in production for defense-in-depth.

---

## 🛠️ Tech Stack

**Backend:** FastAPI (Python 3.11) · PostgreSQL 15 · SQLAlchemy · Alembic · PyJWT · bcrypt / passlib · slowapi (rate limiting) · Pydantic
**Testing:** pytest · pytest-asyncio · httpx
**Infrastructure:** Docker · Docker Compose

---

## 💻 Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/ayushk-codes/high-concurrency-flash-sale-api.git
cd high-concurrency-flash-sale-api
```

### 2. Configure environment variables

Create a `.env` file in the root directory. A full template with explanations for every variable lives in **`.env.example`** — copy it as a starting point:

```bash
cp .env.example .env
```

At minimum, set real values for these before starting anything:

```env
# --- Database ---
DB_PASSWORD=your_secure_password_here
DATABASE_URL=postgresql://admin:your_secure_password_here@db:5432/ticket_db

# --- JWT Security ---
SECRET_KEY=generate_a_secure_random_string_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# --- Frontend Integration (for CORS) ---
FRONTEND_URL=http://localhost:5173

# --- Seeding — set this to something real before running seed.py ---
DEMO_ADMIN_PASSWORD=change_this_before_seeding
```

`.env.example` also documents connection-pool sizing, rate limiting, background-task delay, and testing-specific variables — all with safe defaults.

### 3. Start the infrastructure

```bash
docker compose up -d --build
```

The API is now live at `http://localhost:8000`. Interactive Swagger docs: `http://localhost:8000/docs`.

### 4. Run database migrations

Schema is managed entirely through Alembic — nothing is created automatically on startup.

```bash
docker compose exec web alembic upgrade head
```

### 5. Seed the database

Creates 1 admin (`superadmin`), 5 regular test users (`testuser1`–`testuser5`, password `password123`), and 50 randomly priced events.

```bash
docker compose exec web python seed.py
```

> ⚠️ **Before running this anywhere beyond a fully local, disposable database**, make sure `DEMO_ADMIN_PASSWORD` in `.env` is set to a real value — it is _not_ safe to leave on its fallback default outside local development.

The script is safely re-runnable: users and events are seeded independently, each with its own idempotency check, so re-running it won't duplicate existing data.

---

## 🧪 Testing

### Automated suite

```bash
# One-time setup: a second, fully isolated database for tests
docker compose exec db psql -U admin -c "CREATE DATABASE ticket_db_test;"

# Install test dependencies
pip install -r requirements-dev.txt

# Run everything
pytest -v
```

11 tests across 4 files — authentication, event management & RBAC, ticket purchasing & order history, and concurrency — all running against a database that mirrors production exactly (same PostgreSQL engine, same synchronous driver), so the concurrency test genuinely exercises real row-level locking rather than an approximation of it.

### Manual concurrency proof

A standalone async load-testing script fires 50 simultaneous purchase requests at a single event via `asyncio.gather`, independent of the test suite:

```bash
# 1. Log in via /docs to get a JWT
# 2. Add it to .env: TEST_ACCESS_TOKEN=your_real_token
python stress_test.py
```

Against an event with, say, 10 tickets remaining: exactly 10 requests succeed, exactly 40 receive a clean `"Sold out!"` response — zero database race conditions, zero overselling, every time.

---

## 📡 Core API Endpoints

All routes are prefixed with `/api/v1`. Full interactive documentation at `/docs`.

| Method   | Endpoint                 | Description                               | Auth  |
| -------- | ------------------------ | ----------------------------------------- | ----- |
| `POST`   | `/register`              | Register a new user                       | No    |
| `POST`   | `/login`                 | Authenticate, receive JWT (rate-limited)  | No    |
| `GET`    | `/users/me`              | Current user's profile                    | Yes   |
| `PUT`    | `/users/change-password` | Change password                           | Yes   |
| `GET`    | `/events`                | Paginated, searchable event listing       | No    |
| `GET`    | `/events/{id}`           | Single event details                      | No    |
| `POST`   | `/events`                | Create an event                           | Admin |
| `DELETE` | `/events/{id}`           | Delete an event                           | Admin |
| `POST`   | `/orders`                | Purchase a ticket                         | Yes   |
| `GET`    | `/orders/me`             | Your order history                        | Yes   |
| `WS`     | `/ws/events/{event_id}`  | Live ticket-count broadcast for one event | No    |

---

## 🏗️ Design Decisions Worth Knowing

**Event modification (`PUT /events/{id}`) was deliberately excluded.** Changing `total_tickets`/`available_tickets` while a purchase's `SELECT FOR UPDATE` lock is actively held on that same row introduces genuine concurrency ambiguity — this boundary was chosen to preserve strict atomic invariants on ticket counts rather than patch around a race condition later.

**Order history is snapshotted, not live-joined.** `event_name` and `event_price` are copied onto each order at the moment of purchase, rather than read live from the `Event` table. This means a deleted event never corrupts or erases past order history — a real e-commerce/ticketing pattern, not just a convenience.

**Configuration over hardcoding, everywhere.** Connection pool size, login rate limits, background-task delays, and CORS origins are all environment-driven with safe production defaults — the same values ship to local development, automated tests, and (eventually) production, without code changes between environments.

**Real-time updates are in-memory, not distributed.** The WebSocket connection manager tracks subscribers in a plain in-process dictionary, which is the right call for a single-instance deployment but wouldn't survive horizontal scaling as-is — a second instance's clients wouldn't see broadcasts triggered on the first without adding a shared layer like Redis pub/sub. Noted here as a known, deliberate boundary of the current scale, not an oversight.

---

## 🔗 Frontend

The companion React SPA lives in a separate repository and consumes this API entirely over HTTP — no shared code, no build-time coupling, just a configured base URL:

**[flash-sale-frontend](https://github.com/ayushk-codes/flash-sale-frontend)**

It implements the full user journey — registration, login, event browsing with search/pagination, ticket purchasing with live inventory feedback, order history, and an admin management panel — all backed by the endpoints documented above.
