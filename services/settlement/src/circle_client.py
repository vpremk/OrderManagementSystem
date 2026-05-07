"""
Circle Programmable Wallets (W3S) client.

Entity secret ciphertext is generated fresh for every API call that requires it:
  entity_secret (32 bytes, from CIRCLE_ENTITY_SECRET_HEX)
    → RSA-OAEP + SHA-256 encrypt with Circle's entity public key
    → base64-encode
    → entitySecretCiphertext

Circle's public key is fetched once from GET /v1/w3s/config/entity/publicKey
and cached in memory.  Override with CIRCLE_PUBLIC_KEY env var if needed.

Endpoints used:
  GET  /v1/w3s/config/entity/publicKey                        — fetch RSA public key
  POST /v1/w3s/developer/walletSets                           — create wallet set
  POST /v1/w3s/developer/wallets                              — create SCA wallet(s)
  GET  /v1/w3s/wallets/{id}/balances                          — gas gate check
  POST /v1/w3s/developer/transactions/transfer                — T+0 USDC transfer
  GET  /v1/w3s/transactions/{id}                              — poll state
  POST /v1/w3s/developer/transactions/contractExecution       — transfer MSCA ownership
"""
from __future__ import annotations
import base64
import os
import uuid
from decimal import Decimal

import httpx
import structlog
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

log = structlog.get_logger()

CIRCLE_BASE_URL          = os.getenv("CIRCLE_BASE_URL", "https://api.circle.com")
CIRCLE_API_KEY           = os.getenv("CIRCLE_API_KEY", "")
CIRCLE_ENTITY_SECRET_HEX = os.getenv("CIRCLE_ENTITY_SECRET_HEX", "")
CIRCLE_PUBLIC_KEY        = os.getenv("CIRCLE_PUBLIC_KEY", "")   # optional override
CIRCLE_BLOCKCHAIN        = os.getenv("CIRCLE_BLOCKCHAIN", "ETH-SEPOLIA")
CIRCLE_FEE_LEVEL         = os.getenv("CIRCLE_FEE_LEVEL", "MEDIUM")
CIRCLE_MOCK              = os.getenv("CIRCLE_MOCK", "true").lower() == "true"

# W3S transaction terminal states
STATES_OK  = {"COMPLETE", "CONFIRMED"}
STATES_ERR = {"FAILED", "CANCELLED", "DENIED"}


class CircleClient:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {CIRCLE_API_KEY}",
            "Content-Type": "application/json",
            "accept": "application/json",
        }
        self._public_key_cache: str | None = CIRCLE_PUBLIC_KEY or None

    # ── Entity ciphertext ─────────────────────────────────────────────────────

    def _fetch_public_key(self) -> str:
        """Fetch Circle's RSA entity public key (cached after first call)."""
        if self._public_key_cache:
            return self._public_key_cache
        resp = httpx.get(
            f"{CIRCLE_BASE_URL}/v1/w3s/config/entity/publicKey",
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        self._public_key_cache = resp.json()["data"]["publicKey"]
        log.info("circle.public_key.fetched")
        return self._public_key_cache

    def _entity_ciphertext(self) -> str:
        """
        Encrypt the 32-byte entity secret with Circle's RSA public key
        (PKCS1 OAEP + SHA-256) and return the base64-encoded ciphertext.
        Must be called fresh for each API request — OAEP is non-deterministic.
        """
        if CIRCLE_MOCK:
            return "mock-ciphertext"
        if not CIRCLE_ENTITY_SECRET_HEX:
            raise RuntimeError("CIRCLE_ENTITY_SECRET_HEX is not set")
        entity_secret = bytes.fromhex(CIRCLE_ENTITY_SECRET_HEX)
        if len(entity_secret) != 32:
            raise ValueError("CIRCLE_ENTITY_SECRET_HEX must be 64 hex chars (32 bytes)")
        pub_key = RSA.import_key(self._fetch_public_key())
        cipher  = PKCS1_OAEP.new(key=pub_key, hashAlgo=SHA256)
        return base64.b64encode(cipher.encrypt(entity_secret)).decode()

    # ── WalletSets ────────────────────────────────────────────────────────────

    def create_wallet_set(self, name: str) -> dict:
        """Returns wallet set dict with at least 'id' key."""
        if CIRCLE_MOCK:
            ws_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"oms-ws-{name}"))
            log.info("circle.mock.walletset.created", id=ws_id)
            return {"id": ws_id, "name": name, "custodyType": "DEVELOPER"}

        resp = httpx.post(
            f"{CIRCLE_BASE_URL}/v1/w3s/developer/walletSets",
            headers=self._headers,
            json={
                "idempotencyKey":          str(uuid.uuid5(uuid.NAMESPACE_DNS, f"oms-ws-{name}")),
                "name":                    name,
                "entitySecretCiphertext":  self._entity_ciphertext(),
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"]["walletSet"]

    # ── Wallets ───────────────────────────────────────────────────────────────

    def create_wallet(self, wallet_set_id: str, account: str) -> dict:
        """Returns wallet dict with 'id', 'address', 'state' keys."""
        if CIRCLE_MOCK:
            w_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"oms-wallet-{account}"))
            addr = "0x" + uuid.uuid5(uuid.NAMESPACE_DNS, f"oms-addr-{account}").hex[:40]
            log.info("circle.mock.wallet.created", account=account, wallet_id=w_id, address=addr)
            return {"id": w_id, "address": addr, "state": "LIVE",
                    "walletSetId": wallet_set_id, "blockchain": CIRCLE_BLOCKCHAIN,
                    "accountType": "SCA"}

        resp = httpx.post(
            f"{CIRCLE_BASE_URL}/v1/w3s/developer/wallets",
            headers=self._headers,
            json={
                "idempotencyKey":          str(uuid.uuid5(uuid.NAMESPACE_DNS, f"oms-wallet-{account}")),
                "walletSetId":             wallet_set_id,
                "blockchains":             [CIRCLE_BLOCKCHAIN],
                "count":                   1,
                "metadata":                [{"name": account, "refId": account}],
                "entitySecretCiphertext":  self._entity_ciphertext(),
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"]["wallets"][0]

    # ── Balances ──────────────────────────────────────────────────────────────

    def get_wallet_balances(self, wallet_id: str) -> list[dict]:
        """Returns list of tokenBalance dicts: {token: {...}, amount: '0.05'}."""
        if CIRCLE_MOCK:
            return [{"token": {"isNative": True, "symbol": CIRCLE_BLOCKCHAIN}, "amount": "0.1"}]

        resp = httpx.get(
            f"{CIRCLE_BASE_URL}/v1/w3s/wallets/{wallet_id}/balances",
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"].get("tokenBalances", [])

    def has_gas(self, wallet_id: str) -> bool:
        """True if the wallet holds any native token (required for gas)."""
        for bal in self.get_wallet_balances(wallet_id):
            if bal["token"].get("isNative") and float(bal.get("amount", "0")) > 0:
                return True
        return False

    # ── Transactions ──────────────────────────────────────────────────────────

    def transfer(
        self,
        wallet_id: str,
        destination_address: str,
        amount: Decimal,
        idempotency_key: str,
        token_id: str | None = None,
    ) -> dict:
        """Initiate transfer. Returns {'id': tx_id, 'state': 'INITIATED'}."""
        if CIRCLE_MOCK:
            tx_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"oms-tx-{idempotency_key}"))
            log.info("circle.mock.transfer.initiated", tx_id=tx_id, amount=str(amount))
            return {"id": tx_id, "state": "INITIATED"}

        body: dict = {
            "idempotencyKey":          idempotency_key,
            "walletId":                wallet_id,
            "destinationAddress":      destination_address,
            "amounts":                 [f"{amount:.6f}"],
            "feeLevel":                CIRCLE_FEE_LEVEL,
            "entitySecretCiphertext":  self._entity_ciphertext(),
            "blockchain":              CIRCLE_BLOCKCHAIN,
        }
        if token_id:
            body["tokenId"] = token_id

        resp = httpx.post(
            f"{CIRCLE_BASE_URL}/v1/w3s/developer/transactions/transfer",
            headers=self._headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def get_transaction(self, transaction_id: str) -> dict:
        """
        Returns transaction dict.  Key fields:
          state:       INITIATED | PENDING_RISK_SCREENING | SENT | CONFIRMED | COMPLETE
                       FAILED | CANCELLED | DENIED
          txHash:      '0x...'
          blockHeight: int
          networkFee:  '0.000721...'
        """
        if CIRCLE_MOCK:
            fake_hash = "0x" + f"{abs(hash(transaction_id)):062x}"[:62] + "0000"
            return {"id": transaction_id, "state": "COMPLETE",
                    "txHash": fake_hash, "blockHeight": 10_000_000, "networkFee": "0.0001"}

        resp = httpx.get(
            f"{CIRCLE_BASE_URL}/v1/w3s/transactions/{transaction_id}",
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"]["transaction"]

    def transfer_ownership(
        self,
        wallet_id: str,
        contract_address: str,
        new_owner_address: str,
        idempotency_key: str,
    ) -> dict:
        """
        Call transferNativeOwnership(address) on the MSCA contract,
        handing custody from Circle to an external EOA.
        After this succeeds Circle can no longer sign for this wallet.
        Returns {'id': tx_id, 'state': 'INITIATED'}.
        """
        if CIRCLE_MOCK:
            tx_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"oms-own-{idempotency_key}"))
            log.info("circle.mock.ownership.transfer", tx_id=tx_id, new_owner=new_owner_address)
            return {"id": tx_id, "state": "INITIATED"}

        resp = httpx.post(
            f"{CIRCLE_BASE_URL}/v1/w3s/developer/transactions/contractExecution",
            headers=self._headers,
            json={
                "idempotencyKey":          idempotency_key,
                "walletId":                wallet_id,
                "contractAddress":         contract_address,
                "abiFunctionSignature":    "transferNativeOwnership(address)",
                "abiParameters":           [new_owner_address],
                "feeLevel":                CIRCLE_FEE_LEVEL,
                "entitySecretCiphertext":  self._entity_ciphertext(),
                "refId":                   f"Transfer OMS wallet {wallet_id} to {new_owner_address}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"]
