
from typing import Dict

from src.domain.models import Order, Side, Trade
from src.domain.order_book import OrderBook
from src.services.price_calculator import PriceCalculator
from src.services.trade_executor import TradeExecutor


class OrderManagement:
    """
    Main facade coordinating all order operations.
    
    Manages order books for different symbols and delegates to specialized
    components for price calculation and trade execution. Maintains a mapping
    of symbols to their respective OrderBook instances.
    
    This implementation uses in-memory storage for prototype/demo purposes.
    For production, persistence storage to be used.
    
    Attributes:
        _order_books: Dictionary mapping symbols to OrderBook instances
        _orders: Dictionary mapping order_id to Order for O(1) lookup
    """
    
    def __init__(self):
        """Initialize the OrderManagement with empty state."""
        self._order_books: Dict[str, OrderBook] = {}
        self._orders: Dict[int, Order] = {}
        self._price_calculator = PriceCalculator()
        self._trade_executor = TradeExecutor()
    
    def _get_or_create_order_book(self, symbol: str) -> OrderBook:
        """
        Get an existing OrderBook for a symbol or create a new one.
        
        Args:
            symbol: The financial instrument symbol
            
        Returns:
            OrderBook instance for the symbol
        """
        if symbol not in self._order_books:
            self._order_books[symbol] = OrderBook(symbol)
        return self._order_books[symbol]
    
    def add_order(self, order_id: int, symbol: str, side: Side, amount: int, price: int) -> None:
        """
        Add an order to the appropriate order book.
        
        Creates an OrderBook for the symbol if one doesn't exist,
        adds the order to the book, and tracks it for O(1) lookup by order_id.
        
        Args:
            order_id: Unique identifier for the order
            symbol: Financial instrument symbol (e.g., "JPM")
            side: Order direction (BUY or SELL)
            amount: Number of shares
            price: Price per share
            
        Raises:
            ValueError: If an order with the same order_id already exists
        """
        # Check for duplicate order ID
        if order_id in self._orders:
            raise ValueError(f"Order with ID {order_id} already exists")
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            amount=amount,
            price=price
        )
        
        # Get or create order book for this symbol
        order_book = self._get_or_create_order_book(symbol)
        
        # Add order to the order book
        order_book.add_order(order)
        
        # Track order for O(1) lookup
        self._orders[order_id] = order
    
    def remove_order(self, order_id: int) -> None:
        """
        Remove an order from the system.
        
        Looks up the order by ID, removes it from the appropriate OrderBook,
        and removes it from the local tracking dict.
        
        Args:
            order_id: The ID of the order to remove
        """
        # Look up order by ID
        order = self._orders.get(order_id)
        if order is None:
            return
        
        # Get the order book for this symbol
        order_book = self._order_books.get(order.symbol)
        if order_book is not None:
            order_book.remove_order(order_id)
        
        # Remove from local tracking
        del self._orders[order_id]
    
    def calculate_price(self, symbol: str, side: Side, amount: int) -> int:
        """
        Calculate the best price for buying or selling a given amount.
        Gets orders from the OrderBook for the specified symbol and side,
        then delegates to PriceCalculator to compute the total price.
        
        Args:
            symbol: The financial instrument symbol (e.g., "JPM")
            side: The side (BUY or SELL) for the price calculation
            amount: The amount to calculate the price for
            
        Returns:
            The total price as sum of (order_price * consumed_amount)
            for each order used. Returns 0 if no orders exist for the symbol/side.
        """
        # Get or create order book for this symbol
        order_book = self._get_or_create_order_book(symbol)
        
        # Get orders in price-priority order for the given side
        orders = order_book.get_orders(side)
        
        # Delegate to PriceCalculator
        return self._price_calculator.calculate(orders, amount)
    
    def place_trade(self, symbol: str, side: Side, amount: int) -> Trade:
        """
        Execute a trade at the calculated price.
        Delegates to TradeExecutor to execute the trade, which consumes
        order amounts in price-priority sequence.
        
        Args:
            symbol: The financial instrument symbol (e.g., "JPM")
            side: The side of the trade (BUY or SELL)
            amount: The amount to trade
            
        Returns:
            Trade record with execution details including order fills
        """
        # Get or create order book for this symbol
        order_book = self._get_or_create_order_book(symbol)
        
        # Delegate to TradeExecutor
        trade = self._trade_executor.execute(order_book, side, amount)
        
        # Update local order tracking for consumed/removed orders
        self._update_local_order_tracking(trade)
        
        return trade
    
    def _update_local_order_tracking(self, trade: Trade) -> None:
        """
        Update local order tracking after a trade execution.
        Updates or removes orders from the local tracking dictionary
        based on the order fills in the trade.
        
        Args:
            trade: The executed trade with order fill details
        """
        for fill in trade.order_fills:
            order = self._orders.get(fill.order_id)
            if order is not None:
                new_amount = order.amount - fill.filled_amount
                if new_amount == 0:
                    # Order was fully consumed, remove from tracking
                    del self._orders[fill.order_id]
                # Note: order.amount is already updated by TradeExecutor