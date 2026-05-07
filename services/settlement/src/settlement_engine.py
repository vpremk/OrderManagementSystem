"""
Settlement engine — consumes the 'trades' Kafka topic and drives T+0 USDC
settlement through Circle's Programmable Wallets (W3S) API.

Flow per trade:
  1. Create PENDING settlement record (idempotent — skip if already exists)
  2. Provision buyer + seller wallets on first encounter (SCA via W3S)
  3. Gas gate: verify buyer wallet holds native token before submitting
  4. POST /v1/w3s/developer/transactions/transfer — buyer → seller
  5. Poll GET /v1/w3s/transactions/{id} until terminal state
  6. Mark settlement SETTLED (with txHash + blockHeight) or FAILED
"""
from __future__ import annotations
import threading
import time
import uuid
import structlog
from oms_shared.models import TradeEvent
from oms_shared.kafka_utils import make_consumer, consume_loop, TOPIC_TRADES
import settlement_repo as repo
from circle_client import CircleClient, STATES_OK, STATES_ERR

log = structlog.get_logger()

_stop = threading.Event()
_circle = CircleClient()
_wallet_set_id: str = ""

# Poll every 5 s, give up after 2 minutes
_POLL_INTERVAL = 5
_POLL_MAX_ATTEMPTS = 24


def start() -> None:
    global _wallet_set_id
    _wallet_set_id = repo.get_or_create_wallet_set(_circle)
    log.info("settlement.engine.started", wallet_set_id=_wallet_set_id)
    threading.Thread(target=_run_consumer, daemon=True).start()


def _run_consumer() -> None:
    consumer = make_consumer("settlement-service", [TOPIC_TRADES])
    consume_loop(consumer, _handle_trade, _stop)


def _handle_trade(topic: str, payload: dict) -> None:
    trade = TradeEvent(**payload)

    if repo.get_settlement_by_trade(trade.trade_id):
        return  # idempotent replay

    settlement_id = str(uuid.uuid4())
    repo.create_settlement(settlement_id, trade)
    log.info("settlement.pending", settlement_id=settlement_id, trade_id=trade.trade_id,
             symbol=trade.symbol, notional=str(trade.notional))

    try:
        buy_wallet_id, _   = repo.get_or_create_wallet(trade.buy_account,  _circle, _wallet_set_id)
        _,  sell_address   = repo.get_or_create_wallet(trade.sell_account, _circle, _wallet_set_id)

        # Gas gate — buyer wallet must hold native token to cover fees
        if not _circle.has_gas(buy_wallet_id):
            repo.mark_failed(settlement_id, "Buyer wallet has no gas; fund with native token first")
            log.error("settlement.no_gas", settlement_id=settlement_id, account=trade.buy_account)
            return

        idem_key = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"oms-transfer-{trade.trade_id}"))
        tx = _circle.transfer(buy_wallet_id, sell_address, trade.notional, idem_key)

        repo.set_processing(settlement_id, tx["id"])
        log.info("settlement.transfer.initiated", settlement_id=settlement_id,
                 circle_tx_id=tx["id"], state=tx.get("state"))

        threading.Thread(
            target=_poll_transaction,
            args=(settlement_id, tx["id"]),
            daemon=True,
        ).start()

    except Exception as exc:
        repo.mark_failed(settlement_id, str(exc))
        log.error("settlement.initiation.failed", settlement_id=settlement_id, error=str(exc))


def _poll_transaction(settlement_id: str, tx_id: str) -> None:
    for attempt in range(_POLL_MAX_ATTEMPTS):
        time.sleep(_POLL_INTERVAL)
        try:
            tx = _circle.get_transaction(tx_id)
            state = tx.get("state", "")
            log.info("settlement.poll", settlement_id=settlement_id,
                     attempt=attempt + 1, state=state)

            if state in STATES_OK:
                repo.mark_settled(
                    settlement_id,
                    tx_hash=tx.get("txHash"),
                    block_height=tx.get("blockHeight"),
                    network_fee=tx.get("networkFee"),
                )
                log.info("settlement.settled", settlement_id=settlement_id,
                         tx_hash=tx.get("txHash"), block_height=tx.get("blockHeight"))
                return

            if state in STATES_ERR:
                repo.mark_failed(settlement_id, f"Circle transaction {state}")
                log.error("settlement.transfer.failed", settlement_id=settlement_id, state=state)
                return

        except Exception as exc:
            log.warning("settlement.poll.error", settlement_id=settlement_id, error=str(exc))

    repo.mark_failed(settlement_id, f"Timed out after {_POLL_MAX_ATTEMPTS * _POLL_INTERVAL} s")
    log.error("settlement.timeout", settlement_id=settlement_id)
