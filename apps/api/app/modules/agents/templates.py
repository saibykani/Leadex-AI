"""Seed agent templates. Static, versioned with the code; instantiated per tenant via POST /agents/from-template."""

_DISCLOSURE = ("Hi, this is an automated AI assistant calling on behalf of {business}. This call may be "
               "recorded only with your consent. You can ask to stop at any time and we will not call again.")


def _t(key, name, industry, purpose, greeting, questions, flow, objections, tools, escalation, info=""):
    return {
        "key": key, "name": name, "industry": industry, "purpose": purpose,
        "personality": "Warm, concise, professional. Never pushy. Admits when it does not know.",
        "language": "en", "speaking_rate": 1.0, "voice": "default-en", "greeting": greeting,
        "business_info": info, "qualification_questions": questions, "conversation_flow": flow,
        "objection_handling": objections, "tools": tools, "escalation_policy": escalation,
        "max_call_seconds": 300,
        "business_hours": {"timezone": "Asia/Kolkata", "days": ["mon", "tue", "wed", "thu", "fri"],
                           "start": "10:00", "end": "18:00"},
        "compliance_disclosure": _DISCLOSURE,
    }


_STD_FLOW = ["disclosure", "greeting", "permission_to_continue", "qualification", "value_pitch", "next_step",
             "close"]
_ESC = "Transfer to a human or book a callback if the person asks for one, is upset, or asks legal/pricing specifics."

TEMPLATES: list[dict] = [
    _t("business_website_sales", "Business Website Sales", "web services",
       "Offer a professional website to small businesses without one.",
       "Hello! I noticed your business may not have a website yet. Do you have two minutes?",
       ["Do you currently have a website?", "How do customers usually find you?", "What is your budget range?"],
       _STD_FLOW, [{"objection": "Too expensive", "response": "We have starter plans; can I share options by email?"},
                   {"objection": "Not interested", "response": "Understood, thank you. I will note that."}],
       ["crm_lookup", "create_note", "book_callback"], _ESC),
    _t("real_estate_qualification", "Real Estate Qualification", "real estate",
       "Qualify property buyer/seller inquiries.",
       "Hello! Thanks for your interest in our properties. May I ask a few quick questions?",
       ["Are you looking to buy, sell or rent?", "Which locality?", "What is your budget?", "Timeline?"],
       _STD_FLOW, [{"objection": "Just browsing", "response": "No problem, may I send listings that match?"}],
       ["crm_lookup", "create_note", "book_callback"], _ESC),
    _t("architect_inquiry", "Architect Inquiry", "architecture",
       "Capture requirements for architecture/design projects.",
       "Hello! You reached out about a design project. Could you tell me a little about it?",
       ["Residential or commercial?", "Plot size or built-up area?", "Do you have approvals?", "Timeline?"],
       _STD_FLOW, [{"objection": "Need to discuss with family", "response": "Of course, shall I book a callback?"}],
       ["crm_lookup", "create_note", "book_callback"], _ESC),
    _t("construction_services", "Construction Services", "construction",
       "Qualify construction and renovation leads.",
       "Hello! I'm calling about your construction or renovation inquiry. Is now a good time?",
       ["New build or renovation?", "Location?", "Approximate budget?", "Desired start date?"],
       _STD_FLOW, [{"objection": "Already have a contractor", "response": "Understood; may we send a second quote?"}],
       ["crm_lookup", "create_note", "book_callback"], _ESC),
    _t("restaurant_inquiry", "Restaurant Inquiry", "restaurants",
       "Answer restaurant questions: hours, reservations, catering.",
       "Hello! Thanks for calling. How can I help with your reservation or question today?",
       ["How many guests?", "Which date and time?", "Any dietary requirements?"],
       ["disclosure", "greeting", "intent", "answer", "next_step", "close"],
       [{"objection": "Fully booked?", "response": "I can add you to the waitlist or suggest another slot."}],
       ["create_note", "book_callback"], _ESC),
    _t("appointment_booking", "Appointment Booking", "services",
       "Book appointments and callbacks.",
       "Hello! I can help you book an appointment. What day works best for you?",
       ["What service do you need?", "Preferred date and time?", "Best contact number?"],
       ["disclosure", "greeting", "collect_details", "confirm", "close"],
       [{"objection": "Not sure of my schedule", "response": "I can book a tentative callback instead."}],
       ["crm_lookup", "book_callback"], _ESC),
    _t("follow_up", "Follow-up", "general",
       "Follow up on a previous conversation or proposal.",
       "Hello! I'm following up on our earlier conversation. Is this still a good time?",
       ["Did you get a chance to review our proposal?", "Any questions I can answer?"],
       ["disclosure", "greeting", "recap", "questions", "next_step", "close"],
       [{"objection": "Need more time", "response": "Sure, when should we check back?"}],
       ["crm_lookup", "create_note", "book_callback"], _ESC),
    _t("customer_support", "Customer Support", "general",
       "Answer customer questions using the knowledge base; escalate when unsure.",
       "Hello! How can I help you today?",
       ["Can you describe the issue?", "When did it start?"],
       ["disclosure", "greeting", "diagnose", "answer_from_knowledge", "escalate_or_close"],
       [{"objection": "I want a human", "response": "Of course, I will arrange a callback from our team."}],
       ["crm_lookup", "create_note", "book_callback"], _ESC),
    _t("general_business_development", "General Business Development", "general",
       "Introduce services and identify interest for a sales follow-up.",
       "Hello! I'm reaching out to introduce our services. Do you have a moment?",
       ["What are your main growth goals this year?", "Who handles these decisions?"],
       _STD_FLOW, [{"objection": "Send me an email", "response": "Happy to. Which address should we use?"}],
       ["crm_lookup", "create_note", "book_callback"], _ESC),
]

# Budget-discovery sales agent (used by the lead pipeline). The disclosure is the first line of every conversation
# (orchestrator system prompt). It never invents prices: `business_info` is replaced with the org's configured
# package ranges by POST /pipeline/budget-agent; without them it must ask for the prospect's budget instead.
BUDGET_DISCOVERY_NO_PRICES = ("No package prices are configured. Do NOT quote, estimate or invent any price. "
                              "Ask the prospect what budget range they have in mind and note it.")
TEMPLATES.append(_t(
    "website_sales_budget_discovery", "Website Sales – Budget Discovery", "web services",
    "Understand the prospect's current website, goals, budget range, timeline and decision maker for a new "
    "website. Never invent prices; only quote org-configured package ranges, otherwise ask for their budget.",
    "Hello! I'm calling about helping your business get more customers online. Do you have two minutes?",
    ["Do you have a website today? What do you like or dislike about it?",
     "What should a website do for you: more calls, bookings, enquiries, or credibility?",
     "What budget range did you have in mind for a website?",
     "When would you like it to be live?",
     "Who else is involved in deciding on this?"],
    ["disclosure", "permission_to_continue", "current_website", "goals", "budget_range", "timeline",
     "decision_maker", "objections", "next_step", "close"],
    [{"objection": "Too expensive", "response": "Understood. What range would feel comfortable? We can scope to it."},
     {"objection": "We already have a website", "response": "Great. Is it bringing you enquiries? We can review it."},
     {"objection": "No time now", "response": "No problem. When is a better time for a short callback?"},
     {"objection": "Not interested", "response": "Thank you for your time. I will make sure we do not call again."},
     {"objection": "What does it cost?", "response": "Only quote configured package ranges; otherwise say a "
                                                     "specialist will confirm pricing and ask their budget."}],
    ["crm_lookup", "create_note", "book_callback"], _ESC, info=BUDGET_DISCOVERY_NO_PRICES))

TEMPLATES_BY_KEY = {t["key"]: t for t in TEMPLATES}
