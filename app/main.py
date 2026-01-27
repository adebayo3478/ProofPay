"""
ProofPay Backend - Minimal invoice + checkout on Flare using USDT0

This is the main FastAPI application that provides:
- Invoice CRUD API
- Receipt generation with ISO 20022 compliance
- On-chain evidence anchoring
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

# Load .env from repo root if present (dev convenience)
_HERE = Path(__file__).resolve()
_ENV_PATHS = [
    _HERE.parents[1] / ".env",  # repo root (inner)
    _HERE.parents[2] / ".env",  # workspace root (outer)
]
for _path in _ENV_PATHS:
    if _path.exists():
        load_dotenv(dotenv_path=_path, override=True)

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Import database and models
from . import db, models
from .proofpay import routes as proofpay_routes

ARTIFACTS_DIR = os.getenv("ARTIFACTS_DIR", "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

app = FastAPI(
    title="ProofPay API",
    version="1.0.0",
    description="Invoice + checkout system with ISO 20022 receipt generation on Flare",
)

# Mainnet sanity check: ensure contract address matches if using mainnet RPC
MAINNET_RPC_SUBSTR = "flare-api.flare.network"
MAINNET_EXPECTED_CONTRACT = "0xb59f0d6077A15a3778C262264a83A54B9ABbdEff"
_cfg_rpc = os.getenv("FLARE_RPC_URL", "")
_cfg_addr = os.getenv("ANCHOR_CONTRACT_ADDR", "")
if MAINNET_RPC_SUBSTR in _cfg_rpc:
    if _cfg_addr.lower() != MAINNET_EXPECTED_CONTRACT.lower():
        raise RuntimeError(
            "FLARE_RPC_URL points to Flare mainnet but ANCHOR_CONTRACT_ADDR does not match "
            f"expected mainnet EvidenceAnchor address ({MAINNET_EXPECTED_CONTRACT})."
        )

# CORS configuration
web_origin = os.getenv("WEB_ORIGIN", "http://localhost:3000,http://127.0.0.1:3000")
origins = [o.strip() for o in web_origin.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve evidence bundles at /files
app.mount("/files", StaticFiles(directory=ARTIFACTS_DIR), name="files")

# ProofPay API routes
app.include_router(proofpay_routes.router)

# Database setup
models.Base.metadata.create_all(bind=db.engine)


@app.get("/health")
def health() -> dict:
    """Health check endpoint with network info."""
    return {
        "status": "ok",
        "ts": datetime.utcnow().isoformat(),
        "network": {
            "rpc": os.getenv("FLARE_RPC_URL"),
            "chain_id": os.getenv("CHAIN_ID"),
            "usdt0": os.getenv("USDT0_ADDRESS"),
            "anchor_contract": os.getenv("ANCHOR_CONTRACT_ADDR"),
        },
    }
