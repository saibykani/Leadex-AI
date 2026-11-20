import { AuthArt } from "@/components/auth/AuthArt";
import { AuthCard } from "@/components/auth/AuthCard";
import { DomainBrand } from "@/components/auth/DomainBrand";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen overflow-x-hidden bg-[#f6f5ff] lg:grid lg:grid-cols-[1.05fr_1fr]">
      <section className="sticky top-0 hidden h-screen lg:block" aria-label="Leadex AI highlights">
        <AuthArt />
      </section>
      <div className="lg:hidden">
        <AuthArt compact />
      </div>
      <section className="relative isolate flex items-start justify-center px-4 pb-12 lg:items-center lg:px-10 lg:py-12">
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute -right-24 top-10 h-72 w-72 rounded-full bg-[#bf5af2]/20 blur-3xl" />
          <div className="absolute -left-16 bottom-10 h-72 w-72 rounded-full bg-[#64d2ff]/25 blur-3xl" />
          <div className="absolute bottom-1/3 right-1/4 h-56 w-56 rounded-full bg-[#ff9f0a]/15 blur-3xl" />
        </div>
        <div className="-mt-12 flex w-full justify-center lg:mt-0">
          <AuthCard><DomainBrand />{children}</AuthCard>
        </div>
      </section>
    </main>
  );
}
