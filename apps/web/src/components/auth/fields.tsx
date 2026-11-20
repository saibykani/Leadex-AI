"use client";
import { forwardRef, useId, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type PointerEvent, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion, type Variants } from "framer-motion";
import { AlertCircle, ArrowRight, Check, Eye, EyeOff, Loader2 } from "lucide-react";
import s from "./auth.module.css";

const EASE = [0.22, 1, 0.36, 1] as const;

const container: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } } };
const item: Variants = {
  hidden: { opacity: 0, y: 18, filter: "blur(4px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.55, ease: EASE } },
};

/** Staggered entrance container; wrap children in <StaggerItem>. */
export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} variants={container} initial={reduce ? false : "hidden"} animate="show">
      {children}
    </motion.div>
  );
}
export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} variants={item}>{children}</motion.div>;
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string; trailing?: ReactNode };

/** Input with floating label, animated gradient focus ring and animated error text. */
export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, error, hint, trailing, id, className, onFocus, onBlur, ...p }, ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  const [focus, setFocus] = useState(false);
  const msgId = `${fid}-msg`;
  return (
    <div className={className}>
      <div className="relative">
        <motion.div
          aria-hidden
          className={`pointer-events-none absolute -inset-[2px] rounded-[16px] ${error ? "bg-[#ff375f]" : s.ring}`}
          initial={false}
          animate={{ opacity: focus || error ? 1 : 0, scale: focus ? 1 : 0.98 }}
          transition={{ duration: 0.25 }}
        />
        <div className="relative rounded-[14px] bg-white">
          <input
            ref={ref}
            id={fid}
            placeholder=" "
            aria-invalid={!!error}
            aria-describedby={error || hint ? msgId : undefined}
            onFocus={(e) => { setFocus(true); onFocus?.(e); }}
            onBlur={(e) => { setFocus(false); onBlur?.(e); }}
            {...p}
            className={`peer h-14 w-full rounded-[14px] border bg-white px-4 pb-1.5 pt-5 text-[15px] text-neutral-900 outline-none transition-colors ${trailing ? "pr-12" : ""} ${error ? "border-transparent" : focus ? "border-transparent" : "border-neutral-200 hover:border-neutral-300"}`}
          />
          <label
            htmlFor={fid}
            className="pointer-events-none absolute left-4 top-1/2 origin-left -translate-y-[130%] scale-[0.8] text-[15px] font-medium text-neutral-600 transition-transform duration-200 ease-out peer-placeholder-shown:-translate-y-1/2 peer-placeholder-shown:scale-100 peer-focus:-translate-y-[130%] peer-focus:scale-[0.8] peer-focus:text-[#5e5ce6]"
          >
            {label}
          </label>
          {trailing && <div className="absolute right-2 top-1/2 -translate-y-1/2">{trailing}</div>}
        </div>
      </div>
      <AnimatePresence initial={false}>
        {(error || hint) && (
          <motion.p
            key={error ?? hint}
            id={msgId}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className={`mt-1.5 flex items-center gap-1 text-[13px] ${error ? "text-[#d70015]" : "text-neutral-600"}`}
          >
            {error && <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden />}{error ?? hint}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
});

/** Password field with an animated show/hide icon morph. */
export const PasswordField = forwardRef<HTMLInputElement, Omit<FieldProps, "type" | "trailing">>(function PasswordField(props, ref) {
  const [show, setShow] = useState(false);
  return (
    <Field
      ref={ref}
      {...props}
      type={show ? "text" : "password"}
      trailing={
        <motion.button
          type="button"
          onClick={() => setShow((v) => !v)}
          aria-label={show ? "Hide password" : "Show password"}
          aria-pressed={show}
          whileTap={{ scale: 0.8 }}
          whileHover={{ scale: 1.1 }}
          className="grid h-10 w-10 place-items-center rounded-full text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#5e5ce6]"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={show ? "off" : "on"}
              initial={{ rotate: -90, scale: 0.4, opacity: 0 }}
              animate={{ rotate: 0, scale: 1, opacity: 1 }}
              exit={{ rotate: 90, scale: 0.4, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              {show ? <EyeOff className="h-[18px] w-[18px]" /> : <Eye className="h-[18px] w-[18px]" />}
            </motion.span>
          </AnimatePresence>
        </motion.button>
      }
    />
  );
});

const LEVELS = [
  { label: "", color: "#ff375f" },
  { label: "Weak", color: "#ff375f" },
  { label: "Fair", color: "#ff9f0a" },
  { label: "Good", color: "#0a84ff" },
  { label: "Strong", color: "#30d158" },
];
export function passwordScore(v: string) {
  if (!v) return 0;
  if (v.length < 10) return 1;
  let n = 1;
  if (/[a-zA-Z]/.test(v) && /\d/.test(v)) n++;
  if (/[A-Z]/.test(v) && /[a-z]/.test(v)) n++;
  if (/[^a-zA-Z0-9]/.test(v) || v.length >= 14) n++;
  return Math.min(n, 4);
}

/** Animated four-segment strength meter. */
export function StrengthMeter({ value }: { value: string }) {
  const score = passwordScore(value);
  const lvl = LEVELS[score];
  return (
    <div className="mt-2" aria-live="polite">
      <div className="flex gap-1.5">
        {[1, 2, 3, 4].map((k) => (
          <div key={k} className="h-1.5 flex-1 overflow-hidden rounded-full bg-neutral-200">
            <motion.div
              className="h-full origin-left rounded-full"
              initial={false}
              animate={{ scaleX: value && score >= k ? 1 : 0, backgroundColor: lvl.color }}
              transition={{ duration: 0.4, ease: EASE, delay: (k - 1) * 0.04 }}
            />
          </div>
        ))}
      </div>
      {value && <p className="mt-1 text-[12px] font-medium text-neutral-600">Strength: <span style={{ color: score >= 3 ? "#1d7a32" : undefined }}>{value.length < 10 ? "Too short" : lvl.label}</span></p>}
    </div>
  );
}

type AuthButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean; success?: boolean };

/** Gradient CTA with shimmer, press ripple and loading → success morph. */
export function AuthButton({ loading, success, children, disabled, className, onPointerDown, ...p }: AuthButtonProps) {
  const reduce = useReducedMotion();
  const [ripples, setRipples] = useState<{ id: number; x: number; y: number }[]>([]);
  const busy = loading || success;
  const down = (e: PointerEvent<HTMLButtonElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const id = Date.now();
    setRipples((rs) => [...rs, { id, x: e.clientX - r.left, y: e.clientY - r.top }]);
    setTimeout(() => setRipples((rs) => rs.filter((q) => q.id !== id)), 700);
    onPointerDown?.(e);
  };
  return (
    <motion.button
      {...(p as object)}
      disabled={disabled || busy}
      aria-busy={loading}
      onPointerDown={down}
      whileHover={reduce || disabled || busy ? undefined : { y: -2, scale: 1.01 }}
      whileTap={reduce || disabled || busy ? undefined : { scale: 0.97 }}
      className={`group relative isolate flex h-14 w-full items-center justify-center overflow-hidden rounded-full text-[16px] font-semibold text-white shadow-[0_14px_30px_-10px_rgba(94,92,230,0.7)] outline-none focus-visible:ring-4 focus-visible:ring-[#5e5ce6]/40 disabled:cursor-not-allowed ${disabled && !busy ? "opacity-60" : ""} ${className ?? ""}`}
    >
      <motion.span
        aria-hidden
        className="absolute inset-0 -z-10"
        animate={{ opacity: success ? 0 : 1 }}
        style={{ background: "linear-gradient(100deg,#0a84ff 0%,#5e5ce6 45%,#bf5af2 100%)" }}
      />
      <motion.span aria-hidden className="absolute inset-0 -z-10 bg-[#30d158]" initial={false} animate={{ opacity: success ? 1 : 0 }} />
      {!busy && <span aria-hidden className={s.shimmer} />}
      {ripples.map((r) => <span key={r.id} aria-hidden className={s.ripple} style={{ left: r.x, top: r.y }} />)}
      <AnimatePresence mode="wait" initial={false}>
        {success ? (
          <motion.span key="ok" initial={{ scale: 0, rotate: -45 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 400, damping: 15 }}>
            <Check className="h-6 w-6" strokeWidth={3} aria-label="Success" />
          </motion.span>
        ) : loading ? (
          <motion.span key="ld" initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }} className="flex items-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />Please wait
          </motion.span>
        ) : (
          <motion.span key="tx" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="flex items-center gap-2">
            {children}
            <ArrowRight className="h-[18px] w-[18px] transition-transform duration-200 group-hover:translate-x-1" aria-hidden />
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}

/** Animated error banner. */
export function AuthAlert({ message }: { message: string | null }) {
  return (
    <AnimatePresence initial={false}>
      {message && (
        <motion.div
          key={message}
          role="alert"
          initial={{ opacity: 0, y: -8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -8, scale: 0.98 }}
          className="flex items-start gap-2 rounded-2xl border border-[#ff375f]/30 bg-gradient-to-r from-[#ff375f]/10 to-[#ff9f0a]/10 px-4 py-3 text-sm text-[#b0001a]"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{message}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

const BURST = ["#0a84ff", "#5e5ce6", "#bf5af2", "#ff375f", "#ff9f0a", "#64d2ff", "#30d158", "#ffd60a"];

/** Full-card success overlay: drawn checkmark with a confetti burst. */
export function SuccessBurst({ show, label = "You're in" }: { show: boolean; label?: string }) {
  const reduce = useReducedMotion();
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="absolute -inset-6 z-20 grid place-items-center rounded-[28px] sm:-inset-9 bg-white/90 backdrop-blur-sm"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          role="status"
        >
          <div className="relative grid place-items-center">
            {!reduce && Array.from({ length: 16 }).map((_, k) => {
              const a = (k / 16) * Math.PI * 2;
              return (
                <motion.span
                  key={k}
                  className="absolute left-1/2 top-12 -ml-[5px] -mt-[5px] h-2.5 w-2.5 rounded-[3px]"
                  style={{ background: BURST[k % BURST.length] }}
                  initial={{ x: 0, y: 0, scale: 0, rotate: 0, opacity: 1 }}
                  animate={{ x: Math.cos(a) * 110, y: Math.sin(a) * 110, scale: [0, 1.2, 0.8], rotate: 220, opacity: [1, 1, 0] }}
                  transition={{ duration: 1, ease: "easeOut", delay: 0.15 }}
                />
              );
            })}
            <motion.div
              className="grid h-24 w-24 place-items-center rounded-full bg-gradient-to-br from-[#30d158] to-[#64d2ff] shadow-[0_20px_50px_-12px_rgba(48,209,88,0.7)]"
              initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 14 }}
            >
              <svg viewBox="0 0 52 52" className="h-12 w-12" aria-hidden>
                <motion.path
                  d="M14 27l8 8 16-18" fill="none" stroke="#fff" strokeWidth={5} strokeLinecap="round" strokeLinejoin="round"
                  initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.45, delay: 0.25 }}
                />
              </svg>
            </motion.div>
            <motion.p className="mt-5 text-lg font-semibold text-neutral-900" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
              {label}
            </motion.p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
