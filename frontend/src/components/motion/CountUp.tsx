import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { formatNumber } from "../../format.ts";
import { COUNT } from "../../motion.ts";

/** A number that counts up from 0 when it appears or changes (instant with reduce motion). */
export default function CountUp({ value, digits = 0 }: { value: number; digits?: number }) {
  const node = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const element = node.current;
    if (!element) return;
    if (reduce) {
      element.textContent = formatNumber(value, digits);
      return;
    }
    const controls = animate(0, value, {
      ...COUNT,
      onUpdate: (latest) => {
        element.textContent = formatNumber(latest, digits);
      },
    });
    return () => controls.stop();
  }, [value, digits, reduce]);

  return (
    <>
      {/* Screen readers get the final value once, not every animation frame. */}
      <span ref={node} aria-hidden>
        {formatNumber(value, digits)}
      </span>
      <span className="sr-only">{formatNumber(value, digits)}</span>
    </>
  );
}
