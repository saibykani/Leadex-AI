import type { Config } from "tailwindcss";

// Tokens are CSS variables (RGB triplets) so every token has a light AND dark value (see globals.css) while
// alpha modifiers like `bg-accent/10` keep working. Token names are stable so existing components need no changes.
const v = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        surface: v("surface"),
        raised: v("raised"),
        line: v("line"),
        muted: v("muted"),
        ink: v("ink"),
        accent: { DEFAULT: v("accent"), soft: "rgb(var(--c-accent) / 0.08)", strong: v("accent-strong") },
        danger: v("danger"),
        success: v("success"),
        warning: v("warning"),
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "SF Pro Text", "Inter", "Segoe UI", "Roboto", "Helvetica Neue", "sans-serif"],
        display: ["-apple-system", "BlinkMacSystemFont", "SF Pro Display", "Inter", "Segoe UI", "Roboto", "sans-serif"],
      },
      fontSize: {
        "display-lg": ["44px", { lineHeight: "1.05", letterSpacing: "-0.035em", fontWeight: "700" }],
        "display": ["34px", { lineHeight: "1.1", letterSpacing: "-0.03em", fontWeight: "650" }],
        "title": ["22px", { lineHeight: "1.25", letterSpacing: "-0.02em", fontWeight: "600" }],
        "eyebrow": ["11px", { lineHeight: "1.2", letterSpacing: "0.08em", fontWeight: "600" }],
      },
      boxShadow: {
        card: "var(--shadow-card)",
        lift: "var(--shadow-lift)",
        glow: "0 0 0 1px rgb(var(--c-accent) / 0.12), 0 8px 32px -8px rgb(var(--c-accent) / 0.35)",
        inset: "inset 0 1px 0 0 rgb(255 255 255 / 0.06)",
      },
      backgroundImage: {
        "brand": "linear-gradient(135deg, #0a84ff 0%, #5e5ce6 55%, #bf5af2 100%)",
        "brand-soft": "linear-gradient(135deg, rgb(10 132 255 / 0.12), rgb(94 92 230 / 0.10) 55%, rgb(191 90 242 / 0.12))",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "fade-up": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } },
        "pulse-ring": { "0%": { transform: "scale(.8)", opacity: ".7" }, "100%": { transform: "scale(2.2)", opacity: "0" } },
        gradient: { "0%,100%": { backgroundPosition: "0% 50%" }, "50%": { backgroundPosition: "100% 50%" } },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        "fade-up": "fade-up .35s ease-out both",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0,0,.2,1) infinite",
        gradient: "gradient 8s ease infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
