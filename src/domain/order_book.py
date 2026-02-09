"""
OrderBook implementation for the Order Management System.

This module provides the OrderBook class that manages orders for a single
financial instrument (symbol). It uses Python's sortedcontainers.SortedList
to maintain price-ordered collections of buy and sell orders.

For production deployment, this can be swapped with a MemoryDB-backed
implementation for horizontal scaling across multiple nodes.
"""

from typing import List, Optional

from sortedcontainers import SortedList

from src.domain.models import Order, Side


class OrderBook:
    """
    Collection of orders for a single symbol, organized by side (buy/sell).
    
    Uses in-memory SortedList for O(log n) insertion and O(k) retrieval.
    Orders are maintained in price-priority order:
    - Buy orders: sorted ascending by price (lowest first)
    - Sell orders: sorted descending by price (highest first)
    
    Attributes:
        symbol: The financial instrument symbol (e.g., "JPM", "GOOG")
    """
    
    def __init__(self, symbol: str):
        """
        Initialize an OrderBook for a specific symbol.
        
        Args:
            symbol: The financial instrument symbol
        """
        self.symbol = symbol
        # Buy orders: sorted ascending by price (lowest first for best buy price)
        self._buy_orders: SortedList[Order] = SortedList(key=lambda o: o.price)
        # Sell orders: sorted descending by price (highest first for best sell price)
        self._sell_orders: SortedList[Order] = SortedList(key=lambda o: -o.price)
        # Index for O(1) lookup by order_id
        self._order_index: dict[int, Order] = {}
    
    def add_order(self, order: Order) -> None:
        """
        Add an order to the order book.
        
        Maintains sorted order automatically via SortedList.
        O(log n) time complexity.
        
        Args:
            order: The Order to add to the book
        """
        if order.side == Side.BUY:
            self._buy_orders.add(order)
        else:
            self._sell_orders.add(order)
        self._order_index[order.order_id] = order
    
    def remove_order(self, order_id: int) -> Optional[Order]:
        """
        Remove an order from the order book.
        
        O(log n) time complexity for removal from SortedList.
        
        Args:
            order_id: The ID of the order to remove
            
        Returns:
            The removed Order, or None if not found
        """
        order = self._order_index.pop(order_id, None)
        if order is None:
            return None
        
        if order.side == Side.BUY:
            self._buy_orders.discard(order)
        else:
            self._sell_orders.discard(order)
        
        return order
    
    def get_order(self, order_id: int) -> Optional[Order]:
        """
        Get an order by ID.
        
        O(1) time complexity via index lookup.
        
        Args:
            order_id: The ID of the order to retrieve
            
        Returns:
            The Order, or None if not found
        """
        return self._order_index.get(order_id)
    
    def get_orders(self, side: Side) -> List[Order]:
        """
        Get all orders for a given side in price-priority order.
        
        Returns orders sorted by:
        - Buy side: ascending price (lowest price first)
        - Sell side: descending price (highest price first)
        
        Args:
            side: The side (BUY or SELL) to retrieve orders for
            
        Returns:
            List of Order objects in price-priority order
        """
        if side == Side.BUY:
            return list(self._buy_orders)
        return list(self._sell_orders)
    
    def update_order_amount(self, order_id: int, new_amount: int) -> bool:
        """
        Update an order's amount in place.
        
        Since amount doesn't affect sort order (only price does),
        we can update in place without re-sorting.
        
        Args:
            order_id: The ID of the order to update
            new_amount: The new amount for the order
            
        Returns:
            True if the order was found and updated, False otherwise
        """
        order = self._order_index.get(order_id)
        if order is None:
            return False
        order.amount = new_amount
        return True