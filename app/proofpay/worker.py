from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
import time
import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from web3 import Web3  # type: ignore
from web3.middleware import geth_poa_middleware
from dotenv import dotenv_values

from .. import db, models
from .receipt import generate_receipt_for_payment
from .utils import normalize_address, amount_to_units


_HERE = Path(__file__).resolve()
_ENV_PATHS = [
    _HERE.parents[2] / ".env",  # repo root (inner)
    _HERE.parents[3] / ".env",  # workspace root (outer)
]
for _path in _ENV_PATHS:
    if _path.exists():
        load_dotenv(dotenv_path=_path, override=True)

logger = logging.getLogger(__name__)


ERC20_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _get_state(session, key: str) -> Optional[str]:
    row = (
        session.query(models.ProofPayWorkerState)
        .filter(models.ProofPayWorkerState.key == key)
        .one_or_none()
    )
    return row.value if row else None


def _set_state(session, key: str, value: str):
    row = (
        session.query(models.ProofPayWorkerState)
        .filter(models.ProofPayWorkerState.key == key)
        .one_or_none()
    )
    if row:
        row.value = value
    else:
        row = models.ProofPayWorkerState(key=key, value=value)
        session.add(row)
    session.commit()


def _get_decimals(contract) -> int:
    try:
        return int(contract.functions.decimals().call())
    except Exception:
        return 6


def _find_matching_invoice(session, merchant_addr: str, amount_units: str, decimals: int) -> Optional[models.Invoice]:
    now = datetime.now(timezone.utc)
    expired_changed = False
    invoices: List[models.Invoice] = (
        session.query(models.Invoice)
        .filter(models.Invoice.status == "ISSUED", models.Invoice.merchant_address == merchant_addr)
        .order_by(models.Invoice.created_at.asc())
        .all()
    )
    for inv in invoices:
        exp = inv.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now >= exp:
            inv.status = "EXPIRED"
            expired_changed = True
            continue
        try:
            inv_units = amount_to_units(inv.amount, decimals)
        except Exception:
            continue
        if inv_units == amount_units:
            if expired_changed:
                session.commit()
            return inv
    if expired_changed:
        session.commit()
    return None


def run_worker():
    def _get_env(key: str) -> Optional[str]:
        val = os.getenv(key)
        if val:
            return val
        for path in _ENV_PATHS:
            if path.exists():
                vals = dotenv_values(path)
                val = vals.get(key)
                if val:
                    return str(val)
        return None

    # Add CWD .env as a last-resort lookup
    if (Path.cwd() / ".env").exists():
        _ENV_PATHS.insert(0, Path.cwd() / ".env")

    rpc_url = _get_env("FLARE_RPC_URL")
    usdt0_address = _get_env("USDT0_ADDRESS")
    merchant_address = _get_env("MERCHANT_ADDRESS")
    if not rpc_url or not usdt0_address or not merchant_address:
        raise RuntimeError("FLARE_RPC_URL, USDT0_ADDRESS, and MERCHANT_ADDRESS must be set")

    confirmations = _env_int("CONFIRMATIONS", 3)
    poll_interval = _env_int("POLL_INTERVAL_SECONDS", 10)
    chunk_size = _env_int("PROOFPAY_CHUNK_SIZE", 25)  # Flare RPC limits to 30 blocks max

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    # Flare is a POA chain - inject middleware to handle extraData
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    token = w3.eth.contract(address=Web3.to_checksum_address(usdt0_address), abi=ERC20_ABI)
    decimals = _get_decimals(token)

    merchant_norm = normalize_address(merchant_address)

    logger.info("ProofPay worker started (confirmations=%s, poll=%ss)", confirmations, poll_interval)

    while True:
        session = db.SessionLocal()
        try:
            latest = w3.eth.block_number
            safe_block = latest - confirmations
            if safe_block < 0:
                time.sleep(poll_interval)
                continue

            last_processed = _get_state(session, "last_processed_block")
            if last_processed is None:
                start_block = max(0, safe_block - 2000)
            else:
                start_block = int(last_processed) + 1

            if start_block > safe_block:
                time.sleep(poll_interval)
                continue

            to_block = safe_block
            for from_block in range(start_block, to_block + 1, chunk_size):
                end_block = min(from_block + chunk_size - 1, to_block)
                logs = token.events.Transfer().get_logs(fromBlock=from_block, toBlock=end_block)
                for log in logs:
                    args = log["args"]
                    to_addr = normalize_address(args["to"])
                    if to_addr != merchant_norm:
                        continue
                    value_units = str(args["value"])
                    tx_hash = log["transactionHash"].hex()

                    existing = (
                        session.query(models.Payment)
                        .filter(models.Payment.tx_hash == tx_hash)
                        .one_or_none()
                    )
                    if existing:
                        continue

                    inv = _find_matching_invoice(session, merchant_address, value_units, decimals)
                    if not inv:
                        continue

                    block = w3.eth.get_block(log["blockNumber"])
                    ts = datetime.fromtimestamp(block["timestamp"], tz=timezone.utc)
                    payer = normalize_address(args["from"])
                    payment = models.Payment(
                        id=uuid4(),
                        invoice_id=inv.id,
                        tx_hash=tx_hash,
                        payer_address=payer,
                        token_address=normalize_address(usdt0_address),
                        amount=inv.amount,
                        block_number=str(log["blockNumber"]),
                        timestamp=ts,
                    )
                    session.add(payment)
                    inv.status = "PAID"
                    session.commit()

                    receipt_id = str(uuid4())
                    iso_xml, bundle_hash, anchor_tx, verification_ref = generate_receipt_for_payment(
                        invoice=inv,
                        payment=payment,
                        receipt_id=receipt_id,
                    )
                    receipt = models.ProofPayReceipt(
                        id=receipt_id,
                        invoice_id=inv.id,
                        payment_id=payment.id,
                        iso_type="pain.001.001.09",
                        iso_xml=iso_xml,
                        iso_json=None,
                        evidence_bundle_hash=bundle_hash,
                        anchor_tx_hash=anchor_tx,
                        verification_ref_or_url=verification_ref,
                    )
                    session.add(receipt)
                    session.commit()

                _set_state(session, "last_processed_block", str(end_block))
        except Exception as e:
            logger.error("Worker error: %s", e, exc_info=True)
        finally:
            session.close()
        time.sleep(poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
