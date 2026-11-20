"use client";
import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

/** Shared glass card: persists across /login ↔ /register and morphs its size with a layout animation. */
export function AuthCard({ children }: { children: ReactNode }) {
  const path = usePathname();
  const reduce = useReducedMotion();
  return (
    <motion.div
      layout={!reduce}
      layoutId="auth-card"
      transition={{ layout: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } }}
      className="relative w-full max-w-[440px] rounded-[28px] border border-white/70 bg-white/85 p-6 shadow-[0_30px_80px_-30px_rgba(60,40,160,0.35)] backdrop-blur-xl sm:p-9"
    >
      <motion.div
        key={path}
        layout="position"
        initial={reduce ? false : { opacity: 0, x: 24 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        {children}
      </motion.div>
    </motion.div>
  );
}
