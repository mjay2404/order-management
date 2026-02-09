
from typing import List

from src.domain.models import Order


class PriceCalculator:
    """
    Calculates the total price by consuming orders in sequence,
    accumulating (price * consumed_amount) for each order until
    the requested amount is fulfilled.
    """
    
    @staticmethod
    def calculate(orders: List[Order], amount: int) -> int:
        """
        Calculate total price by consuming orders in sequence.
        Orders should be pre-sorted by price priority:
        Args:
            orders: List of orders sorted by price priority
            amount: The total amount to calculate price for
            
        Returns:
            Total price as sum of (order_price * consumed_amount) for each order.
            Returns 0 if amount is 0 or orders list is empty.
        """
        total_price = 0
        remaining = amount
        
        for order in orders:
            if remaining <= 0:
                break
            consumed = min(order.amount, remaining)
            total_price += order.price * consumed
            remaining -= consumed
        
        return total_price