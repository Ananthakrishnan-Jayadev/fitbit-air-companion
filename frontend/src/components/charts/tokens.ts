import { useEffect, useState } from "react";

const NAMES = [
  "surface-1",
  "ink-1",
  "ink-2",
  "ink-muted",
  "grid",
  "axis",
  "series-1",
  "series-1-wash",
  "seq-250",
  "seq-350",
  "seq-450",
  "seq-600",
  "good",
  "warning",
  "serious",
  "critical",
] as const;

export type TokenName = (typeof NAMES)[number];
export type ChartTokens = Record<TokenName, string>;

function readTokens(): ChartTokens {
  const style = getComputedStyle(document.documentElement);
  const entries = NAMES.map((name) => [name, style.getPropertyValue(`--${name}`).trim()]);
  return Object.fromEntries(entries) as ChartTokens;
}

/** CSS chart tokens, re-read when the OS switches between light and dark. */
export function useChartTokens(): ChartTokens {
  const [tokens, setTokens] = useState<ChartTokens>(readTokens);
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setTokens(readTokens());
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return tokens;
}
