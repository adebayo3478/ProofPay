"""
ProofPay API Routes

REST endpoints for invoice management and receipt retrieval.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from dotenv import dotenv_values
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import db, models
from . import schemas


router = APIRouter(prefix="/api", tags=["proofpay"])

# Ethereum address regex for validation
ETH_ADDRESS_REGEX = re.compile(r'^0x[a-fA-F0-9]{40}$')


def _get_session():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _env_value(key: str) -> Optional[str]:
    val = os.getenv(key)
    if val:
        return val
    here = Path(__file__).resolve()
    env_paths = [
        Path.cwd() / ".env",
        here.parents[2] / ".env",
        here.parents[3] / ".env",
    ]
    for path in env_paths:
        if path.exists():
            vals = dotenv_values(path)
            val = vals.get(key) or val
            if val:
                return str(val)
    return None


def _merchant_address() -> str:
    """Get and validate merchant address from environment."""
    addr = _env_value("MERCHANT_ADDRESS")
    if not addr:
        raise HTTPException(status_code=500, detail="MERCHANT_ADDRESS is not set")
    addr = addr.strip()
    if not ETH_ADDRESS_REGEX.match(addr):
        raise HTTPException(status_code=500, detail="MERCHANT_ADDRESS is not a valid Ethereum address")
    return addr


def _public_url(request: Request, invoice_id: str) -> str:
    base = os.getenv("PROOFPAY_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL")
    if base:
        return base.rstrip("/") + f"/invoice/{invoice_id}"
    return f"/invoice/{invoice_id}"


def _coerce_amount(amount: str) -> str:
    try:
        dec = Decimal(amount)
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail="amount must be a decimal string")
    if dec <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    # Normalize to plain decimal string (no scientific notation)
    return format(dec, "f")


def _maybe_expire(invoice: models.Invoice) -> bool:
    if invoice.status == "ISSUED" and invoice.expires_at:
        now = datetime.now(timezone.utc)
        exp = invoice.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now >= exp:
            invoice.status = "EXPIRED"
            return True
    return False


@router.post("/invoices", response_model=schemas.InvoiceResponse)
def create_invoice(
    payload: schemas.InvoiceCreateRequest,
    request: Request,
    session=Depends(_get_session),
):
    if payload.expires_at.tzinfo is None:
        expires_at = payload.expires_at.replace(tzinfo=timezone.utc)
    else:
        expires_at = payload.expires_at.astimezone(timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="expiresAt must be in the future")

    amount = _coerce_amount(payload.amount)
    invoice = models.Invoice(
        amount=amount,
        memo=payload.memo,
        currency="USDT0",
        status="ISSUED",
        merchant_address=_merchant_address(),
        expires_at=expires_at,
    )
    session.add(invoice)
    session.commit()

    return schemas.InvoiceResponse(
        id=str(invoice.id),
        amount=invoice.amount,
        memo=invoice.memo,
        currency=invoice.currency,
        status=invoice.status,
        merchant_address=invoice.merchant_address,
        created_at=invoice.created_at,
        expires_at=invoice.expires_at,
        public_url=_public_url(request, str(invoice.id)),
    )


@router.get("/invoices", response_model=dict)
def list_invoices(limit: int = 20, session=Depends(_get_session)):
    items = (
        session.query(models.Invoice)
        .order_by(models.Invoice.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    out = []
    for inv in items:
        out.append(
            {
                "id": str(inv.id),
                "amount": inv.amount,
                "memo": inv.memo,
                "currency": inv.currency,
                "status": inv.status,
                "merchantAddress": inv.merchant_address,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            }
        )
    return {"items": out}


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceResponse)
def get_invoice(invoice_id: str, request: Request, session=Depends(_get_session)):
    inv: Optional[models.Invoice] = session.get(models.Invoice, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="invoice not found")
    if _maybe_expire(inv):
        session.commit()
    return schemas.InvoiceResponse(
        id=str(inv.id),
        amount=inv.amount,
        memo=inv.memo,
        currency=inv.currency,
        status=inv.status,
        merchant_address=inv.merchant_address,
        created_at=inv.created_at,
        expires_at=inv.expires_at,
        public_url=_public_url(request, str(inv.id)),
    )


@router.get("/invoices/{invoice_id}/status", response_model=schemas.InvoiceStatusResponse)
def get_invoice_status(invoice_id: str, session=Depends(_get_session)):
    inv: Optional[models.Invoice] = session.get(models.Invoice, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="invoice not found")
    if _maybe_expire(inv):
        session.commit()
    return schemas.InvoiceStatusResponse(
        id=str(inv.id),
        status=inv.status,
        updated_at=datetime.now(timezone.utc),
    )


@router.get("/invoices/{invoice_id}/receipt", response_model=schemas.ReceiptResponse)
def get_invoice_receipt(invoice_id: str, session=Depends(_get_session)):
    receipt = (
        session.query(models.ProofPayReceipt)
        .filter(models.ProofPayReceipt.invoice_id == invoice_id)
        .order_by(models.ProofPayReceipt.created_at.desc())
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="receipt not found")
    return schemas.ReceiptResponse(
        id=str(receipt.id),
        invoice_id=str(receipt.invoice_id),
        payment_id=str(receipt.payment_id),
        iso_type=receipt.iso_type,
        iso_xml=receipt.iso_xml,
        iso_json=receipt.iso_json,
        evidence_bundle_hash=receipt.evidence_bundle_hash,
        anchor_tx_hash=receipt.anchor_tx_hash,
        verification_ref_or_url=receipt.verification_ref_or_url,
        created_at=receipt.created_at,
    )


@router.get("/config")
def get_config():
    return {
        "merchantAddress": _merchant_address(),
        "usdt0Address": _env_value("USDT0_ADDRESS"),
        "chainId": _env_value("CHAIN_ID"),
        "rpcUrl": _env_value("FLARE_RPC_URL"),
    }
