"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

type Invoice = {
  id: string;
  amount: string;
  memo?: string | null;
  currency: string;
  status: string;
  merchantAddress: string;
  created_at: string;
  expires_at: string;
};

export default function MerchantPage() {
  const [amount, setAmount] = useState("");
  const [memo, setMemo] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [items, setItems] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadInvoices() {
    const res = await apiFetch(`/api/invoices?limit=20`, {
      cache: "no-store"
    });
    const data = await res.json();
    setItems(data.items || []);
  }

  useEffect(() => {
    loadInvoices();
  }, []);

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/invoices`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount,
          memo: memo || null,
          expiresAt: expiresAt
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create invoice");
      }
      setAmount("");
      setMemo("");
      setExpiresAt("");
      await loadInvoices();
    } catch (e: any) {
      setError(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="card">
        <h3>Create Invoice</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label className="label">Amount (USDT0)</label>
            <input
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="10.50"
              type="number"
              step="0.01"
            />
          </div>
          <div>
            <label className="label">Expiry Date/Time</label>
            <input
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              placeholder="2026-01-26T18:00:00Z"
              type="datetime-local"
            />
          </div>
          <div>
            <label className="label">Memo (optional)</label>
            <input
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder="Payment for services..."
            />
          </div>
        </div>
        <div style={{ marginTop: 20 }}>
          <button className="btn btn-primary" onClick={submit} disabled={loading} style={{ width: "100%" }}>
            {loading ? "Creating..." : "Create Invoice"}
          </button>
          {error && <div style={{ color: "#f87171", marginTop: 12, fontSize: 14 }}>{error}</div>}
        </div>
      </div>

      <div className="card">
        <h3>Recent Invoices</h3>
        {items.length === 0 && <div className="muted">No invoices yet. Create one above.</div>}
        {items.map((inv) => (
          <div key={inv.id} style={{ padding: "14px 0", borderBottom: "1px solid rgba(148,163,184,0.15)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Link href={`/invoice/${inv.id}`} style={{ fontWeight: 500 }}>
                {inv.id.slice(0, 8)}...
              </Link>
              <span className="pill" style={{
                background: inv.status === "PAID" ? "rgba(34,197,94,0.15)" : "rgba(251,191,36,0.15)",
                color: inv.status === "PAID" ? "#4ade80" : "#fbbf24",
                borderColor: inv.status === "PAID" ? "rgba(34,197,94,0.3)" : "rgba(251,191,36,0.3)"
              }}>
                {inv.status}
              </span>
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              {inv.amount} {inv.currency} · expires {new Date(inv.expires_at).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
