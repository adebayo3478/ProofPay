# ProofPay

**Crypto invoice payments with ISO 20022 receipts on Flare.**

ProofPay is a minimal invoice + checkout system that lets merchants accept USDT0 payments on the Flare network and automatically generates ISO 20022 compliant receipts with optional onchain evidence anchoring.

---

## What It Does

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Merchant   │      │    Payer     │      │   Worker     │      │   Receipt    │
│  Creates     │ ───▶ │  Pays USDT0  │ ───▶ │  Detects TX  │ ───▶ │  Generated   │
│  Invoice     │      │  via Wallet  │      │  On-Chain    │      │  (ISO 20022) │
└──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
```

1. **Merchant creates invoice** via web UI with amount, memo, and expiry
2. **Payer opens invoice link** and pays with their wallet (MetaMask, Rabby, etc.)
3. **Worker detects payment** by watching USDT0 Transfer events on Flare
4. **Receipt is generated** as ISO 20022 pain.001 XML + evidence bundle
5. **Optional anchoring** of bundle hash on-chain for verifiability

---

##  Quick Start 

### Prerequisites

- Python 3.10+ with pip
- Node.js 18+ with npm
- A Flare wallet with:
  - Some FLR for gas (if using anchoring)
  - The USDT0 token address on Flare mainnet

### 1. Clone and Setup

```powershell
cd C:\path\to\your\projects
git clone https://github.com/your-repo/ProofPay.git
cd ProofPay
```

### 2. Backend Configuration

Create `.env` in the repo root:

```env
# Required
FLARE_RPC_URL=https://flare-api.flare.network/ext/C/rpc
CHAIN_ID=14
USDT0_ADDRESS=0xe7cd86e13AC4309349F30B3435a9d337750fC82D
MERCHANT_ADDRESS=0xYourMerchantWalletAddress

# Optional (for on-chain anchoring)
ANCHOR_CONTRACT_ADDR=0xb59f0d6077A15a3778C262264a83A54B9ABbdEff
ANCHOR_PRIVATE_KEY=0xYourAnchorWalletPrivateKey
ANCHOR_ABI_PATH=contracts/EvidenceAnchor.abi.json
```

### 3. Frontend Configuration

Create `.env.local` in `apps/proofpay/`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010
NEXT_PUBLIC_USDT0_ADDRESS=0xe7cd86e13AC4309349F30B3435a9d337750fC82D
NEXT_PUBLIC_CHAIN_ID=14
NEXT_PUBLIC_FLARE_RPC_URL=https://flare-api.flare.network/ext/C/rpc
```

### 4. Install Dependencies

**Terminal 1 - Backend:**
```powershell
pip install -r requirements.txt
```

**Terminal 2 - Frontend:**
```powershell
cd apps\proofpay
npm install
```

### 5. Run Everything

**Terminal 1 - API Server:**
```powershell
uvicorn app.main:app --reload --port 8010
```

**Terminal 2 - Payment Worker:**
```powershell
python -m app.proofpay.worker
```

**Terminal 3 - Frontend:**
```powershell
cd apps\proofpay
npm run dev
```

### 6. Test It!

1. Open http://localhost:3000/merchant
2. Create an invoice (e.g., 0.01 USDT0)
3. Click the invoice link to open the payment page
4. Connect your wallet and switch to Flare network
5. Pay the invoice
6. Watch the status change to PAID and see your ISO 20022 receipt!

---

##  Project Structure

```
ProofPay/
├── app/                      # Backend (FastAPI)
│   ├── main.py              # API entry point
│   ├── models.py            # SQLAlchemy models
│   ├── db.py                # Database config
│   ├── iso.py               # ISO 20022 XML generator
│   ├── bundle.py            # Evidence bundle creator
│   ├── anchor.py            # On-chain anchoring
│   └── proofpay/            # ProofPay module
│       ├── routes.py        # Invoice API endpoints
│       ├── schemas.py       # Pydantic models
│       ├── worker.py        # Payment detection worker
│       └── receipt.py       # Receipt generation
├── apps/proofpay/           # Frontend (Next.js)
│   ├── app/
│   │   ├── merchant/        # Merchant dashboard
│   │   └── invoice/[id]/    # Payment page
│   └── lib/                 # Config & utilities
├── contracts/               # EvidenceAnchor contract
├── artifacts/               # Generated receipts & bundles
└── requirements.txt         # Python dependencies
```

---

##  API Reference

### Create Invoice
```http
POST /api/invoices
Content-Type: application/json

{
  "amount": "10.00",
  "memo": "Order #123",
  "expiresAt": "2026-02-01T00:00:00Z"
}
```

### Get Invoice
```http
GET /api/invoices/{id}
```

### Check Status
```http
GET /api/invoices/{id}/status
```

### Get Receipt
```http
GET /api/invoices/{id}/receipt
```

### Health Check
```http
GET /health
```

---

##  Security Notes

- **Never commit `.env` files** - they contain private keys
- **Use a dedicated anchor wallet** with minimal FLR for gas
- **Validate all inputs** - the backend validates amounts and addresses
- **CORS is configured** for localhost by default; update `WEB_ORIGIN` for production

---

## 🛠 Configuration Reference

### Backend (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `FLARE_RPC_URL` | ✅ | Flare RPC endpoint |
| `CHAIN_ID` | ✅ | 14 (mainnet) or 114 (Coston2) |
| `USDT0_ADDRESS` | ✅ | USDT0 token contract |
| `MERCHANT_ADDRESS` | ✅ | Your payment receiving wallet |
| `DATABASE_URL` | ❌ | DB connection (default: SQLite) |
| `ANCHOR_CONTRACT_ADDR` | ❌ | EvidenceAnchor contract |
| `ANCHOR_PRIVATE_KEY` | ❌ | Key for anchor transactions |
| `CONFIRMATIONS` | ❌ | Block confirmations (default: 3) |
| `POLL_INTERVAL_SECONDS` | ❌ | Worker poll rate (default: 10) |

### Frontend (`apps/proofpay/.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | Backend API URL |
| `NEXT_PUBLIC_USDT0_ADDRESS` | USDT0 contract for wallet |
| `NEXT_PUBLIC_CHAIN_ID` | Chain ID for wallet |
| `NEXT_PUBLIC_FLARE_RPC_URL` | RPC for wallet connection |

---

## Current Limitations (MVP)

- **USDT0 only** - no other tokens or native FLR
- **Single merchant** - one address via env var
- **Exact amount matching** - payer must send exact amount
- **Basic UI** - functional but minimal styling
- **No authentication** - merchant page is public

---

## 🚧 Possible Roadmap

### v1.1 - Enhanced Features
- [ ] QR codes for mobile payments
- [ ] Webhook notifications
- [ ] Email receipts
- [ ] Multi-token support (FXRP, FLR)

### v1.2 - Enterprise
- [ ] Multi-merchant accounts
- [ ] API authentication
- [ ] Accounting export (CSV/JSON)
- [ ] Dashboard analytics

### v1.3 - Compliance
- [ ] Additional ISO 20022 message types
- [ ] Audit trail and verification portal

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

##  License

MIT License - see LICENSE file for details.

---

##  Resources

- [Flare documentation](https://dev.flare.network/)
- [ProofRails](https://github.com/proofrails/Middleware-ISO20022-v1.3)
- [USDT0 on Flare](https://flarescan.com/token/0xe7cd86e13AC4309349F30B3435a9d337750fC82D)
