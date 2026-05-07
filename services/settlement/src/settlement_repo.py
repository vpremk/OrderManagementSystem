from __future__ import annotations
import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import Base, Settlement, SettlementAccount, SettlementConfig
from oms_shared.models import TradeEvent
import structlog

log = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://oms:oms_secret@postgres:5432/oms")
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL)
    return _engine


def init_db() -> None:
    Base.metadata.create_all(_get_engine())
    log.info("settlement.db.initialized")


# ── WalletSet bootstrap ───────────────────────────────────────────────────────

def get_or_create_wallet_set(circle_client, name: str = "OMS WalletSet") -> str:
    """Returns the Circle wallet set ID, creating and persisting it on first call."""
    with Session(_get_engine()) as session:
        cfg = session.query(SettlementConfig).filter_by(key="wallet_set_id").first()
        if cfg:
            return cfg.value
        ws = circle_client.create_wallet_set(name)
        session.add(SettlementConfig(key="wallet_set_id", value=ws["id"]))
        session.commit()
        log.info("settlement.walletset.created", wallet_set_id=ws["id"])
        return ws["id"]


# ── Wallet provisioning ───────────────────────────────────────────────────────

def get_or_create_wallet(account: str, circle_client, wallet_set_id: str) -> tuple[str, str]:
    """
    Returns (circle_wallet_id, on_chain_address) for the account.
    Creates the wallet on first encounter and persists the mapping.
    """
    with Session(_get_engine()) as session:
        sa = session.query(SettlementAccount).filter_by(account=account).first()
        if sa:
            return sa.circle_wallet_id, sa.wallet_address
        wallet = circle_client.create_wallet(wallet_set_id, account)
        session.add(SettlementAccount(
            account=account,
            circle_wallet_id=wallet["id"],
            wallet_address=wallet["address"],
            blockchain=wallet.get("blockchain", "ETH-SEPOLIA"),
        ))
        session.commit()
        log.info("settlement.wallet.created", account=account,
                 wallet_id=wallet["id"], address=wallet["address"])
        return wallet["id"], wallet["address"]


def list_wallets() -> list[dict]:
    with Session(_get_engine()) as session:
        return [_wallet_row(sa) for sa in session.query(SettlementAccount).all()]


# ── Settlement CRUD ───────────────────────────────────────────────────────────

def create_settlement(settlement_id: str, trade: TradeEvent) -> None:
    from circle_client import CIRCLE_BLOCKCHAIN
    with Session(_get_engine()) as session:
        session.add(Settlement(
            settlement_id=settlement_id,
            trade_id=trade.trade_id,
            buy_order_id=trade.buy_order_id,
            sell_order_id=trade.sell_order_id,
            buy_exec_id=trade.buy_exec_id,
            sell_exec_id=trade.sell_exec_id,
            buy_account=trade.buy_account,
            sell_account=trade.sell_account,
            symbol=trade.symbol,
            quantity=trade.quantity,
            price=trade.price,
            notional_usd=trade.notional,
            blockchain=CIRCLE_BLOCKCHAIN,
            status="PENDING",
        ))
        session.commit()


def get_settlement_by_trade(trade_id: str) -> dict | None:
    with Session(_get_engine()) as session:
        row = session.query(Settlement).filter_by(trade_id=trade_id).first()
        return _row(row) if row else None


def get_settlement(settlement_id: str) -> dict | None:
    with Session(_get_engine()) as session:
        row = session.query(Settlement).filter_by(settlement_id=settlement_id).first()
        return _row(row) if row else None


def list_settlements(status: str | None = None, symbol: str | None = None) -> list[dict]:
    with Session(_get_engine()) as session:
        q = session.query(Settlement)
        if status:
            q = q.filter_by(status=status)
        if symbol:
            q = q.filter_by(symbol=symbol)
        return [_row(r) for r in q.order_by(Settlement.created_at.desc()).all()]


def set_processing(settlement_id: str, circle_transfer_id: str) -> None:
    with Session(_get_engine()) as session:
        row = session.query(Settlement).filter_by(settlement_id=settlement_id).first()
        if row:
            row.status = "PROCESSING"
            row.circle_transfer_id = circle_transfer_id
            session.commit()


def mark_settled(settlement_id: str, tx_hash: str | None, block_height: int | None,
                 network_fee: str | None = None) -> None:
    with Session(_get_engine()) as session:
        row = session.query(Settlement).filter_by(settlement_id=settlement_id).first()
        if row:
            row.status = "SETTLED"
            row.settled_at = datetime.utcnow()
            row.tx_hash = tx_hash
            row.block_height = block_height
            row.network_fee = network_fee
            session.commit()


def mark_failed(settlement_id: str, error: str) -> None:
    with Session(_get_engine()) as session:
        row = session.query(Settlement).filter_by(settlement_id=settlement_id).first()
        if row:
            row.status = "FAILED"
            row.error_msg = error
            session.commit()


# ── Serialisation ─────────────────────────────────────────────────────────────

def _row(s: Settlement) -> dict:
    return {
        "settlement_id":      s.settlement_id,
        "trade_id":           s.trade_id,
        "buy_account":        s.buy_account,
        "sell_account":       s.sell_account,
        "buy_order_id":       s.buy_order_id,
        "sell_order_id":      s.sell_order_id,
        "symbol":             s.symbol,
        "quantity":           str(s.quantity),
        "price":              str(s.price),
        "notional_usd":       str(s.notional_usd),
        "blockchain":         s.blockchain,
        "circle_transfer_id": s.circle_transfer_id,
        "tx_hash":            s.tx_hash,
        "block_height":       s.block_height,
        "network_fee":        s.network_fee,
        "status":             s.status,
        "settled_at":         s.settled_at.isoformat() if s.settled_at else None,
        "created_at":         s.created_at.isoformat(),
        "error_msg":          s.error_msg,
    }


def _wallet_row(sa: SettlementAccount) -> dict:
    return {
        "account":          sa.account,
        "circle_wallet_id": sa.circle_wallet_id,
        "wallet_address":   sa.wallet_address,
        "blockchain":       sa.blockchain,
        "created_at":       sa.created_at.isoformat(),
    }
