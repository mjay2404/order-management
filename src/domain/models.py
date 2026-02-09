"""Data models for the Order Management System."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List


class Side(Enum):
    """Order side indicating buy or sell direction."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """
    Represents an order in the order management system.
    
    Attributes:
        order_id: Unique identifier for the order
        symbol: Financial instrument symbol (e.g., "JPM", "GOOG")
        side: Order direction (BUY or SELL)
        amount: Number of shares
        price: Price per share in cents
    """
    order_id: int
    symbol: str
    side: Side
    amount: int
    price: int
    
    def to_dict(self) -> dict:
        """Serialize the Order to a dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "amount": self.amount,
            "price": self.price
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        """Create an Order from a dictionary."""
        return cls(
            order_id=data["order_id"],
            symbol=data["symbol"],
            side=Side(data["side"]),
            amount=data["amount"],
            price=data["price"]
        )


@dataclass
class OrderFill:
    """
    Represents the fill details for a single order within a trade.
    
    Attributes:
        order_id: The ID of the order that was filled
        filled_amount: Number of shares filled from this order
        fill_price: Price per share at which the fill occurred
    """
    order_id: int
    filled_amount: int
    fill_price: int
    
    def to_dict(self) -> dict:
        """Serialize the OrderFill to a dictionary."""
        return {
            "order_id": self.order_id,
            "filled_amount": self.filled_amount,
            "fill_price": self.fill_price
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "OrderFill":
        """Create an OrderFill from a dictionary."""
        return cls(
            order_id=data["order_id"],
            filled_amount=data["filled_amount"],
            fill_price=data["fill_price"]
        )


@dataclass
class Trade:
    """
    Represents an executed trade in the order management system.
    
    Attributes:
        trade_id: Unique identifier for the trade (UUID string)
        symbol: Financial instrument symbol (e.g., "JPM", "GOOG")
        side: Trade direction (BUY or SELL)
        amount: Total number of shares traded
        total_price: Total price of the trade in cents
        executed_at: Timestamp when the trade was executed
        order_fills: List of OrderFill details showing which orders were consumed
    """
    trade_id: str
    symbol: str
    side: Side
    amount: int
    total_price: int
    executed_at: datetime
    order_fills: List[OrderFill]
    
    def to_dict(self) -> dict:
        """Serialize the Trade to a dictionary."""
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "amount": self.amount,
            "total_price": self.total_price,
            "executed_at": self.executed_at.isoformat(),
            "order_fills": [fill.to_dict() for fill in self.order_fills]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Trade":
        """Create a Trade from a dictionary."""
        return cls(
            trade_id=data["trade_id"],
            symbol=data["symbol"],
            side=Side(data["side"]),
            amount=data["amount"],
            total_price=data["total_price"],
            executed_at=datetime.fromisoformat(data["executed_at"]),
            order_fills=[OrderFill.from_dict(fill) for fill in data["order_fills"]]
        )