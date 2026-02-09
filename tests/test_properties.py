"""
Property-based tests for the Order Management System.
"""

import pytest
from hypothesis import given, settings, strategies as st

from src.domain.models import Order, Side
from src.domain.order_book import OrderBook
from src.services.order_manager import OrderManagement
from src.services.price_calculator import PriceCalculator
from src.services.trade_executor import TradeExecutor


# Strategies for generating valid Order components
order_id_strategy = st.integers(min_value=1, max_value=10_000_000)
symbol_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu",)),  # Uppercase letters only
    min_size=1,
    max_size=5
)
side_strategy = st.sampled_from([Side.BUY, Side.SELL])
amount_strategy = st.integers(min_value=1, max_value=1_000_000)
price_strategy = st.integers(min_value=1, max_value=1_000_000)


@st.composite
def order_strategy(draw):
    """Generate a valid Order with random attributes."""
    return Order(
        order_id=draw(order_id_strategy),
        symbol=draw(symbol_strategy),
        side=draw(side_strategy),
        amount=draw(amount_strategy),
        price=draw(price_strategy)
    )


class TestOrderSerializationRoundTrip:
    """
    For any valid Order object, serializing to dict and then deserializing back
    shall produce an Order object equivalent to the original.
    """

    @given(order=order_strategy())
    def test_order_serialization_round_trip(self, order: Order):
        """Property: to_dict() followed by from_dict() produces an equivalent Order."""
        serialized = order.to_dict()
        deserialized = Order.from_dict(serialized)
        
        assert deserialized.order_id == order.order_id
        assert deserialized.symbol == order.symbol
        assert deserialized.side == order.side
        assert deserialized.amount == order.amount
        assert deserialized.price == order.price

    @given(order=order_strategy())
    def test_serialized_dict_has_correct_structure(self, order: Order):
        """Property: Serialized dict contains all required fields with correct types."""
        serialized = order.to_dict()
        
        assert "order_id" in serialized
        assert "symbol" in serialized
        assert "side" in serialized
        assert "amount" in serialized
        assert "price" in serialized
        
        assert isinstance(serialized["order_id"], int)
        assert isinstance(serialized["symbol"], str)
        assert isinstance(serialized["side"], str)
        assert isinstance(serialized["amount"], int)
        assert isinstance(serialized["price"], int)
        assert serialized["side"] in ("BUY", "SELL")


class TestOrderBookSortedInvariant:
    """
    For any sequence of order additions to an OrderBook, the buy orders shall
    always be sorted in ascending price order, and sell orders shall always be
    sorted in descending price order.
    """

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=1,
            max_size=50,
            unique_by=lambda x: x[0]
        )
    )
    @settings(max_examples=100)
    def test_buy_orders_sorted_ascending_by_price(self, orders):
        """Property: Buy orders are always sorted in ascending price order."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=Side.BUY, amount=amount, price=price)
            order_book.add_order(order)
        
        retrieved_orders = order_book.get_orders(Side.BUY)
        prices = [o.price for o in retrieved_orders]
        assert prices == sorted(prices), f"Buy orders not sorted ascending: {prices}"

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=1,
            max_size=50,
            unique_by=lambda x: x[0]
        )
    )
    @settings(max_examples=100)
    def test_sell_orders_sorted_descending_by_price(self, orders):
        """Property: Sell orders are always sorted in descending price order."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=Side.SELL, amount=amount, price=price)
            order_book.add_order(order)
        
        retrieved_orders = order_book.get_orders(Side.SELL)
        prices = [o.price for o in retrieved_orders]
        assert prices == sorted(prices, reverse=True), f"Sell orders not sorted descending: {prices}"

    @given(
        buy_orders=st.lists(
            st.tuples(st.integers(min_value=1, max_value=5_000_000), price_strategy, amount_strategy),
            min_size=0,
            max_size=25,
            unique_by=lambda x: x[0]
        ),
        sell_orders=st.lists(
            st.tuples(st.integers(min_value=5_000_001, max_value=10_000_000), price_strategy, amount_strategy),
            min_size=0,
            max_size=25,
            unique_by=lambda x: x[0]
        )
    )
    @settings(max_examples=100)
    def test_mixed_orders_maintain_sorted_invariant(self, buy_orders, sell_orders):
        """Property: Adding mixed buy and sell orders maintains sorted invariant for both sides."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in buy_orders:
            order = Order(order_id=order_id, symbol="TEST", side=Side.BUY, amount=amount, price=price)
            order_book.add_order(order)
        
        for order_id, price, amount in sell_orders:
            order = Order(order_id=order_id, symbol="TEST", side=Side.SELL, amount=amount, price=price)
            order_book.add_order(order)
        
        buy_retrieved = order_book.get_orders(Side.BUY)
        buy_prices = [o.price for o in buy_retrieved]
        assert buy_prices == sorted(buy_prices)
        
        sell_retrieved = order_book.get_orders(Side.SELL)
        sell_prices = [o.price for o in sell_retrieved]
        assert sell_prices == sorted(sell_prices, reverse=True)


class TestBuyPriceUsesAscendingOrder:
    """
    Buy Price Uses Ascending Order
    """

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=2,
            max_size=20,
            unique_by=lambda x: x[0]
        ).filter(lambda lst: len(set(p for _, p, _ in lst)) >= 2),
        requested_amount=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_buy_price_consumes_lowest_price_first(self, orders, requested_amount):
        """Property: Buy price calculation consumes orders starting from lowest price."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=Side.BUY, amount=amount, price=price)
            order_book.add_order(order)
        
        retrieved_orders = order_book.get_orders(Side.BUY)
        calculated_price = PriceCalculator.calculate(retrieved_orders, requested_amount)
        
        # Manually calculate expected price using ascending order
        sorted_orders = sorted(retrieved_orders, key=lambda o: o.price)
        expected_price = 0
        remaining = requested_amount
        
        for order in sorted_orders:
            if remaining <= 0:
                break
            consumed = min(order.amount, remaining)
            expected_price += order.price * consumed
            remaining -= consumed
        
        assert calculated_price == expected_price


class TestSellPriceUsesDescendingOrder:
    """
    Sell Price Uses Descending Order
    """

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=2,
            max_size=20,
            unique_by=lambda x: x[0]
        ).filter(lambda lst: len(set(p for _, p, _ in lst)) >= 2),
        requested_amount=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_sell_price_consumes_highest_price_first(self, orders, requested_amount):
        """Property: Sell price calculation consumes orders starting from highest price."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=Side.SELL, amount=amount, price=price)
            order_book.add_order(order)
        
        retrieved_orders = order_book.get_orders(Side.SELL)
        calculated_price = PriceCalculator.calculate(retrieved_orders, requested_amount)
        
        # Manually calculate expected price using descending order
        sorted_orders = sorted(retrieved_orders, key=lambda o: o.price, reverse=True)
        expected_price = 0
        remaining = requested_amount
        
        for order in sorted_orders:
            if remaining <= 0:
                break
            consumed = min(order.amount, remaining)
            expected_price += order.price * consumed
            remaining -= consumed
        
        assert calculated_price == expected_price


class TestPriceCalculationFormulaCorrectness:
    """
    Price Calculation Formula Correctness
    """

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=1,
            max_size=20,
            unique_by=lambda x: x[0]
        ),
        requested_amount=st.integers(min_value=1, max_value=1_000_000)
    )
    @settings(max_examples=100)
    def test_price_equals_sum_of_price_times_consumed(self, orders, requested_amount):
        """Property: Total price equals sum of (price × min(order_amount, remaining))."""
        order_list = [
            Order(order_id=order_id, symbol="TEST", side=Side.BUY, amount=amount, price=price)
            for order_id, price, amount in orders
        ]
        
        calculated_price = PriceCalculator.calculate(order_list, requested_amount)
        
        expected_price = 0
        remaining = requested_amount
        for order in order_list:
            if remaining <= 0:
                break
            consumed = min(order.amount, remaining)
            expected_price += order.price * consumed
            remaining -= consumed
        
        assert calculated_price == expected_price

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=0,
            max_size=20,
            unique_by=lambda x: x[0]
        )
    )
    @settings(max_examples=50)
    def test_zero_amount_returns_zero(self, orders):
        """Property: Requesting zero amount returns zero price."""
        order_list = [
            Order(order_id=order_id, symbol="TEST", side=Side.BUY, amount=amount, price=price)
            for order_id, price, amount in orders
        ]
        assert PriceCalculator.calculate(order_list, 0) == 0

    @settings(max_examples=50)
    @given(requested_amount=st.integers(min_value=1, max_value=1_000_000))
    def test_empty_orders_returns_zero(self, requested_amount):
        """Property: Empty order list returns zero price."""
        assert PriceCalculator.calculate([], requested_amount) == 0


class TestPriceCalculationExamples:
    """Unit tests for specific price calculation examples."""

    def setup_method(self):
        """Set up the example order book for each test."""
        self.orders = [
            Order(order_id=1, symbol="JPM", side=Side.BUY, amount=20, price=20),
            Order(order_id=4, symbol="JPM", side=Side.BUY, amount=10, price=21),
        ]

    def test_calculate_price_jpm_buy_20_equals_400(self):
        """calculatePrice(JPM, Buy, 20) = $20 * 20 = $400"""
        assert PriceCalculator.calculate(self.orders, 20) == 400

    def test_calculate_price_jpm_buy_10_equals_200(self):
        """calculatePrice(JPM, Buy, 10) = $20 * 10 = $200"""
        assert PriceCalculator.calculate(self.orders, 10) == 200

    def test_calculate_price_jpm_buy_22_equals_442(self):
        """calculatePrice(JPM, Buy, 22) = $20 * 20 + $21 * 2 = $442"""
        assert PriceCalculator.calculate(self.orders, 22) == 442


class TestTradeExecutionCorrectness:
    """
    Trade Execution Correctness
    """

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=1,
            max_size=20,
            unique_by=lambda x: x[0]
        ),
        side=side_strategy
    )
    @settings(max_examples=100)
    def test_sum_of_amount_reductions_equals_trade_amount(self, orders, side):
        """Property: Sum of amount reductions equals the trade amount."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=side, amount=amount, price=price)
            order_book.add_order(order)
        
        total_available = sum(amount for _, _, amount in orders)
        trade_amount = min(total_available, max(1, total_available // 2))
        
        executor = TradeExecutor()
        trade = executor.execute(order_book, side, trade_amount)
        
        sum_of_fills = sum(fill.filled_amount for fill in trade.order_fills)
        assert sum_of_fills == trade_amount

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, st.integers(min_value=1, max_value=100)),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x[0]
        ),
        side=side_strategy
    )
    @settings(max_examples=100)
    def test_zero_amount_orders_are_removed(self, orders, side):
        """Property: Orders with zero remaining amount are removed."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=side, amount=amount, price=price)
            order_book.add_order(order)
        
        total_available = sum(amount for _, _, amount in orders)
        
        executor = TradeExecutor()
        trade = executor.execute(order_book, side, total_available)
        
        # All orders should be removed
        remaining_orders = order_book.get_orders(side)
        assert len(remaining_orders) == 0

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=1,
            max_size=20,
            unique_by=lambda x: x[0]
        ),
        side=side_strategy
    )
    @settings(max_examples=100)
    def test_total_price_matches_calculate_price(self, orders, side):
        """Property: Trade total price matches what calculate_price would return."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=side, amount=amount, price=price)
            order_book.add_order(order)
        
        total_available = sum(amount for _, _, amount in orders)
        trade_amount = min(total_available, max(1, total_available // 2))
        
        # Calculate expected price before trade
        pre_trade_orders = order_book.get_orders(side)
        expected_price = PriceCalculator.calculate(pre_trade_orders, trade_amount)
        
        executor = TradeExecutor()
        trade = executor.execute(order_book, side, trade_amount)
        
        assert trade.total_price == expected_price


class TestOrderRemovalExcludesFromCalculations:
    """
    Order Removal Excludes from Calculations
    """

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=2,
            max_size=20,
            unique_by=lambda x: x[0]
        ),
        side=side_strategy
    )
    @settings(max_examples=100)
    def test_removed_order_excluded_from_price_calculation(self, orders, side):
        """Property: Removed order is excluded from price calculations."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=side, amount=amount, price=price)
            order_book.add_order(order)
        
        # Remove the first order
        first_order_id = orders[0][0]
        order_book.remove_order(first_order_id)
        
        # Verify it's not in the order book
        remaining_orders = order_book.get_orders(side)
        remaining_ids = [o.order_id for o in remaining_orders]
        assert first_order_id not in remaining_ids


class TestOrderAdditionPreservesAttributes:
    """
    Order Addition Preserves Attributes
    """

    @given(order=order_strategy())
    def test_order_addition_preserves_all_attributes(self, order: Order):
        """Property: After adding an order, retrieving it returns identical attributes."""
        order_book = OrderBook(order.symbol)
        order_book.add_order(order)
        
        retrieved = order_book.get_order(order.order_id)
        
        assert retrieved is not None
        assert retrieved.order_id == order.order_id
        assert retrieved.symbol == order.symbol
        assert retrieved.side == order.side
        assert retrieved.amount == order.amount
        assert retrieved.price == order.price


class TestPriceCalculationIsReadOnly:
    """
    Price Calculation is Read-Only
    """

    @given(
        orders=st.lists(
            st.tuples(order_id_strategy, price_strategy, amount_strategy),
            min_size=1,
            max_size=20,
            unique_by=lambda x: x[0]
        ),
        side=side_strategy,
        requested_amount=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=100)
    def test_price_calculation_does_not_modify_order_book(self, orders, side, requested_amount):
        """Property: Price calculation does not modify order book state."""
        order_book = OrderBook("TEST")
        
        for order_id, price, amount in orders:
            order = Order(order_id=order_id, symbol="TEST", side=side, amount=amount, price=price)
            order_book.add_order(order)
        
        # Capture state before
        orders_before = order_book.get_orders(side)
        amounts_before = [(o.order_id, o.amount) for o in orders_before]
        
        # Calculate price
        PriceCalculator.calculate(orders_before, requested_amount)
        
        # Capture state after
        orders_after = order_book.get_orders(side)
        amounts_after = [(o.order_id, o.amount) for o in orders_after]
        
        assert amounts_before == amounts_after


class TestOrderManagementIntegration:
    """Integration tests for OrderManagement facade."""

    def test_add_and_calculate_price(self):
        """Test adding orders and calculating price through OrderManagement."""
        om = OrderManagement()
        
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        om.add_order(4, "JPM", Side.BUY, 10, 21)
        
        assert om.calculate_price("JPM", Side.BUY, 20) == 400
        assert om.calculate_price("JPM", Side.BUY, 10) == 200
        assert om.calculate_price("JPM", Side.BUY, 22) == 442

    def test_remove_order(self):
        """Test removing an order through OrderManagement."""
        om = OrderManagement()
        
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        om.add_order(4, "JPM", Side.BUY, 10, 21)
        
        om.remove_order(1)
        
        # Only order 4 remains, so price for 10 shares = 10 * 21 = 210
        assert om.calculate_price("JPM", Side.BUY, 10) == 210

    def test_place_trade(self):
        """Test placing a trade through OrderManagement."""
        om = OrderManagement()
        
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        om.add_order(4, "JPM", Side.BUY, 10, 21)
        
        trade = om.place_trade("JPM", Side.BUY, 22)
        
        assert trade.amount == 22
        assert trade.total_price == 442
        assert len(trade.order_fills) == 2
        
        # After trade, only 8 shares remain at price 21
        assert om.calculate_price("JPM", Side.BUY, 8) == 168  # 8 * 21


class TestEdgeCases:
    """Edge case tests for the Order Management System."""

    def test_duplicate_order_id_raises_error(self):
        """Adding an order with duplicate ID should raise ValueError."""
        om = OrderManagement()
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        
        with pytest.raises(ValueError, match="Order with ID 1 already exists"):
            om.add_order(1, "JPM", Side.BUY, 50, 25)

    def test_trade_amount_reflects_actual_filled(self):
        """Trade.amount should reflect actual filled amount, not requested."""
        om = OrderManagement()
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        
        # Request 50 but only 20 available
        trade = om.place_trade("JPM", Side.BUY, 50)
        
        assert trade.amount == 20  # Actual filled, not requested
        assert trade.total_price == 400  # 20 * 20
        assert sum(f.filled_amount for f in trade.order_fills) == 20

    def test_insufficient_liquidity_returns_partial_price(self):
        """Price calculation with insufficient liquidity returns partial price."""
        om = OrderManagement()
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        om.add_order(2, "JPM", Side.BUY, 10, 21)
        
        # Request 50 but only 30 available
        price = om.calculate_price("JPM", Side.BUY, 50)
        
        # Should return price for available 30 shares: 20*20 + 10*21 = 610
        assert price == 610

    def test_empty_order_book_returns_zero_price(self):
        """Price calculation on empty order book returns 0."""
        om = OrderManagement()
        price = om.calculate_price("UNKNOWN", Side.BUY, 100)
        assert price == 0

    def test_zero_amount_trade_returns_empty_trade(self):
        """Trading zero amount returns trade with zero values."""
        om = OrderManagement()
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        
        trade = om.place_trade("JPM", Side.BUY, 0)
        
        assert trade.amount == 0
        assert trade.total_price == 0
        assert len(trade.order_fills) == 0

    def test_same_price_orders_fifo(self):
        """Orders at same price should be consumed in FIFO order."""
        om = OrderManagement()
        om.add_order(1, "JPM", Side.BUY, 10, 20)
        om.add_order(2, "JPM", Side.BUY, 10, 20)  # Same price
        
        trade = om.place_trade("JPM", Side.BUY, 5)
        
        # First order (ID 1) should be consumed first
        assert trade.order_fills[0].order_id == 1
        assert trade.order_fills[0].filled_amount == 5

    def test_trade_on_empty_order_book(self):
        """Trading on empty order book returns trade with zero fills."""
        om = OrderManagement()
        trade = om.place_trade("UNKNOWN", Side.BUY, 100)
        
        assert trade.amount == 0
        assert trade.total_price == 0
        assert len(trade.order_fills) == 0

    def test_remove_nonexistent_order_is_safe(self):
        """Removing non-existent order should not raise error."""
        om = OrderManagement()
        # Should not raise
        om.remove_order(999)

    def test_order_fully_consumed_is_removed(self):
        """Order with zero amount after trade should be removed."""
        om = OrderManagement()
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        
        om.place_trade("JPM", Side.BUY, 20)  # Consume entire order
        
        # Order should be removed, price calculation should return 0
        assert om.calculate_price("JPM", Side.BUY, 10) == 0

    def test_partial_order_consumption(self):
        """Partially consumed order should have reduced amount."""
        om = OrderManagement()
        om.add_order(1, "JPM", Side.BUY, 20, 20)
        
        om.place_trade("JPM", Side.BUY, 5)  # Consume 5 of 20
        
        # 15 shares remain at price 20
        assert om.calculate_price("JPM", Side.BUY, 15) == 300  # 15 * 20