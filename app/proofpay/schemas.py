"""
ProofPay API Schemas

Pydantic models for request/response validation with security hardening.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Security: max memo length to prevent abuse
MAX_MEMO_LENGTH = 500
# Security: reasonable bounds for invoice amounts
MIN_AMOUNT = Decimal("0.000001")
MAX_AMOUNT = Decimal("1000000000")  # 1 billion


class InvoiceCreateRequest(BaseModel):
    """Request body for creating an invoice."""
    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)
    amount: str = Field(..., description="Decimal amount (string)")
    memo: Optional[str] = Field(None, description="Optional memo", max_length=MAX_MEMO_LENGTH)
    expires_at: datetime = Field(..., alias="expiresAt", description="Expiry timestamp (ISO 8601)")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        """Validate amount is a valid decimal within reasonable bounds."""
        try:
            dec = Decimal(v)
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("amount must be a valid decimal string")
        if dec <= 0:
            raise ValueError("amount must be positive")
        if dec < MIN_AMOUNT:
            raise ValueError(f"amount must be at least {MIN_AMOUNT}")
        if dec > MAX_AMOUNT:
            raise ValueError(f"amount cannot exceed {MAX_AMOUNT}")
        return v

    @field_validator("memo")
    @classmethod
    def sanitize_memo(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize memo - remove control characters."""
        if v is None:
            return v
        # Remove control characters except newlines and tabs
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v)


class InvoiceResponse(BaseModel):
    """Response body for invoice details."""
    model_config = ConfigDict(populate_by_name=True)
    id: str
    amount: str
    memo: Optional[str]
    currency: str
    status: str
    merchant_address: str = Field(..., alias="merchantAddress")
    created_at: datetime
    expires_at: datetime
    public_url: Optional[str] = Field(None, alias="publicUrl")


class InvoiceStatusResponse(BaseModel):
    """Response body for invoice status check."""
    id: str
    status: str
    updated_at: datetime


class PaymentResponse(BaseModel):
    """Response body for payment details."""
    id: str
    invoice_id: str
    tx_hash: str
    payer_address: str
    amount: str
    timestamp: datetime


class ReceiptResponse(BaseModel):
    """Response body for ISO 20022 receipt."""
    id: str
    invoice_id: str
    payment_id: str
    iso_type: str
    iso_xml: Optional[str] = None
    iso_json: Optional[str] = None
    evidence_bundle_hash: Optional[str] = None
    anchor_tx_hash: Optional[str] = None
    verification_ref_or_url: Optional[str] = None
    created_at: datetime


class ConfigResponse(BaseModel):
    """Response body for backend configuration."""
    merchant_address: str = Field(..., alias="merchantAddress")
    usdt0_address: Optional[str] = Field(None, alias="usdt0Address")
    chain_id: Optional[str] = Field(None, alias="chainId")
    rpc_url: Optional[str] = Field(None, alias="rpcUrl")
