"use client";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Briefcase, Building2, GraduationCap, Hammer, Home, PenTool, Sofa, Stethoscope, Store, UtensilsCrossed, Users, Wrench } from "lucide-react";

export const INDUSTRIES = [
  { icon: Home, name: "Real estate", body: "Find agencies and listings without a web presence; share a property-ready site preview.", tint: "from-[#0a84ff] to-[#64d2ff]" },
  { icon: PenTool, name: "Architects", body: "Discover practices, audit their portfolios and refer client briefs to them.", tint: "from-[#5e5ce6] to-[#0a84ff]" },
  { icon: Sofa, name: "Interior design", body: "Qualify studios by locality and show a portfolio-style website demo.", tint: "from-[#bf5af2] to-[#5e5ce6]" },
  { icon: Hammer, name: "Construction", body: "Track builders through the pipeline and match them to customer requirements.", tint: "from-[#ff9f0a] to-[#ff375f]" },
  { icon: UtensilsCrossed, name: "Restaurants", body: "Menu-first website previews and AI follow-ups for reservations.", tint: "from-[#ff375f] to-[#ff9f0a]" },
  { icon: Store, name: "Retail", body: "Reach shops that rely on walk-ins and help them get found online.", tint: "from-[#30d158] to-[#64d2ff]" },
  { icon: Stethoscope, name: "Clinics", body: "Appointment-focused agents with careful, consent-first outreach.", tint: "from-[#64d2ff] to-[#0a84ff]" },
  { icon: GraduationCap, name: "Education", body: "Institutes and tutors, with enquiry handling and course pages.", tint: "from-[#5e5ce6] to-[#bf5af2]" },
  { icon: Briefcase, name: "Professional services", body: "Consultants, accountants and agencies with credibility-focused sites.", tint: "from-[#0a84ff] to-[#5e5ce6]" },
  { icon: Building2, name: "Property brokers", body: "Route buyer requirements to verified brokers through the marketplace.", tint: "from-[#bf5af2] to-[#ff375f]" },
  { icon: Wrench, name: "Contractors", body: "Plumbers, electricians and trades with quick-quote website templates.", tint: "from-[#ff9f0a] to-[#ffd60a]" },
  { icon: Users, name: "SMBs", body: "Any local business that needs to be discovered, engaged and converted.", tint: "from-[#30d158] to-[#0a84ff]" },
];

/** Draggable (mouse and touch) carousel with constraints computed from content width. */
export function IndustryCarousel() {
  const wrap = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const [left, setLeft] = useState(0);
  useEffect(() => {
    const calc = () => { if (wrap.current && track.current) setLeft(Math.min(0, wrap.current.offsetWidth - track.current.scrollWidth)); };
    calc();
    window.addEventListener("resize", calc);
    return () => window.removeEventListener("resize", calc);
  }, []);
  return (
    <div ref={wrap} className="overflow-hidden px-4 sm:px-6">
      <motion.div ref={track} drag="x" dragConstraints={{ left, right: 0 }} dragElastic={0.12}
        whileDrag={{ cursor: "grabbing" }} className="flex w-max cursor-grab gap-4 pb-6 pt-2 active:cursor-grabbing">
        {INDUSTRIES.map(({ icon: Icon, name, body, tint }) => (
          <motion.article key={name} whileHover={{ y: -8 }} whileTap={{ scale: 0.97 }} transition={{ type: "spring", stiffness: 300, damping: 20 }}
            className="w-[250px] shrink-0 select-none rounded-3xl border border-line bg-white p-6 shadow-card sm:w-[280px]">
            <div className={`grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br ${tint} text-white`}><Icon className="h-5 w-5" /></div>
            <h3 className="mt-5 text-lg font-semibold tracking-tight">{name}</h3>
            <p className="mt-2 text-[14px] leading-relaxed text-muted">{body}</p>
          </motion.article>
        ))}
      </motion.div>
      <p className="text-center text-xs text-muted">Drag or swipe to explore</p>
    </div>
  );
}
