import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { formatNumber } from "../../format.ts";
import { COUNT } from "../../motion.ts";

/**
 * A number that rolls from its previous value to the new one (e.g. yesterday's recovery to
 * today's), so the change itself is visible. First render shows the value as is: nothing
 * counts up from zero on page load. Instant with reduce motion.
 */
export default function CountUp({ value, digits = 0 }: { value: number; digits?: number }) {
  const node = useRef<HTMLSpanElement>(null);
  const previous = useRef(value);
  const reduce = useReducedMotion();

  useEffect(() => {
    const element = node.current;
    const from = previous.current;
    previous.current = value;
    if (!element) return;
    if (reduce || from === value) {
      element.textContent = formatNumber(value, digits);
      return;
    }
    const controls = animate(from, value, {
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
