
import uuid
from datetime import datetime, UTC
from typing import List

from src.domain.models import OrderFill, Side, Trade
from src.domain.order_book import OrderBook
from src.services.price_calculator import PriceCalculator


class TradeExecutor:
    """
    Handles trade execution by consuming order amounts.
    Executes trades by consuming order amounts in price-priority sequence,
    removing orders that reach zero amount, and returning a Trade record
    with complete execution details.
    """
    
    def execute(self, order_book: OrderBook, side: Side, amount: int) -> Trade:
        """
        Execute a trade by consuming order amounts.
        
        Consumes orders in price-priority sequence:
        - For BUY trades: consumes from lowest-priced orders first
        - For SELL trades: consumes from highest-priced orders first
        
        Orders with zero remaining amount after consumption are removed
        from the order book.
        
        Args:
            order_book: The OrderBook to execute the trade against
            side: The side of the trade (BUY or SELL)
            amount: The amount to trade
            
        Returns:
            Trade record with execution details including order fills
        """
        # Get orders in price-priority order
        orders = order_book.get_orders(side)
        
        # Calculate total price before modifying orders
        total_price = PriceCalculator.calculate(orders, amount)
        
        # Execute the trade by consuming orders
        order_fills: List[OrderFill] = []
        remaining = amount
        actual_filled = 0
        actual_price = 0
        
        for order in orders:
            if remaining <= 0:
                break
            
            consumed = min(order.amount, remaining)
            
            # Record the fill
            order_fills.append(OrderFill(
                order_id=order.order_id,
                filled_amount=consumed,
                fill_price=order.price
            ))
            
            # Track actual filled amount and price
            actual_filled += consumed
            actual_price += order.price * consumed
            
            # Update or remove the order
            new_amount = order.amount - consumed
            if new_amount == 0:
                # Remove order with zero amount
                order_book.remove_order(order.order_id)
            else:
                # Update order with reduced amount
                order_book.update_order_amount(order.order_id, new_amount)
            
            remaining -= consumed
        
        # Create and return the trade record with actual filled amounts
        return Trade(
            trade_id=str(uuid.uuid4()),
            symbol=order_book.symbol,
            side=side,
            amount=actual_filled,  # Actual filled amount, not requested
            total_price=actual_price,  # Actual price based on fills
            executed_at=datetime.now(UTC),
            order_fills=order_fills
        )