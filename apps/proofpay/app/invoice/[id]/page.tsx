"use client";

import { useEffect, useState } from "react";
import { useAccount, useConnect, usePublicClient, useWriteContract, useChainId, useSwitchChain } from "wagmi";
import { erc20Abi, parseUnits, isAddress } from "viem";
import { USDT0_ADDRESS } from "../../../lib/config";
import { apiFetch } from "../../../lib/api";

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

type Receipt = {
  id: string;
  iso_xml?: string | null;
  iso_json?: string | null;
  evidence_bundle_hash?: string | null;
  anchor_tx_hash?: string | null;
  verification_ref_or_url?: string | null;
};

export default function InvoicePage({ params }: { params: { id: string } }) {
  const { address, isConnected } = useAccount();
  const { connect, connectors, isPending } = useConnect();
  const wagmiChainId = useChainId();
  const { switchChainAsync, isPending: isSwitching } = useSwitchChain();
  const publicClient = usePublicClient();
  const { writeContractAsync } = useWriteContract();

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [decimals, setDecimals] = useState<number>(6);
  const [status, setStatus] = useState<string>("ISSUED");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tokenAddress, setTokenAddress] = useState<string>(USDT0_ADDRESS);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [expectedChainId, setExpectedChainId] = useState<number | null>(null);
  const [walletChainId, setWalletChainId] = useState<number | null>(null);

  // Get actual wallet chain ID from provider
  useEffect(() => {
    async function getWalletChain() {
      if (typeof window === "undefined" || !(window as any).ethereum) return;
      try {
        const chainHex = await (window as any).ethereum.request({ method: "eth_chainId" });
        setWalletChainId(parseInt(chainHex, 16));
      } catch {
        // ignore
      }
    }
    getWalletChain();

    // Listen for chain changes
    if (typeof window !== "undefined" && (window as any).ethereum) {
      const handleChainChanged = (chainHex: string) => {
        setWalletChainId(parseInt(chainHex, 16));
      };
      (window as any).ethereum.on("chainChanged", handleChainChanged);
      return () => {
        (window as any).ethereum.removeListener("chainChanged", handleChainChanged);
      };
    }
  }, [isConnected]);

  // Use wallet chain ID if available, otherwise fall back to wagmi
  const chainId = walletChainId ?? wagmiChainId;

  async function loadInvoice() {
    const res = await apiFetch(`/api/invoices/${params.id}`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    setInvoice(data);
    setStatus(data.status);
  }

  async function loadReceipt() {
    const res = await apiFetch(`/api/invoices/${params.id}/receipt`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    setReceipt(data);
  }

  useEffect(() => {
    loadInvoice();
  }, [params.id]);

  useEffect(() => {
    async function loadConfig() {
      try {
        const res = await apiFetch("/api/config", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.usdt0Address) {
          setTokenAddress(data.usdt0Address);
        }
        if (data.chainId) {
          const parsed = Number(data.chainId);
          if (!Number.isNaN(parsed)) {
            setExpectedChainId(parsed);
          }
        }
      } catch {
        // ignore config load errors
      }
    }
    loadConfig();
  }, []);

  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await apiFetch(`/api/invoices/${params.id}/status`, {
        cache: "no-store"
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data.status);
        if (data.status === "PAID") {
          loadReceipt();
        }
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [params.id]);

  useEffect(() => {
    async function fetchDecimals() {
      if (!tokenAddress || !publicClient) return;
      try {
        const dec = await publicClient.readContract({
          address: tokenAddress as `0x${string}`,
          abi: erc20Abi,
          functionName: "decimals"
        });
        setDecimals(Number(dec));
      } catch {
        setDecimals(6);
      }
    }
    fetchDecimals();
  }, [publicClient, tokenAddress]);

  async function handlePay() {
    if (!invoice) return;
    if (!tokenAddress) {
      setError("USDT0 token address is not configured");
      return;
    }
    if (!invoice.merchantAddress) {
      setError("Merchant address missing on invoice");
      return;
    }
    if (!isAddress(tokenAddress)) {
      setError("USDT0 token address is invalid");
      return;
    }
    if (!isAddress(invoice.merchantAddress)) {
      setError("Merchant address is invalid");
      return;
    }

    // BLOCK if wrong network - user must click "Switch to Flare" first
    if (expectedChainId && chainId !== expectedChainId) {
      setError(`Wrong network! Please switch to Flare (chain ${expectedChainId}) first.`);
      return;
    }

    setBusy(true);
    setError(null);
    try {
      let payer = address;
      if (!payer && typeof window !== "undefined") {
        try {
          const accounts = await (window as any).ethereum?.request({
            method: "eth_accounts"
          });
          payer = accounts?.[0];
        } catch {
          // ignore
        }
      }
      if (!payer) {
        throw new Error("Wallet address not available");
      }
      const amountUnits = parseUnits(invoice.amount, decimals);

      // Direct ERC20 transfer call via wallet
      const txHash = await writeContractAsync({
        address: tokenAddress as `0x${string}`,
        abi: erc20Abi,
        functionName: "transfer",
        args: [invoice.merchantAddress as `0x${string}`, amountUnits]
      });
      
      // Wait for confirmation
      if (publicClient) {
        await publicClient.waitForTransactionReceipt({ hash: txHash });
      }
      
      setStatus("PAID");
    } catch (e: any) {
      setError(e.message || "Payment failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleConnect() {
    setConnectError(null);
    try {
      const connector = connectors?.[0];
      if (!connector) {
        throw new Error("No wallet connector available");
      }
      await connect({ connector });
    } catch (e: any) {
      setConnectError(e.message || "Wallet connection failed");
    }
  }

  async function handleSwitch() {
    setConnectError(null);
    setError(null);
    try {
      if (!expectedChainId) {
        throw new Error("Chain ID not available");
      }
      
      const ethereum = typeof window !== "undefined" ? (window as any).ethereum : null;
      if (!ethereum) {
        throw new Error("No wallet found");
      }

      const chainHex = `0x${expectedChainId.toString(16)}`;
      
      try {
        // First try to switch
        await ethereum.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: chainHex }]
        });
      } catch (switchError: any) {
        // If chain doesn't exist, add it (error code 4902)
        if (switchError.code === 4902 || switchError.message?.includes("Unrecognized chain")) {
          await ethereum.request({
            method: "wallet_addEthereumChain",
            params: [{
              chainId: chainHex,
              chainName: expectedChainId === 14 ? "Flare Mainnet" : "Coston2 Testnet",
              nativeCurrency: { name: "Flare", symbol: "FLR", decimals: 18 },
              rpcUrls: [expectedChainId === 14 
                ? "https://flare-api.flare.network/ext/C/rpc" 
                : "https://coston2-api.flare.network/ext/C/rpc"],
              blockExplorerUrls: [expectedChainId === 14 
                ? "https://flarescan.com" 
                : "https://coston2.testnet.flarescan.com"]
            }]
          });
        } else {
          throw switchError;
        }
      }
    } catch (e: any) {
      setConnectError(e.message || "Network switch failed");
    }
  }

  function copy(text?: string | null) {
    if (!text) return;
    navigator.clipboard.writeText(text);
  }

  if (!invoice) {
    return <div className="card">Loading invoice...</div>;
  }

  const wrongNetwork = isConnected && expectedChainId && chainId !== expectedChainId;

  return (
    <div>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <h3 style={{ margin: 0 }}>Invoice</h3>
          <div className="pill" style={isConnected 
            ? { background: "rgba(34,197,94,0.15)", color: "#4ade80", borderColor: "rgba(34,197,94,0.3)" }
            : { background: "rgba(251,191,36,0.15)", color: "#fbbf24", borderColor: "rgba(251,191,36,0.3)" }
          }>
            {isConnected ? "✓ Connected" : "Not connected"}
          </div>
        </div>

        <div style={{ fontSize: 36, fontWeight: 700, marginBottom: 8 }}>
          {invoice.amount} <span style={{ color: "#38bdf8" }}>{invoice.currency}</span>
        </div>

        {invoice.memo && (
          <div style={{ marginBottom: 16, padding: "12px 16px", background: "rgba(56,189,248,0.1)", borderRadius: 10, borderLeft: "3px solid #38bdf8" }}>
            {invoice.memo}
          </div>
        )}

        <div style={{ display: "grid", gap: 8, fontSize: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="muted">Status</span>
            <strong style={{ color: status === "PAID" ? "#4ade80" : "#fbbf24" }}>{status}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="muted">Expires</span>
            <span>{new Date(invoice.expires_at).toLocaleString()}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="muted">Merchant</span>
            <span style={{ fontFamily: "monospace", fontSize: 12 }}>{invoice.merchantAddress.slice(0,10)}...{invoice.merchantAddress.slice(-8)}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="muted">Required Network</span>
            <span>{expectedChainId === 14 ? "Flare Mainnet" : expectedChainId === 114 ? "Coston2" : `Chain ${expectedChainId}`}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="muted">Your Network</span>
            <span style={{ color: wrongNetwork ? "#f87171" : "#4ade80" }}>
              {chainId === 1 ? "Ethereum Mainnet" : chainId === 14 ? "Flare Mainnet ✓" : chainId === 114 ? "Coston2 ✓" : chainId ? `Chain ${chainId}` : "Not connected"}
            </span>
          </div>
        </div>

        {wrongNetwork && (
          <div style={{ marginTop: 16, padding: "12px 16px", background: "rgba(239,68,68,0.15)", borderRadius: 10, border: "1px solid rgba(239,68,68,0.3)", color: "#f87171" }}>
            ⚠️ Wrong network! You're on {chainId === 1 ? "Ethereum" : `Chain ${chainId}`}. Switch to Flare to pay.
          </div>
        )}

        <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 12 }}>
          {!isConnected && (
            <button className="btn btn-secondary" onClick={handleConnect} disabled={isPending || busy} style={{ width: "100%" }}>
              {isPending ? "Connecting..." : "Connect Wallet"}
            </button>
          )}
          {wrongNetwork && (
            <button className="btn btn-primary" onClick={handleSwitch} disabled={isSwitching || busy} style={{ width: "100%", background: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)" }}>
              {isSwitching ? "Switching..." : "Switch to Flare Network"}
            </button>
          )}
          {isConnected && !wrongNetwork && status === "ISSUED" && (
            <button className="btn btn-primary" onClick={handlePay} disabled={busy} style={{ width: "100%" }}>
              {busy ? "Processing..." : "Pay with USDT0"}
            </button>
          )}
          {status !== "ISSUED" && (
            <div className="pill" style={{ background: "rgba(34,197,94,0.2)", color: "#4ade80", borderColor: "rgba(34,197,94,0.4)", justifyContent: "center", padding: "12px 20px" }}>
              ✓ Payment complete
            </div>
          )}
          {address && <div className="muted" style={{ textAlign: "center", fontSize: 12 }}>Wallet: {address}</div>}
          {connectError && <div style={{ color: "#f87171", textAlign: "center", fontSize: 14 }}>{connectError}</div>}
          {error && <div style={{ color: "#f87171", textAlign: "center", fontSize: 14 }}>{error}</div>}
        </div>
      </div>

      {status === "PAID" && receipt && (
        <div className="card">
          <h3>Receipt</h3>
          <div className="muted">Verification: {receipt.verification_ref_or_url || "pending"}</div>
          {receipt.iso_xml && (
            <div style={{ marginTop: 12 }}>
              <button className="btn" onClick={() => copy(receipt.iso_xml)}>
                Copy XML
              </button>
              <pre style={{ whiteSpace: "pre-wrap" }}>{receipt.iso_xml}</pre>
            </div>
          )}
          {receipt.iso_json && (
            <div style={{ marginTop: 12 }}>
              <button className="btn" onClick={() => copy(receipt.iso_json || "")}>
                Copy JSON
              </button>
              <pre style={{ whiteSpace: "pre-wrap" }}>{receipt.iso_json}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
