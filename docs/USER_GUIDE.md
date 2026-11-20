# LEADEX AI: User Guide

A plain-English guide for people who use the app day to day. You do not need any technical knowledge.

What you see depends on your role. If a button or page is missing, you probably do not have permission; ask your workspace owner.

## What "simulated" means

You will see **Simulated** badges in several places. It means the action was **practised, not real**: no real phone call was made, no real email, WhatsApp message or payment was sent, and no real AI model wrote the text. Simulated mode is on whenever the app is not running in its live production setting, or when a provider (phone, email, payments) has not been connected yet. Simulated calls are never used for self-learning. Real outreach starts only once your administrator has switched the app to production and connected the providers.

## Getting started (onboarding)

After you register, the **Onboarding** page walks you through setup. Each step can be skipped and finished later:

1. **Tell us about your company**: company name, the industry you sell to, primary city, team size and main growth goal. Press **Save profile**.
2. **Bring in your first businesses**: run a search by industry and city (Discovery).
3. **Generate a website demo**: pick a template and preview a website for a business.
4. **Create your first AI voice agent**.
5. **Connect your channels** (open Integrations).
6. **Invite a teammate**.

When done, choose **Go to Command Center**.

## Dashboard

The dashboard shows how your pipeline is doing: a launch checklist (**Continue setup**), pipeline value by stage, a conversion funnel built from lead status history, a revenue forecast based on your history, top opportunities (open leads with a stated budget), AI agent performance (runs, outcomes, speed) and a latest-activity feed. It shows "Insufficient data" until you have enough history. You can also type a question in **Ask your pipeline anything** (Copilot).

## Discovery: find businesses

Open **Discovery** to find businesses from official data sources or from your own files. Every field remembers where it came from.

- **New search**: pick a category and location, choose sources, and press **Run search**. Past searches appear under **Job history**.
- **Import CSV**: upload your own spreadsheet saved as CSV. The app tells you how many rows were new and how many were merged with existing records (duplicates).
- Filter by category or website status, then use **Convert to lead** to move a business into your CRM. Businesses already in your CRM are marked **In leads**.
- **Export CSV** downloads your results.

If no search provider is connected, results may be sample data and are labelled as such.

## Leads and CRM

**Leads** is your list of prospects.

- Search, filter by country, industry, owner or website, and **Save view** to keep a filter for later.
- **New lead** adds one by hand (business name is required).
- Open a lead to see details, **Change status**, set the **Assignee**, **Add note**, add a **New task**, edit or delete the lead.
- The lead page shows whether **Consent on file** exists and its reference. Record consent in Compliance before contacting someone.

The **Pipeline** page shows leads by stage.

## Website Studio

Open **Websites** to create sample sites for businesses.

1. **New website**, then **Generate website** to create a draft.
2. Review the preview and edit sections (move up, move down, remove, restore).
3. **Approve** it, then **Publish**. If something is wrong, **Roll back live site**.
4. **Share preview** gives you a link to show a prospect before it is live.

## AI agents

Open **Agents** to see your agents. Choose **New agent**, or start from **Templates** (**Use template**).

**Creating an agent**: set its purpose, industry, language, personality and greeting; add business information and qualification questions; set conversation flow steps, an escalation policy and a maximum call length. A **compliance disclosure** is required and is spoken first on every call. You can add documents so the agent can answer from your knowledge. **Publish** creates a version; older versions stay under **Published versions**.

**Test lab**: try an agent before it ever speaks to a customer. Type messages (or use browser speech-to-text), optionally have replies read aloud, switch **Use knowledge** on or off and see **Citations**. You can also try a tool call. The provider can be set to **Simulated** (template replies, no AI model).

**Phone voice**: in the agent form choose a **Phone voice** (default is a female voice suited to the language) and a **Speaking rate**.

**Self-learning openings**: on an agent page, add two or more different ways to open a call under **Self-learning**. On real calls the agent tries them and gradually favours the ones that lead to better outcomes; you see how many calls were scored and an estimated "chance best" per opening. You can **Pause** or **Resume** an opening. Only real calls count.

**Rating calls Good/Bad**: open a real call that has a transcript and press **Good call** or **Bad call** (with an optional note). Your rating overrides the automatic score and teaches the agent directly.

## Calls

**Calls** lists call history with status filters. Open a call to see status, duration, transcript, outcome, interest, decision maker, timeline and next step. The page also has a telephony card showing whether calling is real, simulated or not set up, with steps to connect Twilio. Before a call can start the lead needs a phone number and country, voice consent, and approval for outreach, and the agent must be published. Calls blocked by compliance rules show as **blocked** with a reason. From a call you can use **Teach the agent**.

## Campaigns: voice, email and WhatsApp

Open **Campaigns**, then **New campaign**:

1. Choose the **Channel** and the **Recipients**.
2. Build a **Sequence** of steps with **Add step**.
3. For **voice** campaigns pick the voice agent and use the **concurrency slider** (1 to 20) to set how many calls may run at the same time. Start low.
4. Email campaigns require your **physical mailing address** (a legal requirement under CAN-SPAM). You can restrict the send window (UTC hours) and set an optional spend limit.
5. **Create draft**, then on the campaign page **Submit for approval**. Someone with permission **Approves** it, and you can **Process due steps**. The timeline and per-recipient table show what was sent, delivered, bounced or blocked.

Separate pages: **Email** (connect Gmail or Outlook, see your mailboxes and previews) and **WhatsApp** (conversations, numbers, templates, and a "Needs a human" queue).

## Marketplace

The **Marketplace** connects customers' requirements with service providers.

- **New provider**: business name, categories, service city and country, availability, typical project size, experience.
- **New requirement**: customer name and email, service category, location, budget range, timeline, and a **consent reference** (required).
- **Run matching** suggests providers. Contact is only possible when permitted.
- Open a provider to see **verification history**, upload documents and record a manual verification decision (Verified, Rejected, Pending) with evidence of what was checked.

## Workflows

**Workflows** lets you build automations as a diagram of nodes and connections. Use **Validate**, **Save draft**, **Save version** and **Run published version**. The **Execution log** shows what happened. The workflows list shows pending approvals (**Approve**) and success rate.

## Compliance

Open **Compliance** for the rules that protect your customers and you:

- **Gate checker**: check whether a contact may be reached on a channel.
- **Consents**: **Record consent** (who, channel, evidence) and **Withdraw** it later.
- **Suppressions**: **Suppress** a contact to stop outreach; **Release** removes it.
- **Kill switches**: emergency stops for outreach.
- **DNC registry**: numbers on a national do-not-call list are blocked for calls, SMS and WhatsApp. Import the scrub file from your own registry subscription (for India, TRAI NCPR through your DLT/telemarketer registration). Importing **replaces the previous list** for that country. Files older than the shown number of days count as stale.
- **Data requests** (for people with the right permission): **Log request** when someone asks for their data. **Export data** downloads everything held about them. For deletion requests, **Erase data** permanently deletes their personal data (transcripts, notes, messages) and keeps a do-not-contact entry. Erasing cannot be undone.

This page helps you follow the rules; it is not legal advice.

## Billing

**Billing** shows your **Current plan** and usage. You can switch plan, set a **Monthly budget**, choose **Hard stop when the limit is reached**, allow paid-provider fallback, and view and pay **Invoices**. Payments marked "SIMULATED" move no money.

## Settings

- **Organization**: workspace name and country; **Invite a teammate** by email (**Send invite**); pending invitations are listed.
- **Security**: verify your email address, change your password, set up **two-factor authentication** with an authenticator app (scan or enter the setup key, then **Verify and enable**), view **Signed-in devices**, and **Sign out all other devices** if you lose a device.
- **Branding (white label)**: app name, logo URL, main colour, support email and custom app domain, then **Save branding**.

## Getting help

If something looks wrong, note what you clicked and any message shown, and send it to your administrator. They can use [API_GUIDE.md](API_GUIDE.md) and [GO_LIVE_CHECKLIST.md](GO_LIVE_CHECKLIST.md).
