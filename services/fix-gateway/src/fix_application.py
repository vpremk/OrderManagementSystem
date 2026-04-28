from __future__ import annotations
import os
import threading
import quickfix as fix
import structlog
from decimal import Decimal
from confluent_kafka import Producer
from oms_shared.models import OrderEvent, Side, OrdType, ExecutionReportEvent
from oms_shared.kafka_utils import (
    make_producer, make_consumer, publish, consume_loop,
    TOPIC_ORDERS_NEW, TOPIC_EXECUTIONS_REPORTS,
)
from oms_shared.telemetry import orders_received

log = structlog.get_logger()


class OMSApplication(fix.Application):
    def __init__(self) -> None:
        super().__init__()
        self._producer: Producer = make_producer()
        self._sessions: dict[str, fix.SessionID] = {}
        self._stop = threading.Event()
        self._consumer_thread = threading.Thread(target=self._consume_reports, daemon=True)

    def start_consumer(self) -> None:
        self._consumer_thread.start()

    def stop(self) -> None:
        self._stop.set()

    # QuickFIX callbacks
    def onCreate(self, session_id: fix.SessionID) -> None:
        log.info("fix.session.created", session=str(session_id))

    def onLogon(self, session_id: fix.SessionID) -> None:
        key = f"{session_id.getSenderCompID()}:{session_id.getTargetCompID()}"
        self._sessions[key] = session_id
        log.info("fix.session.logon", session=str(session_id))

    def onLogout(self, session_id: fix.SessionID) -> None:
        key = f"{session_id.getSenderCompID()}:{session_id.getTargetCompID()}"
        self._sessions.pop(key, None)
        log.info("fix.session.logout", session=str(session_id))

    def toAdmin(self, message: fix.Message, session_id: fix.SessionID) -> None:
        pass

    def fromAdmin(self, message: fix.Message, session_id: fix.SessionID) -> None:
        pass

    def toApp(self, message: fix.Message, session_id: fix.SessionID) -> None:
        log.debug("fix.outbound", msg=message.toString().strip())

    def fromApp(self, message: fix.Message, session_id: fix.SessionID) -> None:
        msg_type = fix.MsgType()
        message.getHeader().getField(msg_type)
        t = msg_type.getValue()
        log.debug("fix.inbound", msg_type=t)

        session_key = f"{session_id.getSenderCompID()}:{session_id.getTargetCompID()}"

        if t == fix.MsgType_NewOrderSingle:
            self._handle_new_order(message, session_key)
        elif t == fix.MsgType_OrderCancelRequest:
            self._handle_cancel(message, session_key)
        elif t == fix.MsgType_OrderCancelReplaceRequest:
            self._handle_replace(message, session_key)

    # Inbound handlers
    def _handle_new_order(self, msg: fix.Message, session_key: str) -> None:
        try:
            cl_ord_id = fix.ClOrdID(); msg.getField(cl_ord_id)
            symbol    = fix.Symbol();   msg.getField(symbol)
            side      = fix.Side();     msg.getField(side)
            ord_type  = fix.OrdType();  msg.getField(ord_type)
            qty       = fix.OrderQty(); msg.getField(qty)
            account   = fix.Account();
            try:
                msg.getField(account)
                acct = account.getValue()
            except fix.FieldNotFound:
                acct = "DEFAULT"

            price_val = None
            if ord_type.getValue() == fix.OrdType_LIMIT:
                price = fix.Price(); msg.getField(price)
                price_val = Decimal(str(price.getValue()))

            event = OrderEvent(
                cl_ord_id=cl_ord_id.getValue(),
                account=acct,
                symbol=symbol.getValue(),
                side=Side(side.getValue()),
                ord_type=OrdType(ord_type.getValue()),
                quantity=Decimal(str(qty.getValue())),
                price=price_val,
                session_id=session_key,
            )
            orders_received.labels(service="fix-gateway", symbol=event.symbol).inc()
            publish(self._producer, TOPIC_ORDERS_NEW, event.order_id, event)
            log.info("fix.order.received", cl_ord_id=event.cl_ord_id, symbol=event.symbol)
        except Exception:
            log.exception("fix.order.parse_error")

    def _handle_cancel(self, msg: fix.Message, session_key: str) -> None:
        log.info("fix.cancel.received", session=session_key)
        # TODO: publish cancel event

    def _handle_replace(self, msg: fix.Message, session_key: str) -> None:
        log.info("fix.replace.received", session=session_key)
        # TODO: publish replace event

    # Outbound: consume execution reports and send FIX 35=8
    def _consume_reports(self) -> None:
        consumer = make_consumer("fix-gateway-reporter", [TOPIC_EXECUTIONS_REPORTS])
        consume_loop(consumer, self._send_execution_report, self._stop)

    def _send_execution_report(self, topic: str, payload: dict) -> None:
        try:
            evt = ExecutionReportEvent(**payload)
            session_key = evt.session_id
            # Resolve session: find the matching SessionID where OMS is sender
            session_id = None
            for k, sid in self._sessions.items():
                if k == session_key or evt.account in k:
                    session_id = sid
                    break

            if session_id is None:
                log.warning("fix.session.not_found", session_key=session_key)
                return

            report = fix.Message()
            header = report.getHeader()
            header.setField(fix.MsgType(fix.MsgType_ExecutionReport))
            report.setField(fix.OrderID(evt.order_id))
            report.setField(fix.ExecID(evt.exec_id))
            report.setField(fix.ExecType(evt.exec_type.value))
            report.setField(fix.OrdStatus(evt.ord_status.value))
            report.setField(fix.Symbol(evt.symbol))
            report.setField(fix.Side(evt.side.value))
            report.setField(fix.LeavesQty(float(evt.leaves_qty)))
            report.setField(fix.CumQty(float(evt.cum_qty)))
            report.setField(fix.AvgPx(float(evt.avg_px)))
            report.setField(fix.LastQty(float(evt.last_qty)))
            report.setField(fix.LastPx(float(evt.last_px)))
            report.setField(fix.ClOrdID(evt.cl_ord_id))

            fix.Session.sendToTarget(report, session_id)
            log.info("fix.exec_report.sent", order_id=evt.order_id, exec_type=evt.exec_type)
        except Exception:
            log.exception("fix.exec_report.error")
