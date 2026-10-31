import { motion } from "motion/react";
import type { ReactNode } from "react";
import { fadeUp, stagger } from "../../motion.ts";

/** Children wrapped in <StaggerItem> fade in one after another. */
export function Stagger({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <motion.div className={className} variants={stagger} initial="hidden" animate="show">
      {children}
    </motion.div>
  );
}

export function StaggerItem({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <motion.div className={className} variants={fadeUp}>
      {children}
    </motion.div>
  );
}
