# Marketplace API

A microservices-based marketplace backend built with FastAPI. Users can register, authenticate, browse products, and place orders.

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │            Docker Compose Network           │
                    │                                             │
  Client Request    │  ┌──────────────┐    ┌──────────────────┐  │
  ──────────────────┼─►│ Auth Service │◄──►│   Auth DB        │  │
        :8001       │  │  (FastAPI)   │    │  (PostgreSQL)    │  │
                    │  └──────────────┘    └──────────────────┘  │
                    │                                             │
                    │  ┌──────────────┐    ┌──────────────────┐  │
        :8002       │  │  Marketplace │◄──►│ Marketplace DB   │  │
  ──────────────────┼─►│   Service    │    │  (PostgreSQL)    │  │
                    │  │  (FastAPI)   │    └──────────────────┘  │
                    │  └──────┬───────┘                           │
                    │         │ validates JWT via                  │
                    │         ▼ auth-service /me                   │
                    │  ┌──────────────┐                           │
                    │  │ Auth Service │                           │
                    │  │  /api/v1/    │                           │
                    │  │  auth/me     │                           │
                    │  └──────────────┘                           │
                    └─────────────────────────────────────────────┘
```

**Services:**

| Service | Port | Description |
|---------|------|-------------|
| auth-service | 8001 | User registration, login, JWT token management |
| marketplace-service | 8002 | Products CRUD, order placement |
| auth-db | 5432 | PostgreSQL database for auth-service |
| marketplace-db | 5433 | PostgreSQL database for marketplace-service |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd marketplace-api

# Copy environment variables
cp .env.example .env

# Start all services
docker compose up --build

# Services will be available at:
#   Auth Service:    http://localhost:8001
#   Marketplace:     http://localhost:8002
#   Auth DB:         localhost:5432
#   Marketplace DB:  localhost:5433
```

## Running Integration Tests

With the services running, execute:

```bash
./tests/integration.sh
```

The script tests the full happy path (register, login, create product, place order) and error cases (duplicate registration, wrong password, unauthorized access, insufficient stock). It prints PASS/FAIL for each test and exits with code 0 on success.

## API Endpoints

### Auth Service (port 8001)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/auth/register` | Register new user | No |
| POST | `/api/v1/auth/login` | Login, get access + refresh tokens | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | No |
| POST | `/api/v1/auth/logout` | Revoke refresh token | No |
| GET | `/api/v1/auth/me` | Get current user profile | Yes (JWT) |
| GET | `/health` | Health check | No |

### Marketplace Service (port 8002)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/products` | List products (paginated, searchable) | No |
| GET | `/api/v1/products/{id}` | Get product details | No |
| POST | `/api/v1/products` | Create a product | Yes (JWT) |
| PUT | `/api/v1/products/{id}` | Update product (owner only) | Yes (JWT) |
| DELETE | `/api/v1/products/{id}` | Soft-delete product (owner only) | Yes (JWT) |
| POST | `/api/v1/orders` | Place an order | Yes (JWT) |
| GET | `/api/v1/orders` | List my orders (paginated) | Yes (JWT) |
| GET | `/api/v1/orders/{id}` | Get order details (owner only) | Yes (JWT) |
| GET | `/health` | Health check | No |

### Request/Response Examples

**Register:**
```bash
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "mypassword123"}'
```

**Login:**
```bash
curl -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "mypassword123"}'
# Returns: {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

**Create Product:**
```bash
curl -X POST http://localhost:8002/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"name": "Widget", "description": "A fine widget", "price": 19.99, "stock": 50}'
```

**Place Order:**
```bash
curl -X POST http://localhost:8002/api/v1/orders/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"product_id": "<product-uuid>", "quantity": 2}'
```

## Tech Stack

- **Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL 15 (Alpine)
- **ORM:** SQLAlchemy (async) + Alembic migrations
- **Auth:** JWT (HS256) with access + refresh token pattern
- **Containerization:** Docker + Docker Compose
