"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion, useAnimationControls, useReducedMotion } from "framer-motion";
import { auth } from "@/lib/api";
import { AuthAlert, AuthButton, Field, PasswordField, StrengthMeter, Stagger, StaggerItem, SuccessBurst } from "@/components/auth/fields";

const schema = z.object({
  full_name: z.string().min(1, "Required").max(200),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(10, "At least 10 characters")
    .regex(/[a-zA-Z]/, "Must contain a letter").regex(/\d/, "Must contain a digit"),
  organization_name: z.string().min(2, "At least 2 characters").max(200),
  country_code: z.string().length(2, "Use a 2-letter ISO code").optional().or(z.literal("")),
});

export default function RegisterPage() {
  const router = useRouter();
  const reduce = useReducedMotion();
  const shake = useAnimationControls();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const pw = watch("password") ?? "";

  const doShake = () => { if (!reduce) void shake.start({ x: [0, -12, 12, -8, 8, -4, 0], transition: { duration: 0.45 } }); };

  const onSubmit = handleSubmit(async (v) => {
    setError(null);
    try {
      await auth.register({ ...v, country_code: v.country_code || undefined });
      setDone(true);
      setTimeout(() => router.push("/dashboard"), reduce ? 0 : 900);
    } catch (e) { setError((e as Error).message); doShake(); }
  }, doShake);

  return (
    <motion.form onSubmit={onSubmit} animate={shake} noValidate>
      <SuccessBurst show={done} label="Workspace ready" />
      <Stagger className="space-y-4">
        <StaggerItem className="mb-2">
          <h1 className="bg-gradient-to-r from-[#ff375f] via-[#bf5af2] to-[#5e5ce6] bg-clip-text text-[32px] font-semibold tracking-tight text-transparent">Create your account</h1>
          <p className="mt-2 text-[15px] text-neutral-600">Start your workspace in under a minute.</p>
        </StaggerItem>
        <AuthAlert message={error} />
        <StaggerItem><Field id="full_name" label="Full name" autoComplete="name" {...register("full_name")} error={errors.full_name?.message} /></StaggerItem>
        <StaggerItem><Field id="email" label="Work email" type="email" autoComplete="email" {...register("email")} error={errors.email?.message} /></StaggerItem>
        <StaggerItem>
          <PasswordField id="password" label="Password" autoComplete="new-password" {...register("password")} error={errors.password?.message} />
          <StrengthMeter value={pw} />
        </StaggerItem>
        <StaggerItem><Field id="org" label="Organization" autoComplete="organization" {...register("organization_name")} error={errors.organization_name?.message} /></StaggerItem>
        <StaggerItem><Field id="cc" label="Country (ISO code, optional)" maxLength={2} hint="e.g. IN, US, GB" {...register("country_code")} error={errors.country_code?.message} /></StaggerItem>
        <StaggerItem className="pt-1"><AuthButton type="submit" loading={isSubmitting} success={done}>Create account</AuthButton></StaggerItem>
        <StaggerItem><p className="text-center text-sm text-neutral-600">Have an account? <Link href="/login" className="font-semibold text-[#0a6fd6] underline-offset-4 hover:underline">Sign in</Link></p></StaggerItem>
        <StaggerItem><p className="text-center text-xs text-neutral-500">By creating an account you agree to the <Link href="/terms" className="underline">Terms</Link> and <Link href="/privacy" className="underline">Privacy Policy</Link>.</p></StaggerItem>
      </Stagger>
    </motion.form>
  );
}
