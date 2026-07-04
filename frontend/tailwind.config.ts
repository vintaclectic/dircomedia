import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Stage blacks — deeper, more purple-blue atmosphere
        void: "#020205",
        obsidian: "#04040a",
        ink: "#07070e",
        graphite: "#0b0b14",
        slate: "#11111c",
        steel: "#1a1a26",
        chrome: "#26262f",
        silver: "#3a3a48",

        // Text scale
        bone: "#f5f5f7",
        smoke: "#c8c8d2",
        ash: "#8a8a98",
        dust: "#56565f",
        fog: "#36363f",

        // Primary action — electric cyan-blue
        electric: "#0055FF",
        "electric-bright": "#3D8BFF",
        "electric-deep": "#0044CC",
        cyan: "#00E5FF",

        // Skull & roses accent
        crimson: "#B91C1C",
        rose: "#FF0844",
        "bone-white": "#F8F5EE",

        // Project signatures — corrected to spec
        "p-dirco": "#0055FF",
        "p-dirhaven-rp": "#FF2222",
        "p-dirhaven-app": "#00DD88",
        "p-dirmegle": "#FF5500",
        "p-medaled": "#FFD700",
        "p-agentis": "#7C3AED",
        "p-vintinuum": "#F0287A",

        // Semantic
        success: "#00DD88",
        warning: "#FFB020",
        danger: "#FF3B47",

        // Legacy aliases (compat)
        bg: "#020205",
        surface: "#0b0b14",
        border: "#1a1a26",
        muted: "#26262f",
        "text-muted": "#56565f",
        "text-secondary": "#8a8a98",
        accent: "#0055FF",
        "accent-hover": "#3D8BFF",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "'Bebas Neue'", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      letterSpacing: {
        tightest: "-0.04em",
        tighter: "-0.025em",
        widest: "0.24em",
      },
      boxShadow: {
        "glow-sm": "0 0 12px rgba(0,85,255,0.30)",
        "glow-md": "0 0 32px rgba(0,85,255,0.40)",
        "glow-lg": "0 0 80px rgba(0,85,255,0.50)",
        "inner-line": "inset 0 1px 0 rgba(255,255,255,0.06)",
      },
      backdropBlur: {
        xs: "2px",
      },
      animation: {
        shimmer: "shimmer 2.4s linear infinite",
        "pulse-soft": "pulseSoft 3.5s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        "border-spin": "borderSpin 4s linear infinite",
        rise: "rise 0.55s cubic-bezier(0.16,1,0.3,1) both",
        "fade-in": "fadeIn 0.4s ease-out both",
        halo: "halo 4s ease-in-out infinite",
        count: "count 0.9s ease-out both",
        scan: "scan 3s linear infinite",
        heartbeat: "heartbeat 1.8s ease-in-out infinite",
        "drift-slow": "driftSlow 30s ease-in-out infinite",
        "particle-rise": "particleRise 18s linear infinite",
        "spectrum-shift": "spectrumShift 12s linear infinite",
        "rocket-launch": "rocketLaunch 0.6s cubic-bezier(0.16,1,0.3,1) both",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-6px)" },
        },
        borderSpin: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        rise: {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        halo: {
          "0%, 100%": { opacity: "0.4", transform: "scale(1)" },
          "50%": { opacity: "0.9", transform: "scale(1.08)" },
        },
        count: {
          "0%": { opacity: "0", transform: "translateY(6px) scale(0.96)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        heartbeat: {
          "0%, 100%": { transform: "scale(1)", opacity: "0.95" },
          "14%": { transform: "scale(1.06)", opacity: "1" },
          "28%": { transform: "scale(1)", opacity: "0.9" },
          "42%": { transform: "scale(1.04)", opacity: "1" },
          "70%": { transform: "scale(1)", opacity: "0.95" },
        },
        driftSlow: {
          "0%, 100%": { transform: "translate(0, 0) rotate(0deg)" },
          "33%": { transform: "translate(2%, -1%) rotate(0.5deg)" },
          "66%": { transform: "translate(-1%, 2%) rotate(-0.5deg)" },
        },
        particleRise: {
          "0%": { transform: "translateY(100vh) translateX(0)", opacity: "0" },
          "10%": { opacity: "0.6" },
          "90%": { opacity: "0.4" },
          "100%": { transform: "translateY(-10vh) translateX(20px)", opacity: "0" },
        },
        spectrumShift: {
          "0%, 100%": { filter: "hue-rotate(0deg)" },
          "50%": { filter: "hue-rotate(20deg)" },
        },
        rocketLaunch: {
          "0%": { transform: "translateY(0) scale(1)", opacity: "1" },
          "50%": { transform: "translateY(-8px) scale(1.02)", opacity: "1" },
          "100%": { transform: "translateY(0) scale(1)", opacity: "1" },
        },
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
        "in-out-expo": "cubic-bezier(0.87, 0, 0.13, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
