from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from sortedcontainers import SortedDict
from oms_shared.models import OrderEvent, FillEvent, ExecType, Side
import uuid


@dataclass
class BookOrder:
    order_id: str
    cl_ord_id: str
    account: str
    session_id: str
    side: Side
    quantity: Decimal
    remaining: Decimal
    price: Optional[Decimal]  # None = market order


@dataclass
class Fill:
    exec_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    maker_order_id: str = ""
    taker_order_id: str = ""
    maker_cl_ord_id: str = ""
    taker_cl_ord_id: str = ""
    maker_account: str = ""
    taker_account: str = ""
    maker_session_id: str = ""
    taker_session_id: str = ""
    symbol: str = ""
    side: Side = Side.BUY
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")


class OrderBook:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        # bids: price → deque[BookOrder], highest price first → use negated keys
        self._bids: SortedDict = SortedDict(lambda k: -k)
        # asks: price → deque[BookOrder], lowest price first
        self._asks: SortedDict = SortedDict()
        self._orders: dict[str, tuple[str, Decimal]] = {}  # order_id → (side, price)

    def add_order(self, order: OrderEvent) -> list[Fill]:
        book_order = BookOrder(
            order_id=order.order_id,
            cl_ord_id=order.cl_ord_id,
            account=order.account,
            session_id=order.session_id,
            side=order.side,
            quantity=order.quantity,
            remaining=order.quantity,
            price=order.price,
        )

        fills = self._match(book_order)

        if book_order.remaining > 0 and book_order.price is not None:
            # Resting limit order
            book = self._bids if book_order.side == Side.BUY else self._asks
            px = book_order.price
            if px not in book:
                book[px] = deque()
            book[px].append(book_order)
            self._orders[book_order.order_id] = (book_order.side.value, px)

        return fills

    def cancel_order(self, order_id: str) -> bool:
        entry = self._orders.pop(order_id, None)
        if entry is None:
            return False
        side_val, px = entry
        book = self._bids if side_val == Side.BUY.value else self._asks
        level = book.get(px)
        if level:
            remaining = deque(o for o in level if o.order_id != order_id)
            if remaining:
                book[px] = remaining
            else:
                del book[px]
        return True

    def _match(self, taker: BookOrder) -> list[Fill]:
        fills: list[Fill] = []
        opposite = self._asks if taker.side == Side.BUY else self._bids

        while taker.remaining > 0 and opposite:
            best_px = next(iter(opposite))
            if taker.price is not None:
                if taker.side == Side.BUY and taker.price < best_px:
                    break
                if taker.side == Side.SELL and taker.price > best_px:
                    break

            level: deque[BookOrder] = opposite[best_px]
            while taker.remaining > 0 and level:
                maker = level[0]
                fill_qty = min(taker.remaining, maker.remaining)
                fill_px = maker.price  # maker price rules

                taker.remaining -= fill_qty
                maker.remaining -= fill_qty

                fills.append(Fill(
                    maker_order_id=maker.order_id,
                    taker_order_id=taker.order_id,
                    maker_cl_ord_id=maker.cl_ord_id,
                    taker_cl_ord_id=taker.cl_ord_id,
                    maker_account=maker.account,
                    taker_account=taker.account,
                    maker_session_id=maker.session_id,
                    taker_session_id=taker.session_id,
                    symbol=self.symbol,
                    side=taker.side,
                    price=fill_px,
                    quantity=fill_qty,
                ))

                if maker.remaining == 0:
                    level.popleft()
                    self._orders.pop(maker.order_id, None)

            if not level:
                del opposite[best_px]

        return fills

    def snapshot(self) -> dict:
        def _levels(book: SortedDict) -> list[tuple[str, str]]:
            result = []
            for px, level in list(book.items())[:10]:
                qty = sum(o.remaining for o in level)
                result.append((str(px), str(qty)))
            return result

        return {"bids": _levels(self._bids), "asks": _levels(self._asks)}
