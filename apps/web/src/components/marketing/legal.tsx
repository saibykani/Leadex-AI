import type { ReactNode } from "react";
import Link from "next/link";

/**
 * Legal page TEMPLATES. They describe how this software actually behaves, but they are not legal advice:
 * bracketed fields must be filled in and the text reviewed by a qualified lawyer for each country you sell in.
 */
const ENTITY = "[Company legal name]";
const ADDRESS = "[Registered address]";
const CONTACT = "[privacy@yourdomain.com]";

function LegalDoc({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-4 pb-24 pt-32 sm:px-6">
      <div className="mb-8 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
        <strong>Template, pending legal review.</strong> Fields in [brackets] must be completed and this text reviewed
        by counsel before the platform is offered to customers.
      </div>
      <h1 className="text-4xl font-semibold tracking-tight text-slate-900">{title}</h1>
      <p className="mt-2 text-sm text-slate-500">Last updated: {updated}</p>
      <div className="legal mt-10 space-y-6 text-[15px] leading-relaxed text-slate-700 [&_h2]:mt-10 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-slate-900 [&_li]:ml-5 [&_li]:list-disc [&_ul]:space-y-1.5">
        {children}
      </div>
      <p className="mt-12 text-sm text-slate-500">
        See also: <Link className="text-blue-600 underline" href="/privacy">Privacy</Link> ·{" "}
        <Link className="text-blue-600 underline" href="/terms">Terms</Link> ·{" "}
        <Link className="text-blue-600 underline" href="/cookies">Cookies</Link>
      </p>
    </article>
  );
}

export function PrivacyPolicy() {
  return (
    <LegalDoc title="Privacy Policy" updated="[date]">
      <p>{ENTITY} ({ADDRESS}) operates Leadex AI. This policy explains what personal data the platform processes, why, and your rights. Contact: {CONTACT}.</p>
      <h2>Our two roles</h2>
      <ul>
        <li><strong>Controller</strong> for account data of people who sign up (name, email, password hash, sign-in sessions, audit logs).</li>
        <li><strong>Processor</strong> for the business and lead data our customers store or discover in their workspace. Each customer decides how that data is used and is responsible for having a lawful basis to contact anyone.</li>
      </ul>
      <h2>Data we process</h2>
      <ul>
        <li>Account data: name, email, hashed password (Argon2id), optional two-factor secret (encrypted), device/session records (browser type, IP address).</li>
        <li>Business data from public sources such as Google Places, retained only as long as the provider&apos;s terms allow and attributed to its source.</li>
        <li>Lead and communication data entered by customers: contact details, notes, consent records, call transcripts, email and WhatsApp messages.</li>
        <li>Website enquiries sent through our contact and demo forms.</li>
      </ul>
      <h2>How outreach is controlled</h2>
      <p>Before any call, email or WhatsApp message, the platform checks suppression lists, recorded consent, calling windows and kill switches, and blocks the message when eligibility is uncertain. AI voice agents disclose that they are AI at the start of each call.</p>
      <h2>Sub-processors</h2>
      <p>Depending on the features a customer enables: hosting provider [name, region], Google (Places API), Twilio (voice), Meta (WhatsApp Business Platform), email providers (Gmail / Microsoft / SMTP), Stripe or Razorpay (payments). AI models run on our own infrastructure by default; third-party AI providers are used only if a customer enables them.</p>
      <h2>Retention</h2>
      <p>Account data is kept while the account is active and for [period] afterwards. Customer workspace data is deleted [period] after the workspace is closed. Audit logs are kept for [period] for security.</p>
      <h2>Your rights</h2>
      <p>Depending on where you live (for example under the GDPR, UK GDPR, India&apos;s DPDP Act or US state laws), you may request access, correction, deletion, portability, or object to processing. Email {CONTACT}. If your data is in a customer&apos;s workspace, we will forward your request to that customer.</p>
      <h2>Security</h2>
      <p>Tenant data is isolated with PostgreSQL row-level security, secrets are encrypted at rest, passwords are hashed, and every sensitive action is recorded in an append-only audit log.</p>
      <h2>International transfers</h2>
      <p>[Describe where data is stored and the transfer safeguards used, e.g. Standard Contractual Clauses.]</p>
    </LegalDoc>
  );
}

export function TermsOfService() {
  return (
    <LegalDoc title="Terms of Service" updated="[date]">
      <p>These terms are an agreement between you (the customer) and {ENTITY} for use of Leadex AI.</p>
      <h2>Acceptable use</h2>
      <ul>
        <li>You must have a lawful basis, and where required consent, before contacting anyone through the platform, and must follow telemarketing, anti-spam and do-not-call rules (for example TCPA, TRAI/TCCCPR, PECR, CAN-SPAM).</li>
        <li>You must not disable or work around the platform&apos;s compliance checks, AI disclosure, or opt-out handling.</li>
        <li>You must use third-party data (for example Google Places) only as that provider&apos;s terms permit.</li>
        <li>No unlawful, deceptive, harassing or discriminatory content or campaigns.</li>
      </ul>
      <h2>Your data</h2>
      <p>You own the data in your workspace. We process it only to provide the service, under our Data Processing Agreement [link].</p>
      <h2>AI output</h2>
      <p>AI-generated text, websites, call summaries and budget estimates can be wrong. Review them before relying on them or sending them to anyone.</p>
      <h2>Plans and payment</h2>
      <p>Prices are shown on the pricing page or in your order. Usage-based charges (calls, messages) are billed as recorded in your workspace. [Refund, renewal and cancellation terms.]</p>
      <h2>Availability</h2>
      <p>[Service levels, maintenance windows, support hours.]</p>
      <h2>Liability</h2>
      <p>[Limitation of liability, indemnities, governing law and jurisdiction.]</p>
      <h2>Termination</h2>
      <p>You can close your workspace at any time. We may suspend accounts that break these terms, especially the outreach rules above.</p>
    </LegalDoc>
  );
}

export function CookiePolicy() {
  return (
    <LegalDoc title="Cookie Policy" updated="[date]">
      <p>This policy reflects what the Leadex AI web app currently stores in your browser.</p>
      <h2>What we store</h2>
      <ul>
        <li><strong>Sign-in tokens and selected workspace</strong> in browser local storage, strictly necessary to keep you signed in.</li>
        <li><strong>Interface preferences</strong> (for example theme or saved lead views), stored locally on your device.</li>
      </ul>
      <h2>What we do not use</h2>
      <p>The platform does not set advertising cookies or third-party tracking pixels, and does not include third-party analytics. If that changes, this page will be updated and a consent banner shown first where the law requires one.</p>
      <h2>Third-party pages</h2>
      <p>Hosted payment pages (Stripe, Razorpay) and embedded images from image hosts set their own cookies under their own policies.</p>
      <h2>Clearing data</h2>
      <p>Signing out removes the sign-in tokens. You can clear all stored data from your browser settings at any time.</p>
    </LegalDoc>
  );
}
