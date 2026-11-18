import type { AnalysisResponse } from "./api";

// sirf is browser me save hota hai (localStorage); server ko kuch nahi jaata
const STORAGE_KEY = "linklens-history-v1";
const MAX_ENTRIES = 8;
const KEEP_MS = 7 * 24 * 3600 * 1000;
export const FRESH_MS = 24 * 3600 * 1000;

export interface HistoryEntry {
  keys: string[];
  input: string;
  savedAt: number;
  data: AnalysisResponse;
}

export function urlKey(raw: string): string {
  const value = raw.trim().toLowerCase();
  const withScheme = value.includes("://") ? value : `https://${value}`;
  try {
    const u = new URL(withScheme);
    return `${u.hostname.replace(/^www\./, "")}${u.pathname.replace(/\/+$/, "")}`;
  } catch {
    return value;
  }
}

export function loadHistory(): HistoryEntry[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    const cutoff = Date.now() - KEEP_MS;
    return parsed.filter((e) => e?.data?.success && Array.isArray(e.keys) && e.savedAt > cutoff);
  } catch {
    return [];
  }
}

function persist(entries: HistoryEntry[]): HistoryEntry[] {
  // quota bhar jaye to purane entries hata ke dobara try karo
  for (let list = entries; list.length; list = list.slice(0, -1)) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
      return list;
    } catch {
      /* next iteration me chhoti list */
    }
  }
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage band hai */
  }
  return [];
}

export function saveToHistory(input: string, data: AnalysisResponse): HistoryEntry[] {
  const keys = [...new Set([urlKey(input), urlKey(data.website)])];
  const rest = loadHistory().filter((e) => !e.keys.some((k) => keys.includes(k)));
  return persist([{ keys, input: input.trim(), savedAt: Date.now(), data }, ...rest].slice(0, MAX_ENTRIES));
}

export function findFresh(input: string): HistoryEntry | undefined {
  const key = urlKey(input);
  return loadHistory().find((e) => e.keys.includes(key) && Date.now() - e.savedAt < FRESH_MS);
}

export function removeFromHistory(savedAt: number): HistoryEntry[] {
  return persist(loadHistory().filter((e) => e.savedAt !== savedAt));
}

export function clearHistory(): HistoryEntry[] {
  return persist([]);
}

export function timeAgo(ts: number): string {
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
