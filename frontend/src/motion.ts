// Motion tokens (design.md): short, ease-out, no overshoot. Reduced motion is handled
// globally by <MotionConfig reducedMotion="user"> in main.tsx.
import type { Transition } from "motion/react";

export const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

export const FAST: Transition = { duration: 0.15, ease: EASE_OUT };
export const BASE: Transition = { duration: 0.22, ease: EASE_OUT };
export const COUNT: Transition = { duration: 0.8, ease: EASE_OUT };
