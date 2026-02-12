"""
FastAPI REST API for the Order Management System.
This module provides the REST API layer for the OMS, exposing endpoints
for order management, price calculation, and trade execution.
"""

from contextlib import asynccontextmanager
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.domain.models import Side
from src.services.order_manager import OrderManagement


# Global OrderManagement instance
_order_management: Optional[OrderManagement] = None


def get_order_management() -> OrderManagement:
    """
    Dependency injection for OrderManagement.
    Returns the singleton OrderManagement instance, creating it if necessary.
    """
    global _order_management
    if _order_management is None:
        raise RuntimeError("OrderManagement not initialized. Application not started properly.")
    return _order_management


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    global _order_management
    
    # Startup: Initialize OrderManagement
    _order_management = OrderManagement()
    
    yield
    
    # Shutdown: Clean up resources
    _order_management = None


# Create FastAPI application
app = FastAPI(
    title="Order Management System",
    description="Order Management System for financial instruments",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS middleware - restricted to localhost for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# Type alias for dependency injection
OrderManagementDep = Annotated[OrderManagement, Depends(get_order_management)]


class OrderRequest(BaseModel):
    """Request model for creating an order."""
    order_id: int = Field(..., description="Unique order identifier")
    symbol: str = Field(
        ...,
        description="Financial instrument symbol",
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z]+$"
    )
    side: str = Field(..., description="Order side: BUY or SELL")
    amount: int = Field(..., gt=0, le=10_000_000, description="Number of shares")
    price: int = Field(..., gt=0, le=10_000_000, description="Price per share in cents")


class OrderResponse(BaseModel):
    """Response model for order operations."""
    order_id: int
    symbol: str
    side: str
    amount: int
    price: int


class PriceResponse(BaseModel):
    """Response model for price calculation."""
    price: int = Field(..., description="Calculated total price in cents")


class TradeRequest(BaseModel):
    """Request model for executing a trade."""
    symbol: str = Field(
        ...,
        description="Financial instrument symbol",
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z]+$"
    )
    side: str = Field(..., description="Trade side: BUY or SELL")
    amount: int = Field(..., gt=0, le=10_000_000, description="Number of shares to trade")


class OrderFillResponse(BaseModel):
    """Response model for order fill details within a trade."""
    order_id: int
    filled_amount: int
    fill_price: int


class TradeResponse(BaseModel):
    """Response model for trade execution."""
    trade_id: str = Field(..., description="Unique trade identifier")
    symbol: str = Field(..., description="Financial instrument symbol")
    side: str = Field(..., description="Trade side: BUY or SELL")
    amount: int = Field(..., description="Number of shares traded")
    total_price: int = Field(..., description="Total price in cents")
    executed_at: str = Field(..., description="ISO timestamp of execution")
    order_fills: list[OrderFillResponse] = Field(..., description="Details of orders consumed")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Health status")


class OrderBookOrder(BaseModel):
    """Order details in the order book."""
    order_id: int
    price: int
    amount: int


class OrderBookResponse(BaseModel):
    """Response model for order book view."""
    symbol: str
    buy_orders: list[OrderBookOrder]
    sell_orders: list[OrderBookOrder]


@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new order",
)
def add_order(
    order_request: OrderRequest,
    order_management: OrderManagementDep,
) -> OrderResponse:
    """Add a new order to the order book for the specified symbol."""
    order_management.add_order(
        order_id=order_request.order_id,
        symbol=order_request.symbol,
        side=Side(order_request.side),
        amount=order_request.amount,
        price=order_request.price,
    )
    
    return OrderResponse(
        order_id=order_request.order_id,
        symbol=order_request.symbol,
        side=order_request.side,
        amount=order_request.amount,
        price=order_request.price,
    )


@app.delete(
    "/orders/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an order",
)
def remove_order(
    order_id: int,
    order_management: OrderManagementDep,
) -> Response:
    """Remove an order from the order book by its ID."""
    order_management.remove_order(order_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/price",
    response_model=PriceResponse,
    summary="Calculate best price",
)
def calculate_price(
    symbol: str,
    side: str,
    amount: int,
    order_management: OrderManagementDep,
) -> PriceResponse:
    """Calculate the best price for buying or selling a given amount."""
    try:
        side_enum = Side(side)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid side", "valid_values": ["BUY", "SELL"]},
        )
    
    price = order_management.calculate_price(symbol, side_enum, amount)
    return PriceResponse(price=price)


@app.post(
    "/trades",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a trade",
)
def place_trade(
    trade_request: TradeRequest,
    order_management: OrderManagementDep,
) -> TradeResponse:
    """Execute a trade for the specified symbol, side, and amount."""
    try:
        side_enum = Side(trade_request.side)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid side", "valid_values": ["BUY", "SELL"]},
        )
    
    trade = order_management.place_trade(
        symbol=trade_request.symbol,
        side=side_enum,
        amount=trade_request.amount,
    )
    
    return TradeResponse(
        trade_id=trade.trade_id,
        symbol=trade.symbol,
        side=trade.side.value,
        amount=trade.amount,
        total_price=trade.total_price,
        executed_at=trade.executed_at.isoformat(),
        order_fills=[
            OrderFillResponse(
                order_id=fill.order_id,
                filled_amount=fill.filled_amount,
                fill_price=fill.fill_price,
            )
            for fill in trade.order_fills
        ],
    )


@app.get(
    "/orderbook/{symbol}",
    response_model=OrderBookResponse,
    summary="View order book",
)
def get_order_book(
    symbol: str,
    order_management: OrderManagementDep,
) -> OrderBookResponse:
    """View all orders in the order book for a symbol."""
    # Access the internal order book
    order_book = order_management._order_books.get(symbol)
    
    if order_book is None:
        return OrderBookResponse(
            symbol=symbol,
            buy_orders=[],
            sell_orders=[],
        )
    
    buy_orders = [
        OrderBookOrder(order_id=o.order_id, price=o.price, amount=o.amount)
        for o in order_book.get_orders(Side.BUY)
    ]
    
    sell_orders = [
        OrderBookOrder(order_id=o.order_id, price=o.price, amount=o.amount)
        for o in order_book.get_orders(Side.SELL)
    ]
    
    return OrderBookResponse(
        symbol=symbol,
        buy_orders=buy_orders,
        sell_orders=sell_orders,
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
def health_check() -> HealthResponse:
    """Check the health status of the service."""
    return HealthResponse(status="healthy")


def main():
    """Entry point for running the application with uvicorn."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)


if __name__ == "__main__":
    main()