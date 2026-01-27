"""
Internal schemas/dataclasses used by the ISO and anchoring modules.

Note: ProofPay-specific API schemas are in app/proofpay/schemas.py
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VerificationResult:
    """Result of verifying an evidence bundle."""
    bundle_hash: str
    errors: list[str]


@dataclass
class ChainMatch:
    """Result of looking up an anchor on-chain."""
    matches: bool
    txid: Optional[str] = None
    anchored_at: Optional[datetime] = None
