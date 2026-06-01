# Marketplace API Specification

## Overview

A microservices-based marketplace backend with two independent services: Auth and Marketplace. Users can register, authenticate, browse products, and place orders.

## User Stories

### Auth Service

**US-1: User Registration**
As a new user, I want to create an account with email and password so that I can access the marketplace.
- Acceptance: Email must be unique, password min 8 chars, returns user object (no password)
- Error: 409 if email already exists, 422 if validation fails

**US-2: User Login**
As a registered user, I want to log in with my credentials so that I can get access tokens.
- Acceptance: Returns access_token (15min) + refresh_token (7 days)
- Error: 401 if credentials invalid

**US-3: Token Refresh**
As a logged-in user, I want to refresh my expired access token without logging in again.
- Acceptance: Returns new access_token, old refresh_token invalidated
- Error: 401 if refresh token expired or revoked

**US-4: Get Current User**
As an authenticated user, I want to see my profile information.
- Acceptance: Returns user object from valid JWT
- Error: 401 if token invalid/expired

**US-5: Logout**
As a logged-in user, I want to revoke my refresh token.
- Acceptance: Refresh token invalidated, returns success
- Error: 401 if token invalid

### Marketplace Service

**US-6: List Products**
As any user, I want to browse available products.
- Acceptance: Paginated list of products (20 per page), supports search by name
- No auth required

**US-7: Get Product Details**
As any user, I want to see details of a specific product.
- Acceptance: Returns product with id, name, description, price, stock, seller_id
- Error: 404 if product not found

**US-8: Create Product**
As an authenticated user, I want to list a product for sale.
- Acceptance: Creates product with name, description, price, stock. Seller set from JWT.
- Error: 401 if not authenticated, 422 if validation fails

**US-9: Update Product**
As the product owner, I want to update my product listing.
- Acceptance: Only the seller who created the product can update it
- Error: 403 if not owner, 404 if product not found

**US-10: Delete Product**
As the product owner, I want to remove my product listing.
- Acceptance: Soft delete (set is_active=false), only owner can delete
- Error: 403 if not owner, 404 if product not found

**US-11: Place Order**
As an authenticated user, I want to purchase a product.
- Acceptance: Creates order with product_id, quantity, total_price. Decrements stock.
- Error: 401 if not authenticated, 400 if insufficient stock, 404 if product not found

**US-12: List My Orders**
As an authenticated user, I want to see my order history.
- Acceptance: Returns paginated list of user's orders with product details
- Error: 401 if not authenticated

**US-13: Get Order Details**
As an authenticated user, I want to see details of a specific order.
- Acceptance: Returns order details, only if user owns the order
- Error: 403 if not order owner, 404 if order not found

## API Endpoints

### Auth Service (port 8001)

```
POST   /api/v1/auth/register     - Register new user
POST   /api/v1/auth/login        - Login, get tokens
POST   /api/v1/auth/refresh      - Refresh access token
POST   /api/v1/auth/logout       - Revoke refresh token
GET    /api/v1/auth/me           - Get current user (requires JWT)
GET    /health                   - Health check
```

### Marketplace Service (port 8002)

```
GET    /api/v1/products              - List products (public)
GET    /api/v1/products/{id}         - Get product (public)
POST   /api/v1/products              - Create product (auth required)
PUT    /api/v1/products/{id}         - Update product (owner only)
DELETE /api/v1/products/{id}         - Delete product (owner only)
POST   /api/v1/orders                - Place order (auth required)
GET    /api/v1/orders                - List my orders (auth required)
GET    /api/v1/orders/{id}           - Get order details (owner only)
GET    /health                       - Health check
```

## Data Models

### Auth Service

**users**
- id: UUID (PK)
- email: String (unique, indexed)
- password_hash: String
- created_at: DateTime
- updated_at: DateTime

**refresh_tokens**
- id: UUID (PK)
- user_id: UUID (FK → users)
- token_hash: String (indexed)
- expires_at: DateTime
- revoked: Boolean (default false)
- created_at: DateTime

### Marketplace Service

**products**
- id: UUID (PK)
- name: String (indexed)
- description: Text
- price: Decimal(10,2)
- stock: Integer
- seller_id: UUID (not FK — references Auth service)
- is_active: Boolean (default true)
- created_at: DateTime
- updated_at: DateTime

**orders**
- id: UUID (PK)
- buyer_id: UUID (not FK — references Auth service)
- product_id: UUID (FK → products)
- quantity: Integer
- total_price: Decimal(10,2)
- status: Enum (pending, confirmed, cancelled)
- created_at: DateTime

## Constraints

- No shared databases between services
- Auth service is the source of truth for users
- Marketplace service validates tokens by calling Auth service /me
- All UUIDs are v4
- All timestamps are UTC
- Prices stored as Decimal, never float

## Non-Goals (v1)

- Payment processing
- Image uploads
- Real-time notifications
- Admin dashboard
- Rate limiting (add in v2)
