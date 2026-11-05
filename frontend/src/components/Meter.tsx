import { motion } from "motion/react";
import { COUNT } from "../motion.ts";

interface MeterProps {
  value: number | null;
  max?: number;
  color: string;
  label: string;
  /** Optional target range drawn as a bracket on the track (e.g. today's suggested strain). */
  target?: [number, number] | null;
  size?: "sm" | "md";
}

const pct = (v: number, max: number) => Math.max(0, Math.min(100, (v / max) * 100));

/**
 * Horizontal 0..max meter. Renders at its value on first paint; afterwards the fill glides
 * to each new value (switching days), so the bar shows how much it changed.
 */
export default function Meter({ value, max = 100, color, label, target, size = "sm" }: MeterProps) {
  const fill = value === null ? 0 : pct(value, max);
  return (
    <div
      className={`relative w-full bg-stone-200 dark:bg-stone-800 ${
        size === "md" ? "h-3" : "h-2"
      }`}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value ?? undefined}
    >
      {target && (
        <div
          aria-hidden
          // The target range: an ink bracket standing just proud of the bar.
          className="absolute -inset-y-1 z-10 border-2 border-stone-900 dark:border-stone-100"
          style={{ left: `${pct(target[0], max)}%`, width: `${pct(target[1], max) - pct(target[0], max)}%` }}
        />
      )}
      <motion.div
        className="relative h-full"
        style={{ backgroundColor: color }}
        initial={false}
        animate={{ width: `${fill}%` }}
        transition={COUNT}
      />
    </div>
  );
}
