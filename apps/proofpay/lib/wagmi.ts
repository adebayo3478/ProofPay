import { http, defineChain } from "viem";
import { createConfig } from "wagmi";
import { injected } from "wagmi/connectors";

const chainId = Number(process.env.NEXT_PUBLIC_CHAIN_ID || "14");
const rpcUrl =
  process.env.NEXT_PUBLIC_FLARE_RPC_URL ||
  "https://flare-api.flare.network/ext/C/rpc";

const proofpayChain = defineChain({
  id: Number.isNaN(chainId) ? 114 : chainId,
  name: chainId === 114 ? "Coston2" : "Flare Mainnet",
  nativeCurrency: { name: "Flare", symbol: "FLR", decimals: 18 },
  rpcUrls: {
    default: { http: [rpcUrl] }
  }
});

export const wagmiConfig = createConfig({
  chains: [proofpayChain],
  connectors: [injected()],
  transports: {
    [proofpayChain.id]: http(rpcUrl)
  }
});
