# Marketplace API — Implementation Plan

## Phase 1: Project Foundation (Tasks 1-3)

### Task 1: Project scaffold + Docker setup
- Create project directory structure:
  ```
  marketplace-api/
  ├── auth-service/
  │   ├── app/
  │   │   ├── __init__.py
  │   │   ├── main.py
  │   │   ├── config.py
  │   │   ├── database.py
  │   │   ├── models/
  │   │   ├── schemas/
  │   │   ├── routes/
  │   │   └── utils/
  │   ├── tests/
  │   ├── alembic/
  │   ├── Dockerfile
  │   └── requirements.txt
  ├── marketplace-service/
  │   ├── app/
  │   │   ├── __init__.py
  │   │   ├── main.py
  │   │   ├── config.py
  │   │   ├── database.py
  │   │   ├── models/
  │   │   ├── schemas/
  │   │   ├── routes/
  │   │   └── utils/
  │   ├── tests/
  │   ├── alembic/
  │   ├── Dockerfile
  │   └── requirements.txt
  ├── docker-compose.yml
  └── .env.example
  ```
- Docker Compose with 4 services: auth-db, marketplace-db, auth-service, marketplace-service
- PostgreSQL 15 images for databases
- Health checks on all services
- Volume mounts for development
- .env.example with all required env vars

### Task 2: Auth service — database + models
- SQLAlchemy 2.0 async engine setup
- User model (id, email, password_hash, created_at, updated_at)
- RefreshToken model (id, user_id, token_hash, expires_at, revoked, created_at)
- Alembic init + initial migration
- Database connection utility

### Task 3: Marketplace service — database + models
- SQLAlchemy 2.0 async engine setup
- Product model (id, name, description, price, stock, seller_id, is_active, created_at, updated_at)
- Order model (id, buyer_id, product_id, quantity, total_price, status, created_at)
- Alembic init + initial migration
- Database connection utility

## Phase 2: Auth Service (Tasks 4-7)

### Task 4: Auth — registration endpoint
- POST /api/v1/auth/register
- Pydantic schemas: UserCreate, UserResponse
- Email validation, password min 8 chars
- bcrypt password hashing
- Duplicate email check (409)
- Tests: successful registration, duplicate email, invalid input

### Task 5: Auth — login + token endpoints
- POST /api/v1/auth/login — returns access_token + refresh_token
- POST /api/v1/auth/refresh — validates refresh token, returns new access_token
- POST /api/v1/auth/logout — revokes refresh token
- JWT utility (create_access_token, create_refresh_token, verify_token)
- Access token: 15 min expiry, contains user_id + email
- Refresh token: 7 day expiry, stored hashed in DB
- Tests: valid login, invalid credentials, token refresh, logout

### Task 6: Auth — /me endpoint + middleware
- GET /api/v1/auth/me — returns current user from JWT
- JWT middleware/dependency for FastAPI
- Proper 401 responses for invalid/expired tokens
- Tests: valid token, expired token, invalid token

### Task 7: Auth — health check + Dockerfile
- GET /health — returns {"status": "healthy", "service": "auth"}
- Dockerfile (python:3.11-slim, pip install, uvicorn)
- Verify service starts in Docker
- Tests: health endpoint returns 200

## Phase 3: Marketplace Service (Tasks 8-12)

### Task 8: Marketplace — products CRUD
- POST /api/v1/products — create product (auth required)
- GET /api/v1/products — list products (public, paginated, searchable)
- GET /api/v1/products/{id} — get product details (public)
- PUT /api/v1/products/{id} — update product (owner only)
- DELETE /api/v1/products/{id} — soft delete (owner only)
- Pydantic schemas: ProductCreate, ProductUpdate, ProductResponse
- Auth middleware that calls Auth service /me to validate tokens
- Tests: CRUD operations, pagination, search, owner-only updates

### Task 9: Marketplace — orders
- POST /api/v1/orders — place order (auth required)
- GET /api/v1/orders — list my orders (auth required, paginated)
- GET /api/v1/orders/{id} — get order details (owner only)
- Stock validation (reject if insufficient)
- Stock decrement on order creation
- Pydantic schemas: OrderCreate, OrderResponse
- Tests: place order, insufficient stock, list orders, owner-only access

### Task 10: Marketplace — health check + Dockerfile
- GET /health — returns {"status": "healthy", "service": "marketplace"}
- Dockerfile (python:3.11-slim, pip install, uvicorn)
- Verify service starts in Docker
- Tests: health endpoint returns 200

## Phase 4: Integration (Tasks 11-12)

### Task 11: Inter-service communication
- Auth client utility in marketplace-service (calls auth-service /me)
- Proper error handling for auth-service being down
- Timeout configuration (5s default)
- Tests: mock auth-service responses, timeout handling

### Task 12: Docker Compose integration testing
- Verify all 4 services start together
- Test full flow: register → login → create product → place order
- Verify service discovery (docker networking)
- Test database isolation (each service only sees its own DB)

## Task Dependencies

```
Task 1 (scaffold)
├── Task 2 (auth DB) ──→ Task 4 (register) ──→ Task 5 (login) ──→ Task 6 (me)
├── Task 3 (market DB) ──→ Task 8 (products) ──→ Task 9 (orders)
├── Task 7 (auth health/docker)
├── Task 10 (market health/docker)
├── Task 11 (inter-service) [depends on Task 6]
└── Task 12 (integration test) [depends on all above]
```

## Estimated Effort

- Phase 1: ~30 min (foundation)
- Phase 2: ~45 min (auth service)
- Phase 3: ~60 min (marketplace service)
- Phase 4: ~30 min (integration)
- **Total: ~2.5-3 hours with Claude Code**
