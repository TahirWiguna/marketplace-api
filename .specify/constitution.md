# Marketplace API Constitution

## Core Principles

### I. Service Independence
Each microservice owns its data, schema, and database. No shared databases. Services communicate via REST APIs only. Each service must be deployable, scalable, and restartable independently.

### II. API-First Design
Every endpoint is defined in OpenAPI spec before implementation. All APIs return consistent JSON responses with standard error formats. Version all APIs from day one (prefix: /api/v1/).

### III. Test-First Development
TDD mandatory: write failing test → implement → verify pass. Unit tests for business logic, integration tests for API endpoints, contract tests for inter-service communication. Minimum 80% coverage target.

### IV. Docker-First Deployment
Every service runs in its own container. Docker Compose for local development. No local dependencies required beyond Docker. Health checks on all services.

### V. Security by Default
JWT tokens for authentication. Passwords hashed with bcrypt. Input validation on all endpoints. No secrets in code — use environment variables. CORS configured explicitly.

### VI. Observability
Structured JSON logging on all services. Request ID propagation across services. Error tracking with stack traces. Health check endpoints (/health) on every service.

## Tech Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Database:** PostgreSQL 15+ (one per service)
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **Auth:** JWT (PyJWT) + bcrypt
- **Containerization:** Docker + Docker Compose
- **Testing:** pytest + httpx (async test client)

## Service Boundaries

### Auth Service
- Owns: users table, refresh_tokens table
- Endpoints: register, login, refresh, logout, /me
- Port: 8001

### Marketplace Service
- Owns: products table, orders table
- Endpoints: products CRUD, orders CRUD
- Port: 8002
- Validates tokens by calling Auth Service's /me endpoint

## Development Workflow

1. Write OpenAPI spec for new endpoint
2. Write failing tests
3. Implement endpoint
4. Verify tests pass
5. Run full test suite
6. Commit with conventional message (feat:, fix:, etc.)

## Governance

This constitution supersedes all other practices. Any deviation must be documented and approved. Complexity must be justified.

**Version**: 1.0.0 | **Ratified**: 2026-06-01 | **Last Amended**: 2026-06-01
