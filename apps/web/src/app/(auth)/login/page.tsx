"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AnimatePresence, motion, useAnimationControls, useReducedMotion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { api, ApiError, session } from "@/lib/api";
import { AuthAlert, AuthButton, Field, PasswordField, Stagger, StaggerItem, SuccessBurst } from "@/components/auth/fields";

const schema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Required") });
type Tokens = { access_token: string; refresh_token: string };

export default function LoginPage() {
  const router = useRouter();
  const reduce = useReducedMotion();
  const shake = useAnimationControls();
  const [error, setError] = useState<string | null>(null);
  const [needOtp, setNeedOtp] = useState(false);
  const [otp, setOtp] = useState("");
  const [done, setDone] = useState(false);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });

  const doShake = () => { if (!reduce) void shake.start({ x: [0, -12, 12, -8, 8, -4, 0], transition: { duration: 0.45 } }); };

  const onSubmit = handleSubmit(async (v) => {
    setError(null);
    try {
      const body = { email: v.email, password: v.password, ...(needOtp ? { otp_code: otp } : {}) };
      session.save(await api<Tokens>("/auth/login", { method: "POST", body: JSON.stringify(body) }));
      setDone(true);
      setTimeout(() => router.push("/dashboard"), reduce ? 0 : 900);
    } catch (e) {
      if (e instanceof ApiError && e.code === "mfa_required") { setNeedOtp(true); return; }
      setError((e as Error).message);
      doShake();
    }
  }, doShake);

  return (
    <motion.form onSubmit={onSubmit} animate={shake} noValidate>
      <SuccessBurst show={done} label="Welcome back" />
      <Stagger className="space-y-5">
        <StaggerItem>
          <h1 className="bg-gradient-to-r from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] bg-clip-text text-[32px] font-semibold tracking-tight text-transparent">
            {needOtp ? "Verify it's you" : "Welcome back"}
          </h1>
          <p className="mt-2 text-[15px] text-neutral-600">{needOtp ? "One more step to keep your workspace secure." : "Sign in to your Leadex AI workspace."}</p>
        </StaggerItem>
        <AuthAlert message={error} />
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={needOtp ? "otp" : "creds"}
            initial={reduce ? false : { opacity: 0, x: needOtp ? 30 : -30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reduce ? undefined : { opacity: 0, x: needOtp ? -30 : 30 }}
            transition={{ duration: 0.3 }}
          >
            {/* Credentials stay mounted (hidden) during MFA so the second submit re-sends them. */}
            <div className={needOtp ? "hidden" : "space-y-4"}>
              <div><Field id="email" label="Email" type="email" autoComplete="email" {...register("email")} error={errors.email?.message} /></div>
              <div><PasswordField id="password" label="Password" autoComplete="current-password" {...register("password")} error={errors.password?.message} /></div>
              <div className="-mt-1 text-right"><Link href="/forgot-password" className="text-sm font-medium text-[#0a6fd6] underline-offset-4 hover:underline">Forgot password?</Link></div>
            </div>
            {needOtp && (
              <div>
                <motion.div
                  className="mb-4 flex items-center gap-3 rounded-2xl bg-gradient-to-r from-[#5e5ce6]/10 to-[#bf5af2]/10 p-3"
                  initial={reduce ? false : { scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                >
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-[#5e5ce6] to-[#bf5af2] text-white"><ShieldCheck className="h-5 w-5" aria-hidden /></span>
                  <p className="text-sm text-neutral-700">Enter the 6-digit code from your authenticator app.</p>
                </motion.div>
                <Field
                  id="otp" label="Authenticator code" inputMode="numeric" autoComplete="one-time-code" autoFocus maxLength={8}
                  value={otp} onChange={(e) => setOtp(e.target.value.trim())}
                  className="[&_input]:tracking-[0.4em]"
                />
              </div>
            )}
          </motion.div>
        </AnimatePresence>
        <StaggerItem>
          <AuthButton type="submit" loading={isSubmitting} success={done} disabled={needOtp && otp.length < 6}>
            {needOtp ? "Verify" : "Sign in"}
          </AuthButton>
        </StaggerItem>
        <StaggerItem>
          {needOtp
            ? <button type="button" className="w-full rounded-full py-1 text-center text-sm font-medium text-neutral-600 transition-colors hover:text-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#5e5ce6]" onClick={() => { setNeedOtp(false); setOtp(""); setError(null); }}>Use a different account</button>
            : <p className="text-center text-sm text-neutral-600">No account? <Link href="/register" className="font-semibold text-[#0a6fd6] underline-offset-4 hover:underline">Create one</Link></p>}
        </StaggerItem>
      </Stagger>
    </motion.form>
  );
}
