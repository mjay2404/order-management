"""
API integration tests for the Order Management System.

Tests all REST API endpoints with valid inputs and error responses.
Uses FastAPI TestClient with mocked dependencies.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import (
    add_order,
    remove_order,
    calculate_price,
    place_trade,
    health_check,
    get_order_management,
    OrderResponse,
    PriceResponse,
    TradeResponse,
    HealthResponse,
)
from src.domain.models import Side
from src.services.order_manager import OrderManagement


# Create a test app without the lifespan handler
api_test_app = FastAPI()

# Register the routes manually
api_test_app.post("/orders", response_model=OrderResponse, status_code=201)(add_order)
api_test_app.delete("/orders/{order_id}", status_code=204)(remove_order)
api_test_app.get("/price", response_model=PriceResponse)(calculate_price)
api_test_app.post("/trades", response_model=TradeResponse, status_code=201)(place_trade)
api_test_app.get("/health", response_model=HealthResponse)(health_check)


@pytest.fixture
def order_management():
    """Create an OrderManagement instance for testing."""
    return OrderManagement()


@pytest.fixture
def client(order_management):
    """Create a test client with mocked OrderManagement dependency."""
    api_test_app.dependency_overrides[get_order_management] = lambda: order_management
    with TestClient(api_test_app) as test_client:
        yield test_client
    api_test_app.dependency_overrides.clear()


class TestAddOrderEndpoint:
    """Tests for POST /orders endpoint."""

    def test_add_order_success(self, client):
        """Test adding a valid order returns 201 Created."""
        order_data = {
            "order_id": 1,
            "symbol": "JPM",
            "side": "BUY",
            "amount": 100,
            "price": 2000
        }
        
        response = client.post("/orders", json=order_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["order_id"] == 1
        assert data["symbol"] == "JPM"
        assert data["side"] == "BUY"
        assert data["amount"] == 100
        assert data["price"] == 2000

    def test_add_order_sell_side(self, client):
        """Test adding a SELL order."""
        order_data = {
            "order_id": 2,
            "symbol": "GOOG",
            "side": "SELL",
            "amount": 50,
            "price": 15000
        }
        
        response = client.post("/orders", json=order_data)
        
        assert response.status_code == 201
        assert response.json()["side"] == "SELL"

    def test_add_order_invalid_side_raises_error(self, client):
        """Test adding order with invalid side raises ValueError."""
        order_data = {
            "order_id": 1,
            "symbol": "JPM",
            "side": "INVALID",
            "amount": 100,
            "price": 2000
        }
        
        with pytest.raises(ValueError, match="'INVALID' is not a valid Side"):
            client.post("/orders", json=order_data)

    def test_add_order_negative_amount_returns_422(self, client):
        """Test adding order with negative amount returns 422."""
        order_data = {
            "order_id": 1,
            "symbol": "JPM",
            "side": "BUY",
            "amount": -10,
            "price": 2000
        }
        
        response = client.post("/orders", json=order_data)
        assert response.status_code == 422

    def test_add_order_zero_price_returns_422(self, client):
        """Test adding order with zero price returns 422."""
        order_data = {
            "order_id": 1,
            "symbol": "JPM",
            "side": "BUY",
            "amount": 100,
            "price": 0
        }
        
        response = client.post("/orders", json=order_data)
        assert response.status_code == 422

    def test_add_order_missing_field_returns_422(self, client):
        """Test adding order with missing field returns 422."""
        order_data = {
            "order_id": 1,
            "symbol": "JPM",
            "side": "BUY",
            "amount": 100
            # missing price
        }
        
        response = client.post("/orders", json=order_data)
        assert response.status_code == 422


class TestRemoveOrderEndpoint:
    """Tests for DELETE /orders/{orderId} endpoint."""

    def test_remove_order_success(self, client, order_management):
        """Test removing an existing order returns 204 No Content."""
        order_management.add_order(1, "JPM", Side.BUY, 100, 2000)
        
        response = client.delete("/orders/1")
        assert response.status_code == 204

    def test_remove_order_not_found_returns_204(self, client):
        """Test removing non-existent order returns 204 (idempotent)."""
        response = client.delete("/orders/999")
        # In the simplified version, remove_order doesn't return 404
        assert response.status_code == 204


class TestCalculatePriceEndpoint:
    """Tests for GET /price endpoint."""

    def test_calculate_price_success(self, client, order_management):
        """Test calculating price with valid inputs."""
        order_management.add_order(1, "JPM", Side.BUY, 20, 20)
        order_management.add_order(2, "JPM", Side.BUY, 10, 21)
        
        response = client.get("/price", params={
            "symbol": "JPM",
            "side": "BUY",
            "amount": 20
        })
        
        assert response.status_code == 200
        assert response.json()["price"] == 400  # 20 * 20

    def test_calculate_price_partial_order(self, client, order_management):
        """Test price calculation consuming partial order."""
        order_management.add_order(1, "JPM", Side.BUY, 20, 20)
        
        response = client.get("/price", params={
            "symbol": "JPM",
            "side": "BUY",
            "amount": 10
        })
        
        assert response.status_code == 200
        assert response.json()["price"] == 200  # 10 * 20

    def test_calculate_price_multiple_orders(self, client, order_management):
        """Test price calculation spanning multiple orders."""
        order_management.add_order(1, "JPM", Side.BUY, 20, 20)
        order_management.add_order(4, "JPM", Side.BUY, 10, 21)
        
        response = client.get("/price", params={
            "symbol": "JPM",
            "side": "BUY",
            "amount": 22
        })
        
        assert response.status_code == 200
        # 20 * 20 + 2 * 21 = 400 + 42 = 442
        assert response.json()["price"] == 442

    def test_calculate_price_sell_side(self, client, order_management):
        """Test price calculation for SELL side."""
        order_management.add_order(1, "GOOG", Side.SELL, 10, 100)
        
        response = client.get("/price", params={
            "symbol": "GOOG",
            "side": "SELL",
            "amount": 5
        })
        
        assert response.status_code == 200
        assert response.json()["price"] == 500  # 5 * 100

    def test_calculate_price_invalid_side_returns_400(self, client):
        """Test price calculation with invalid side returns 400."""
        response = client.get("/price", params={
            "symbol": "JPM",
            "side": "INVALID",
            "amount": 10
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "Invalid side"

    def test_calculate_price_no_orders_returns_zero(self, client):
        """Test price calculation with no orders returns zero."""
        response = client.get("/price", params={
            "symbol": "UNKNOWN",
            "side": "BUY",
            "amount": 10
        })
        
        assert response.status_code == 200
        assert response.json()["price"] == 0


class TestPlaceTradeEndpoint:
    """Tests for POST /trades endpoint."""

    def test_place_trade_success(self, client, order_management):
        """Test placing a valid trade returns 201 Created."""
        order_management.add_order(1, "JPM", Side.BUY, 20, 20)
        
        trade_data = {
            "symbol": "JPM",
            "side": "BUY",
            "amount": 10
        }
        
        response = client.post("/trades", json=trade_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "JPM"
        assert data["side"] == "BUY"
        assert data["amount"] == 10
        assert data["total_price"] == 200  # 10 * 20
        assert "trade_id" in data
        assert "executed_at" in data
        assert len(data["order_fills"]) == 1
        assert data["order_fills"][0]["order_id"] == 1
        assert data["order_fills"][0]["filled_amount"] == 10
        assert data["order_fills"][0]["fill_price"] == 20

    def test_place_trade_consumes_multiple_orders(self, client, order_management):
        """Test trade consuming multiple orders."""
        order_management.add_order(1, "JPM", Side.BUY, 20, 20)
        order_management.add_order(4, "JPM", Side.BUY, 10, 21)
        
        trade_data = {
            "symbol": "JPM",
            "side": "BUY",
            "amount": 22
        }
        
        response = client.post("/trades", json=trade_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == 22
        assert data["total_price"] == 442  # 20*20 + 2*21
        assert len(data["order_fills"]) == 2

    def test_place_trade_invalid_side_returns_400(self, client):
        """Test placing trade with invalid side returns 400."""
        trade_data = {
            "symbol": "JPM",
            "side": "INVALID",
            "amount": 10
        }
        
        response = client.post("/trades", json=trade_data)
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "Invalid side"

    def test_place_trade_negative_amount_returns_422(self, client):
        """Test placing trade with negative amount returns 422."""
        trade_data = {
            "symbol": "JPM",
            "side": "BUY",
            "amount": -10
        }
        
        response = client.post("/trades", json=trade_data)
        assert response.status_code == 422

    def test_place_trade_missing_field_returns_422(self, client):
        """Test placing trade with missing field returns 422."""
        trade_data = {
            "symbol": "JPM",
            "side": "BUY"
            # missing amount
        }
        
        response = client.post("/trades", json=trade_data)
        assert response.status_code == 422


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_check_success(self, client):
        """Test health check returns 200 with healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"