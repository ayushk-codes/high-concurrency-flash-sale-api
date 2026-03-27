# 🎟️ High-Concurrency Flash Sale API

A robust, production-ready REST API designed to handle high-traffic "Flash Sale" ticketing events. Built with **FastAPI** and **PostgreSQL**, this backend architecture utilizes **Pessimistic Row Locking** to flawlessly manage concurrent purchase requests and strictly prevent ticket overselling.

## 🚀 Architectural Highlights

* **Concurrency Management:** Implements SQLAlchemy `SELECT FOR UPDATE` to lock database rows during transactions, guaranteeing absolute data integrity during massive traffic spikes.
* **Stateless Authentication:** Secure, stateless sessions using heavily encrypted **JWT (JSON Web Tokens)** and Bcrypt password hashing.
* **Separation of Concerns:** Strict architectural boundaries using Pydantic DTOs (Data Transfer Objects) to separate incoming payload validation from outgoing response serialization, preventing data leaks.
* **Containerized Infrastructure:** Fully containerized using **Docker** and ````docker-compose```` for guaranteed parity between local development and production environments.
* **Idempotent Database Seeding:** Automated dummy-data generation script (`seed.py`) for rapid local testing and live demo staging.

## 🛠️ Tech Stack

* **Framework:** FastAPI (Python 3.9+)
* **Database:** PostgreSQL
* **ORM:** SQLAlchemy
* **Authentication:** PyJWT & passlib (Bcrypt)
* **Containerization:** Docker & Docker Compose
* **Validation:** Pydantic

---

## 💻 Local Development Setup

Follow these steps to get the environment running on your local machine.

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory. You must define both the Docker initialization password and the SQLAlchemy connection URL. **Ensure the passwords match.**

```env
# --- Database Configuration ---
# Used by Docker Compose to initialize the PostgreSQL container vault
DB_PASSWORD=your_secure_password_here

# Used by FastAPI/SQLAlchemy to connect to the database
DATABASE_URL=postgresql://postgres:your_secure_password_here@db:5432/flash_sale_db

# --- JWT Security ---
SECRET_KEY=generate_a_secure_random_string_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 3. Spin Up the Infrastructure
Build and launch the API and PostgreSQL database containers in the background:
```bash
docker compose build --no-cache
docker compose up -d
```
*The API will now be live at `http://localhost:8000`*

---

## 🌱 Seeding the Database

To interact with the API, you need initial data. Run the seed script to automatically generate an Admin account, 5 standard users, and 50 random ticketing events.

1. Open a terminal *inside* your running web container:
```bash
docker compose exec web bash
```
2. Execute the seed script:
```bash
python seed.py
```
*(You can safely run this multiple times; it includes an idempotency guard to prevent duplicate data).*

---

## 🧪 Validating Concurrency (Stress Test)

This API includes a custom multi-threaded load-testing script to mathematically prove the integrity of the database locks under extreme traffic. 

1. Log in via the `/login` endpoint to receive a valid JWT.
2. Add the token to your `.env` file: `TEST_ACCESS_TOKEN=your_real_token`
3. Run the stress test locally:
```bash
python stress_test.py
```
**Result:** The script fires 50 concurrent purchase requests at a single event. You will watch the API successfully process exact inventory reductions and safely reject the rest with "Sold Out" errors, with zero database race conditions.

---

## 📡 Core API Endpoints

Once running, visit `http://localhost:8000/docs` to interact with the auto-generated Swagger UI interface.

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/users/` | Register a new user account | No |
| `POST` | `/login` | Authenticate and receive JWT | No |
| `GET` | `/events/` | View paginated available events | No |
| `POST` | `/events/` | Create a new event (Admin only) | Yes |
| `POST` | `/orders/` | Attempt to purchase a ticket | Yes |
| `GET` | `/orders/` | View your purchase history | Yes |
