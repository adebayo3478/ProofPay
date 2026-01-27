from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Tuple

from .. import iso, bundle, models
from ..anchor import anchor_bundle  # type: ignore


def _chain_label() -> str:
    return os.getenv("CHAIN_ID") or os.getenv("FLARE_CHAIN_ID") or "flare"


def generate_receipt_for_payment(
    invoice: models.Invoice,
    payment: models.Payment,
    receipt_id: str,
) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """
    Generates ISO XML + evidence bundle for a payment.
    Returns (iso_xml_text, bundle_hash, anchor_tx_hash, verification_ref).
    """
    created_at = datetime.now(timezone.utc)
    receipt_dict = {
        "id": receipt_id,
        "reference": f"proofpay:invoice:{invoice.id}",
        "tip_tx_hash": payment.tx_hash,
        "chain": _chain_label(),
        "amount": invoice.amount,
        "currency": invoice.currency,
        "sender_wallet": payment.payer_address,
        "receiver_wallet": invoice.merchant_address,
        "status": "paid",
        "created_at": created_at,
    }

    xml_bytes = iso.generate_pain001(receipt_dict)
    xml_text = xml_bytes.decode("utf-8", errors="replace")

    _, bundle_hash = bundle.create_bundle(receipt_dict, xml_bytes)

    anchor_tx_hash: Optional[str] = None
    verification_ref: Optional[str] = bundle_hash

    if os.getenv("ANCHOR_PRIVATE_KEY") and os.getenv("ANCHOR_CONTRACT_ADDR"):
        try:
            tx_hash, _block = anchor_bundle(bundle_hash)
            anchor_tx_hash = tx_hash
            verification_ref = f"flare:tx:{tx_hash}"
        except Exception:
            # Anchoring is best-effort for Sprint 1
            pass

    return xml_text, bundle_hash, anchor_tx_hash, verification_ref
