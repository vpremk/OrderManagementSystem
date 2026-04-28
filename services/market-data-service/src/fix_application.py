from __future__ import annotations
import quickfix as fix
import structlog

log = structlog.get_logger()


class MarketDataApplication(fix.Application):
    def __init__(self) -> None:
        super().__init__()
        # symbol → set of sessionIDs subscribed
        self._subscriptions: dict[str, set[str]] = {}
        self._sessions: dict[str, fix.SessionID] = {}

    def onCreate(self, session_id: fix.SessionID) -> None:
        pass

    def onLogon(self, session_id: fix.SessionID) -> None:
        key = str(session_id)
        self._sessions[key] = session_id
        log.info("mktdata.session.logon", session=key)

    def onLogout(self, session_id: fix.SessionID) -> None:
        key = str(session_id)
        self._sessions.pop(key, None)
        for subs in self._subscriptions.values():
            subs.discard(key)
        log.info("mktdata.session.logout", session=key)

    def toAdmin(self, message, session_id) -> None: pass
    def fromAdmin(self, message, session_id) -> None: pass
    def toApp(self, message, session_id) -> None: pass

    def fromApp(self, message: fix.Message, session_id: fix.SessionID) -> None:
        msg_type = fix.MsgType()
        message.getHeader().getField(msg_type)
        if msg_type.getValue() == fix.MsgType_MarketDataRequest:
            self._handle_md_request(message, session_id)

    def _handle_md_request(self, msg: fix.Message, session_id: fix.SessionID) -> None:
        try:
            sub_req = fix.SubscriptionRequestType(); msg.getField(sub_req)
            symbol = fix.Symbol(); msg.getField(symbol)
            sym = symbol.getValue()
            key = str(session_id)

            if sub_req.getValue() == "1":  # Subscribe
                if sym not in self._subscriptions:
                    self._subscriptions[sym] = set()
                self._subscriptions[sym].add(key)
                log.info("mktdata.subscribed", symbol=sym, session=key)
            elif sub_req.getValue() == "2":  # Unsubscribe
                self._subscriptions.get(sym, set()).discard(key)
        except Exception:
            log.exception("mktdata.request.error")

    def subscribers_for(self, symbol: str) -> list[fix.SessionID]:
        keys = self._subscriptions.get(symbol, set())
        return [self._sessions[k] for k in keys if k in self._sessions]
