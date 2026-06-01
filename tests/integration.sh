#!/usr/bin/env bash
#
# Integration test script for Marketplace API (Docker Compose)
# Tests the full auth + marketplace flow including error cases.
#
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
BASE_URL_AUTH="http://localhost:8001"
BASE_URL_MARKETPLACE="http://localhost:8002"
HEALTH_TIMEOUT=60
TEST_EMAIL="testuser_$(date +%s)@example.com"
TEST_PASSWORD="testpass123"

# ─── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── Counters ────────────────────────────────────────────────────────────────
PASS=0
FAIL=0

# ─── Helpers ─────────────────────────────────────────────────────────────────

pass_test() {
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC}  $1"
}

fail_test() {
    FAIL=$((FAIL + 1))
    echo -e "  ${RED}FAIL${NC}  $1"
    if [ -n "${2:-}" ]; then
        echo -e "         ${RED}Expected: $2${NC}"
    fi
    if [ -n "${3:-}" ]; then
        echo -e "         ${RED}Got:      $3${NC}"
    fi
}

check_status() {
    local description="$1"
    local expected="$2"
    local actual="$3"
    local body="${4:-}"

    if [ "$actual" = "$expected" ]; then
        pass_test "$description"
        return 0
    else
        fail_test "$description" "$expected" "$actual"
        if [ -n "$body" ]; then
            echo -e "         Body: $body"
        fi
        return 1
    fi
}

# ─── Wait for Services ───────────────────────────────────────────────────────
echo -e "\n${CYAN}=== Waiting for services to be healthy ===${NC}"

wait_for_service() {
    local name="$1"
    local url="$2"
    local elapsed=0

    echo -n "  Waiting for $name"
    while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}ready${NC} (${elapsed}s)"
            return 0
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done
    echo -e " ${RED}timeout after ${HEALTH_TIMEOUT}s${NC}"
    echo -e "${RED}ABORT: $name is not responding at $url${NC}"
    exit 1
}

wait_for_service "auth-service" "${BASE_URL_AUTH}/health"
wait_for_service "marketplace-service" "${BASE_URL_MARKETPLACE}/health"

# ─── Test Suite ──────────────────────────────────────────────────────────────

echo -e "\n${CYAN}=== Happy Path Tests ===${NC}"

# 1. Register user
echo -e "\n${YELLOW}--- Register ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL_AUTH}/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "Register new user (POST /api/v1/auth/register)" "201" "$HTTP_CODE" "$BODY"

# 2. Login
echo -e "\n${YELLOW}--- Login ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL_AUTH}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "Login user (POST /api/v1/auth/login)" "200" "$HTTP_CODE" "$BODY"

ACCESS_TOKEN=$(echo "$BODY" | jq -r '.access_token // empty')
REFRESH_TOKEN=$(echo "$BODY" | jq -r '.refresh_token // empty')

if [ -z "$ACCESS_TOKEN" ]; then
    fail_test "Extract access_token from login response" "non-empty" "empty"
    echo -e "${RED}ABORT: Cannot continue without access token${NC}"
    exit 1
else
    pass_test "Extract access_token from login response"
fi

# 3. Create product
echo -e "\n${YELLOW}--- Create Product ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL_MARKETPLACE}/api/v1/products/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -d '{"name":"Test Widget","description":"A fine test widget","price":29.99,"stock":100}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "Create product (POST /api/v1/products)" "201" "$HTTP_CODE" "$BODY"

PRODUCT_ID=$(echo "$BODY" | jq -r '.id // empty')

if [ -z "$PRODUCT_ID" ]; then
    fail_test "Extract product_id from create response" "non-empty" "empty"
else
    pass_test "Extract product_id from create response ($PRODUCT_ID)"
fi

# 4. List products
echo -e "\n${YELLOW}--- List Products ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL_MARKETPLACE}/api/v1/products/")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "List products (GET /api/v1/products)" "200" "$HTTP_CODE" "$BODY"

PRODUCTS_TOTAL=$(echo "$BODY" | jq -r '.total // 0')
if [ "$PRODUCTS_TOTAL" -ge 1 ] 2>/dev/null; then
    pass_test "Products list contains at least 1 item (total=$PRODUCTS_TOTAL)"
else
    fail_test "Products list contains at least 1 item" ">=1" "$PRODUCTS_TOTAL"
fi

# 5. Place order
echo -e "\n${YELLOW}--- Place Order ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL_MARKETPLACE}/api/v1/orders/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -d "{\"product_id\":\"${PRODUCT_ID}\",\"quantity\":2}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "Place order (POST /api/v1/orders)" "201" "$HTTP_CODE" "$BODY"

ORDER_ID=$(echo "$BODY" | jq -r '.id // empty')
if [ -z "$ORDER_ID" ]; then
    fail_test "Extract order_id from create response" "non-empty" "empty"
else
    pass_test "Extract order_id from create response ($ORDER_ID)"
fi

# 6. List orders
echo -e "\n${YELLOW}--- List Orders ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL_MARKETPLACE}/api/v1/orders/" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "List orders (GET /api/v1/orders)" "200" "$HTTP_CODE" "$BODY"

ORDERS_TOTAL=$(echo "$BODY" | jq -r '.total // 0')
if [ "$ORDERS_TOTAL" -ge 1 ] 2>/dev/null; then
    pass_test "Orders list contains at least 1 item (total=$ORDERS_TOTAL)"
else
    fail_test "Orders list contains at least 1 item" ">=1" "$ORDERS_TOTAL"
fi

# ─── Error Case Tests ────────────────────────────────────────────────────────

echo -e "\n${CYAN}=== Error Case Tests ===${NC}"

# 7. Duplicate registration
echo -e "\n${YELLOW}--- Duplicate Registration ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL_AUTH}/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "Duplicate registration should return 409" "409" "$HTTP_CODE" "$BODY"

# 8. Wrong password login
echo -e "\n${YELLOW}--- Wrong Password Login ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL_AUTH}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"wrongpassword\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "Wrong password login should return 401" "401" "$HTTP_CODE" "$BODY"

# 9. Create product without auth
echo -e "\n${YELLOW}--- Create Product Without Auth ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL_MARKETPLACE}/api/v1/products/" \
    -H "Content-Type: application/json" \
    -d '{"name":"Unauthorized Product","description":"Should fail","price":9.99,"stock":1}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "Create product without auth should return 401 or 422" "422" "$HTTP_CODE" "$BODY"

# 10. Order with insufficient stock
echo -e "\n${YELLOW}--- Order With Insufficient Stock ---${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL_MARKETPLACE}/api/v1/orders/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -d "{\"product_id\":\"${PRODUCT_ID}\",\"quantity\":99999}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')
check_status "Order with insufficient stock should return 400" "400" "$HTTP_CODE" "$BODY"

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Integration Test Summary${NC}"
echo -e "${CYAN}========================================${NC}"
TOTAL=$((PASS + FAIL))
echo -e "  Total:  $TOTAL"
echo -e "  ${GREEN}Passed: $PASS${NC}"
if [ $FAIL -gt 0 ]; then
    echo -e "  ${RED}Failed: $FAIL${NC}"
else
    echo -e "  Failed: 0"
fi
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}RESULT: FAIL${NC}"
    exit 1
else
    echo -e "${GREEN}RESULT: PASS${NC}"
    exit 0
fi
