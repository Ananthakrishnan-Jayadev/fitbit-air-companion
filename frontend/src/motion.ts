// Motion tokens (design.md): short, ease-out, no overshoot. Reduced motion is handled
// globally by <MotionConfig reducedMotion="user"> in main.tsx.
import type { Transition, Variants } from "motion/react";

export const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

export const FAST: Transition = { duration: 0.15, ease: EASE_OUT };
export const BASE: Transition = { duration: 0.22, ease: EASE_OUT };
export const COUNT: Transition = { duration: 0.8, ease: EASE_OUT };

/** Fade + 8 px rise; use as `variants` on children of a `stagger` container. */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: BASE },
};

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};
