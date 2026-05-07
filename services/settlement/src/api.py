from __future__ import annotations
import uuid
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from pydantic import BaseModel
import settlement_repo as repo
from circle_client import CircleClient

app = FastAPI(title="OMS Settlement Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

_circle = CircleClient()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Settlements ───────────────────────────────────────────────────────────────

@app.get("/settlements")
def list_settlements(
    status: Optional[str] = Query(None, description="PENDING | PROCESSING | SETTLED | FAILED"),
    symbol: Optional[str] = Query(None),
):
    return repo.list_settlements(status=status, symbol=symbol)


@app.get("/settlements/{settlement_id}")
def get_settlement(settlement_id: str):
    s = repo.get_settlement(settlement_id)
    if not s:
        raise HTTPException(status_code=404, detail="Settlement not found")
    return s


# ── Wallet management ─────────────────────────────────────────────────────────

@app.get("/wallets")
def list_wallets():
    """List all provisioned Circle SCA wallets and their on-chain addresses."""
    return repo.list_wallets()


class TransferOwnershipRequest(BaseModel):
    new_owner_address: str


@app.post("/wallets/{account}/transfer-ownership", status_code=202)
def transfer_ownership(account: str, body: TransferOwnershipRequest):
    """
    Hand MSCA ownership from Circle to an external EOA.
    After this succeeds, Circle can no longer sign for this wallet.
    Call GET /v1/w3s/transactions/{id} to track the on-chain status.
    """
    wallets = repo.list_wallets()
    wallet = next((w for w in wallets if w["account"] == account), None)
    if not wallet:
        raise HTTPException(status_code=404, detail=f"No wallet provisioned for account '{account}'")

    idem_key = str(uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"oms-ownership-{account}-{body.new_owner_address}",
    ))
    tx = _circle.transfer_ownership(
        wallet_id=wallet["circle_wallet_id"],
        contract_address=wallet["wallet_address"],
        new_owner_address=body.new_owner_address,
        idempotency_key=idem_key,
    )
    return {
        "circle_transaction_id": tx["id"],
        "state": tx.get("state"),
        "wallet_id": wallet["circle_wallet_id"],
        "contract_address": wallet["wallet_address"],
        "new_owner": body.new_owner_address,
    }


@app.get("/wallets/{account}/balances")
def get_wallet_balances(account: str):
    """Return on-chain token balances for the account's Circle wallet."""
    wallets = repo.list_wallets()
    wallet = next((w for w in wallets if w["account"] == account), None)
    if not wallet:
        raise HTTPException(status_code=404, detail=f"No wallet provisioned for account '{account}'")
    return {
        "account": account,
        "wallet_id": wallet["circle_wallet_id"],
        "address": wallet["wallet_address"],
        "balances": _circle.get_wallet_balances(wallet["circle_wallet_id"]),
    }
