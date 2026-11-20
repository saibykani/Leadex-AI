"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown, HelpCircle, MessageSquareQuote, ShieldCheck, Sparkles, Star, Users
} from "lucide-react";
import { serif } from "./fonts";


const FAQS = [
  {
    q: "How does Leadex ensure strict tenant data isolation?",
    a: "Leadex implements tenant isolation in depth. Every tenant-owned row in PostgreSQL carries an organization_id. At the application layer, FastAPI scopes all queries through a TenantContext dependency. At the database layer, PostgreSQL Row-Level Security (RLS) is enforced via the app.current_org session setting with FORCE ROW LEVEL SECURITY. The application database user cannot bypass RLS even if an endpoint query omitted a filter.",
  },
  {
    q: "How does OutreachGate prevent legal compliance fines?",
    a: "OutreachGate acts as a mandatory gateway before any telephone call, email, or WhatsApp message can leave the platform. It verifies the lawful basis, checks local timezone calling windows (e.g. 09:00 - 20:00), scrubs numbers against central registries (such as TRAI NCPR in India and US National DNC), and mandates AI disclosure in the first 5 seconds of a call. If consent or eligibility is uncertain, the system defaults to BLOCK.",
  },
  {
    q: "Can we run Leadex AI locally without paying per-token API costs?",
    a: "Yes. Leadex is designed open-source first. The stack includes Ollama for local LLM reasoning, and Twilio's speech recognition and voice for phone calls today (a fully self-hosted speech pipeline is on the roadmap). When running locally or on your own GPU VM, you pay zero per-token API costs to external vendors. Paid cloud model providers are strictly opt-in.",
  },
  {
    q: "How does the Instant Website Studio generate previews without manual coding?",
    a: "Website Studio pulls verified business metadata (business name, category, verified phone, address, customer reviews, and photos) from the discovery engine and compiles it into clean, responsive HTML previews using 11 pre-evaluated industry templates. Previews are hosted immediately on SeaweedFS S3 storage and shared via preview links.",
  },
  {
    q: "How does the Referral Marketplace track and settle commissions?",
    a: "When a customer requirement is logged (e.g. a high-end interior renovation), Leadex matches the brief to verified architects, builders, or brokers in that locality. The platform logs the introduction, generates a commission agreement with clear milestone percentages, and records settlement transactions upon project contract signing.",
  },
  {
    q: "What is the difference between simulated and production mode?",
    a: "In local development and staging environments (when APP_ENV is not production), all outbound integrations—including telephony trunks, email delivery, and WhatsApp Business API—are locked into simulated mode. They return mock responses clearly labeled simulated=true so your team can test end-to-end workflows safely without dialing real people or incurring costs.",
  },
];

export function TestimonialsAndFaq() {
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-white via-[#f8faff] to-white py-24 sm:py-32">
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        {/* FAQ Section */}
        <div className="mx-auto max-w-4xl">
          <div className="text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-1 text-xs font-semibold text-slate-700">
              <HelpCircle className="h-3.5 w-3.5 text-blue-600" /> Frequently Asked Questions
            </div>
            <h3 className={`${serif.className} mt-3 text-3xl font-semibold text-slate-900 sm:text-4xl`}>
              Everything you need to know about the platform.
            </h3>
          </div>

          <div className="mt-10 space-y-3">
            {FAQS.map((faq, i) => {
              const isOpen = openFaq === i;
              return (
                <div
                  key={faq.q}
                  className="rounded-2xl border border-slate-200/90 bg-white overflow-hidden shadow-sm transition-all"
                >
                  <button
                    onClick={() => setOpenFaq(isOpen ? null : i)}
                    className="flex w-full items-center justify-between p-5 text-left font-bold text-slate-900 text-sm sm:text-base hover:text-blue-600 transition-colors"
                  >
                    <span>{faq.q}</span>
                    <ChevronDown
                      className={`h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 ${
                        isOpen ? "rotate-180 text-blue-600" : ""
                      }`}
                    />
                  </button>

                  <AnimatePresence>
                    {isOpen && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.25 }}
                        className="px-5 pb-5 text-xs sm:text-sm leading-relaxed text-slate-600 border-t border-slate-100 pt-3"
                      >
                        {faq.a}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

