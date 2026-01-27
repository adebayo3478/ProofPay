"""
ProofPay Database Models

SQLAlchemy models for:
- Invoice: merchant invoices for USDT0 payments
- Payment: detected on-chain payments
- ProofPayReceipt: ISO 20022 receipts with evidence anchoring
- ProofPayWorkerState: worker checkpoint persistence
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR

from .db import Base


class GUID(TypeDecorator):
    """
    Platform-independent GUID/UUID type.

    Uses PostgreSQL UUID when available, otherwise stores as CHAR(36) for SQLite.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            if isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(str(value))
        # store as string
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value  # already UUID
        return uuid.UUID(value)


class Invoice(Base):
    """Merchant invoice for USDT0 payment."""
    __tablename__ = "pp_invoices"

    id = Column(GUID, primary_key=True, default=uuid.uuid4, nullable=False)
    amount = Column(String, nullable=False)  # decimal string
    memo = Column(String, nullable=True)
    currency = Column(String, nullable=False, default="USDT0")
    status = Column(String, nullable=False, default="ISSUED")  # ISSUED | PAID | EXPIRED
    merchant_address = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_pp_invoices_status", "status"),
        Index("ix_pp_invoices_merchant", "merchant_address"),
        Index("ix_pp_invoices_created", "created_at"),
    )


class Payment(Base):
    """Detected on-chain payment for an invoice."""
    __tablename__ = "pp_payments"

    id = Column(GUID, primary_key=True, default=uuid.uuid4, nullable=False)
    invoice_id = Column(GUID, nullable=False, index=True)
    tx_hash = Column(String, nullable=False, unique=True)
    payer_address = Column(String, nullable=False)
    token_address = Column(String, nullable=False)
    amount = Column(String, nullable=False)  # decimal string
    block_number = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_pp_payments_invoice", "invoice_id"),
    )


class ProofPayReceipt(Base):
    """ISO 20022 receipt with evidence bundle and optional on-chain anchor."""
    __tablename__ = "pp_receipts"

    id = Column(GUID, primary_key=True, default=uuid.uuid4, nullable=False)
    invoice_id = Column(GUID, nullable=False, index=True)
    payment_id = Column(GUID, nullable=False, index=True)
    iso_type = Column(String, nullable=False)
    iso_xml = Column(String, nullable=True)
    iso_json = Column(String, nullable=True)
    evidence_bundle_hash = Column(String, nullable=True)
    anchor_tx_hash = Column(String, nullable=True)
    verification_ref_or_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_pp_receipts_invoice", "invoice_id"),
        Index("ix_pp_receipts_payment", "payment_id"),
    )


class ProofPayWorkerState(Base):
    """Key-value store for worker state (e.g., last processed block)."""
    __tablename__ = "pp_worker_state"

    id = Column(GUID, primary_key=True, default=uuid.uuid4, nullable=False)
    key = Column(String, nullable=False, unique=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
