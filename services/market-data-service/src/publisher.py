from __future__ import annotations
import quickfix as fix
from oms_shared.models import MarketDataUpdate
from fix_application import MarketDataApplication
import structlog

log = structlog.get_logger()


def publish_snapshot(app: MarketDataApplication, update: MarketDataUpdate) -> None:
    subscribers = app.subscribers_for(update.symbol)
    if not subscribers:
        return

    msg = fix.Message()
    header = msg.getHeader()
    header.setField(fix.MsgType(fix.MsgType_MarketDataSnapshotFullRefresh))
    msg.setField(fix.Symbol(update.symbol))

    grp = fix.MarketDataSnapshotFullRefresh.NoMDEntries()
    entries = []

    for price, qty in update.bids:
        entry = fix.Group(268, 269)  # NoMDEntries, MDEntryType
        entry.setField(fix.MDEntryType("0"))  # Bid
        entry.setField(fix.MDEntryPx(float(price)))
        entry.setField(fix.MDEntrySize(float(qty)))
        entries.append(entry)

    for price, qty in update.asks:
        entry = fix.Group(268, 269)
        entry.setField(fix.MDEntryType("1"))  # Offer
        entry.setField(fix.MDEntryPx(float(price)))
        entry.setField(fix.MDEntrySize(float(qty)))
        entries.append(entry)

    msg.setField(fix.NoMDEntries(len(entries)))
    for e in entries:
        msg.addGroup(e)

    for session_id in subscribers:
        try:
            fix.Session.sendToTarget(msg, session_id)
        except Exception:
            log.exception("mktdata.send.error", session=str(session_id))
