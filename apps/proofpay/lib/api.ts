import { API_BASE_URL } from "./config";

const FALLBACKS = ["http://127.0.0.1:8010", "http://127.0.0.1:8000"];
let lastGoodBase: string | null = null;

export async function apiFetch(path: string, options: RequestInit = {}) {
  const candidates = [
    lastGoodBase,
    API_BASE_URL,
    ...FALLBACKS
  ].filter(Boolean) as string[];

  let lastError: unknown = null;
  for (const base of candidates) {
    try {
      const res = await fetch(`${base}${path}`, options);
      if (!res.ok && res.status >= 500) {
        lastError = new Error(`server_error:${res.status}`);
        continue;
      }
      lastGoodBase = base;
      return res;
    } catch (err) {
      lastError = err;
      continue;
    }
  }
  throw lastError || new Error("failed_to_fetch");
}
