"""
FIX 4.4 client simulator for integration testing.
Connects as an initiator, sends orders and validates execution reports.

Usage:
    python fix_client_simulator.py [--host localhost] [--port 9876] [--sender CLIENT1]
"""
from __future__ import annotations
import argparse
import sys
import time
import threading
import quickfix as fix
import quickfix44 as fix44


class SimulatorApp(fix.Application):
    def __init__(self) -> None:
        super().__init__()
        self._session_id: fix.SessionID | None = None
        self._reports: list[dict] = []
        self._ready = threading.Event()

    def onCreate(self, session_id: fix.SessionID) -> None:
        self._session_id = session_id

    def onLogon(self, session_id: fix.SessionID) -> None:
        print(f"[SIM] Logged on: {session_id}")
        self._session_id = session_id
        self._ready.set()

    def onLogout(self, session_id: fix.SessionID) -> None:
        print(f"[SIM] Logged out: {session_id}")
        self._ready.clear()

    def toAdmin(self, message, session_id) -> None: pass
    def fromAdmin(self, message, session_id) -> None: pass
    def toApp(self, message, session_id) -> None: pass

    def fromApp(self, message: fix.Message, session_id: fix.SessionID) -> None:
        msg_type = fix.MsgType()
        message.getHeader().getField(msg_type)
        if msg_type.getValue() == fix.MsgType_ExecutionReport:
            self._handle_exec_report(message)

    def _handle_exec_report(self, msg: fix.Message) -> None:
        order_id = fix.OrderID(); msg.getField(order_id)
        exec_type = fix.ExecType(); msg.getField(exec_type)
        ord_status = fix.OrdStatus(); msg.getField(ord_status)
        cum_qty = fix.CumQty(); msg.getField(cum_qty)
        avg_px = fix.AvgPx(); msg.getField(avg_px)

        report = {
            "order_id": order_id.getValue(),
            "exec_type": exec_type.getValue(),
            "ord_status": ord_status.getValue(),
            "cum_qty": cum_qty.getValue(),
            "avg_px": avg_px.getValue(),
        }
        self._reports.append(report)
        print(f"[SIM] ExecReport: {report}")

    def send_new_order(self, symbol: str, side: str, qty: float, price: float) -> str:
        if not self._session_id:
            raise RuntimeError("Not connected")

        order = fix44.NewOrderSingle()
        cl_ord_id = f"CLT-{int(time.time()*1000)}"
        order.setField(fix.ClOrdID(cl_ord_id))
        order.setField(fix.Symbol(symbol))
        order.setField(fix.Side(side))
        order.setField(fix.OrdType(fix.OrdType_LIMIT))
        order.setField(fix.OrderQty(qty))
        order.setField(fix.Price(price))
        order.setField(fix.TimeInForce(fix.TimeInForce_DAY))
        order.setField(fix.TransactTime())
        order.setField(fix.Account("TEST_ACCOUNT"))

        fix.Session.sendToTarget(order, self._session_id)
        print(f"[SIM] Sent NewOrderSingle: {cl_ord_id} {symbol} {side} {qty}@{price}")
        return cl_ord_id

    def wait_for_reports(self, count: int, timeout: float = 10.0) -> list[dict]:
        deadline = time.time() + timeout
        while len(self._reports) < count and time.time() < deadline:
            time.sleep(0.1)
        return self._reports[:]


def _make_settings(host: str, port: int, sender: str) -> fix.SessionSettings:
    cfg = f"""
[DEFAULT]
ConnectionType=initiator
StartTime=00:00:00
EndTime=00:00:00
HeartBtInt=30
ResetOnLogon=Y
FileStorePath=/tmp/fix/sim/store
FileLogPath=/tmp/fix/sim/log

[SESSION]
BeginString=FIX.4.4
SenderCompID={sender}
TargetCompID=OMS
SocketConnectHost={host}
SocketConnectPort={port}
"""
    import tempfile, os
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False)
    f.write(cfg)
    f.close()
    return fix.SessionSettings(f.name)


def run_integration_test(host: str, port: int, sender: str) -> bool:
    app = SimulatorApp()
    settings = _make_settings(host, port, sender)
    store_factory = fix.FileStoreFactory(settings)
    log_factory = fix.FileLogFactory(settings)
    initiator = fix.SocketInitiator(app, store_factory, settings, log_factory)
    initiator.start()

    print("[SIM] Connecting...")
    if not app._ready.wait(timeout=15):
        print("[SIM] ERROR: Could not connect within 15s")
        initiator.stop()
        return False

    time.sleep(1)

    # Test 1: Send a buy order
    app.send_new_order("AAPL", fix.Side_BUY, 100, 150.00)
    # Test 2: Send a matching sell order
    time.sleep(0.5)
    app.send_new_order("AAPL", fix.Side_SELL, 100, 150.00)

    # Wait for execution reports: NEW + FILL for each side
    reports = app.wait_for_reports(2, timeout=15)

    success = True
    if len(reports) < 2:
        print(f"[SIM] FAIL: Expected >=2 reports, got {len(reports)}")
        success = False
    else:
        new_rpts = [r for r in reports if r["exec_type"] == "0"]
        fill_rpts = [r for r in reports if r["exec_type"] in ("1", "2")]
        print(f"[SIM] NEW reports: {len(new_rpts)}, FILL reports: {len(fill_rpts)}")
        if not new_rpts:
            print("[SIM] FAIL: No NEW execution reports received")
            success = False
        print("[SIM] PASS" if success else "[SIM] FAIL")

    initiator.stop()
    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--sender", default="CLIENT1")
    args = parser.parse_args()

    ok = run_integration_test(args.host, args.port, args.sender)
    sys.exit(0 if ok else 1)
