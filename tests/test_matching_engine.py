"""Unit tests for the order book matching engine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../services/matching-engine/src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../shared"))

from decimal import Decimal
import pytest
from oms_shared.models import OrderEvent, Side, OrdType
from order_book import OrderBook


def _make_order(side: Side, price: str | None, qty: str, cl_ord_id: str = "C1") -> OrderEvent:
    return OrderEvent(
        order_id=f"ORD-{cl_ord_id}",
        cl_ord_id=cl_ord_id,
        account="ACC1",
        symbol="AAPL",
        side=side,
        ord_type=OrdType.LIMIT if price else OrdType.MARKET,
        quantity=Decimal(qty),
        price=Decimal(price) if price else None,
        session_id="OMS:CLIENT1",
    )


class TestOrderBook:
    def setup_method(self):
        self.book = OrderBook("AAPL")

    def test_no_match_empty_book(self):
        fills = self.book.add_order(_make_order(Side.BUY, "100.00", "100"))
        assert fills == []

    def test_resting_order_stored(self):
        self.book.add_order(_make_order(Side.BUY, "100.00", "100"))
        snap = self.book.snapshot()
        assert len(snap["bids"]) == 1
        assert snap["bids"][0] == ("100.00", "100")

    def test_full_match(self):
        self.book.add_order(_make_order(Side.BUY, "100.00", "100", "BUY1"))
        fills = self.book.add_order(_make_order(Side.SELL, "100.00", "100", "SELL1"))
        assert len(fills) == 1
        assert fills[0].quantity == Decimal("100")
        assert fills[0].price == Decimal("100.00")
        # Book should be empty
        snap = self.book.snapshot()
        assert snap["bids"] == []
        assert snap["asks"] == []

    def test_partial_match(self):
        self.book.add_order(_make_order(Side.BUY, "100.00", "100", "BUY1"))
        fills = self.book.add_order(_make_order(Side.SELL, "100.00", "50", "SELL1"))
        assert len(fills) == 1
        assert fills[0].quantity == Decimal("50")
        snap = self.book.snapshot()
        assert snap["bids"][0] == ("100.00", "50")  # 50 remaining

    def test_price_priority(self):
        # Higher bid matches first
        self.book.add_order(_make_order(Side.BUY, "99.00", "100", "BUY-LOW"))
        self.book.add_order(_make_order(Side.BUY, "101.00", "100", "BUY-HIGH"))
        fills = self.book.add_order(_make_order(Side.SELL, "99.00", "100", "SELL1"))
        assert len(fills) == 1
        assert fills[0].maker_cl_ord_id == "BUY-HIGH"

    def test_no_cross_spread(self):
        # Bid 99, ask 101 — no match
        self.book.add_order(_make_order(Side.BUY, "99.00", "100", "BUY1"))
        fills = self.book.add_order(_make_order(Side.SELL, "101.00", "100", "SELL1"))
        assert fills == []
        snap = self.book.snapshot()
        assert len(snap["bids"]) == 1
        assert len(snap["asks"]) == 1

    def test_cancel_order(self):
        self.book.add_order(_make_order(Side.BUY, "100.00", "100", "BUY1"))
        result = self.book.cancel_order("ORD-BUY1")
        assert result is True
        snap = self.book.snapshot()
        assert snap["bids"] == []

    def test_cancel_nonexistent(self):
        result = self.book.cancel_order("DOES-NOT-EXIST")
        assert result is False

    def test_multiple_fills_sweep(self):
        # Two small asks get swept by one large bid
        self.book.add_order(_make_order(Side.SELL, "100.00", "50", "SELL1"))
        self.book.add_order(_make_order(Side.SELL, "100.00", "50", "SELL2"))
        fills = self.book.add_order(_make_order(Side.BUY, "100.00", "100", "BUY1"))
        assert len(fills) == 2
        total_filled = sum(f.quantity for f in fills)
        assert total_filled == Decimal("100")
