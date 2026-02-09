# Order Management System

An order management system prototype that manages financial instrument orders and executes trades via REST API.

## Features

- Add and remove orders from the order book
- Calculate best price for buying/selling a given amount
- Execute trades with automatic order consumption
- Pre-sorted order books for optimal price calculation performance

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start the API server
uvicorn src.api.routes:app --reload --port 8080
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /orders` | Add order | `{order_id, symbol, side, amount, price}` |
| `DELETE /orders/{orderId}` | Remove order | - |
| `GET /price` | Calculate price | `?symbol=JPM&side=BUY&amount=20` |
| `POST /trades` | Execute trade | `{symbol, side, amount}` |
| `GET /health` | Health check | - |

## Core Interface

```python
class OrderManagement:
    def add_order(order_id: int, symbol: str, side: Side, amount: int, price: int) -> None
    def remove_order(order_id: int) -> None
    def calculate_price(symbol: str, side: Side, amount: int) -> int
    def place_trade(symbol: str, side: Side, amount: int) -> Trade
```

## Price Calculation Logic

**Buy orders**: Aggregates from lowest price first (ascending)
**Sell orders**: Aggregates from highest price first (descending)

Example with orders:
- Order 1: Buy 20 shares @ $20
- Order 4: Buy 10 shares @ $21

```
calculatePrice("JPM", BUY, 20) = $20 × 20 = $400
calculatePrice("JPM", BUY, 10) = $20 × 10 = $200
calculatePrice("JPM", BUY, 22) = $20 × 20 + $21 × 2 = $442
```

## Performance Design

- **Pre-sorted order books**: Uses `SortedList` for O(log n) insertion while maintaining sorted order
- **O(1) order lookup**: Hash map index by order_id for fast removal
- **Optimized for price calculation**: Most common operation runs in O(k) where k = orders consumed

## Project Structure

```
├── src/
│   ├── domain/
│   │   ├── models.py        # Order, Trade, Side, OrderFill
│   │   └── order_book.py    # OrderBook with SortedList
│   ├── services/
│   │   ├── order_manager.py # Main facade
│   │   ├── price_calculator.py
│   │   └── trade_executor.py
│   └── api/
│       └── routes.py        # FastAPI REST endpoints
├── tests/
│   ├── test_api.py          # API integration tests
│   └── test_properties.py   # Property-based tests + edge cases
└── pyproject.toml
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Property-based tests only
pytest tests/test_properties.py -v
```

## Example Usage

```python
from src.services.order_manager import OrderManagement
from src.domain.models import Side

om = OrderManagement()

# Add orders
om.add_order(1, "JPM", Side.BUY, 20, 20)
om.add_order(4, "JPM", Side.BUY, 10, 21)

# Calculate price
price = om.calculate_price("JPM", Side.BUY, 22)  # Returns 442

# Execute trade
trade = om.place_trade("JPM", Side.BUY, 22)
print(f"Filled: {trade.amount} shares for ${trade.total_price}")
```