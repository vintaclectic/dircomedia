import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import { Home, FileText, Video, Calendar, BarChart2, Settings, Radio } from "lucide-react";
import { Bebas_Neue, Inter, JetBrains_Mono, Instrument_Serif } from "next/font/google";

const bebasNeue = Bebas_Neue({ weight: "400", subsets: ["latin"], variable: "--font-display", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });
const instrumentSerif = Instrument_Serif({ weight: "400", style: ["normal", "italic"], subsets: ["latin"], variable: "--font-serif", display: "swap" });

export const metadata: Metadata = {
  title: { default: "DirCo Media OS", template: "%s · DirCo" },
  description: "Automated content and social marketing OS for the DirCo galaxy.",
  icons: { icon: "/dirco-logo.svg", shortcut: "/dirco-logo.svg", apple: "/dirco-logo.svg" },
};

const NAV = [
  { href: "/",          label: "Dashboard", icon: Home },
  { href: "/approvals", label: "Approvals", icon: Radio },
  { href: "/content",   label: "Content",   icon: FileText },
  { href: "/video",     label: "Video",     icon: Video },
  { href: "/schedule",  label: "Schedule",  icon: Calendar },
  { href: "/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/settings",  label: "Settings",  icon: Settings },
];

const PROJECTS = [
  { slug: "dirco",        name: "DirCo",        color: "#0055FF" },
  { slug: "dirhaven-rp",  name: "DirHaven RP",  color: "#FF2222" },
  { slug: "dirhaven-app", name: "DirHaven App", color: "#00DD88" },
  { slug: "dirmegle",     name: "DirMegle",     color: "#FF5500" },
  { slug: "medaled",      name: "Medaled",      color: "#FFD700" },
  { slug: "agentis",      name: "Agentis",      color: "#7C3AED" },
  { slug: "vintinuum",    name: "Vintinuum",    color: "#F0287A" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${bebasNeue.variable} ${inter.variable} ${jetbrainsMono.variable} ${instrumentSerif.variable}`}>
      <body style={{ margin: 0, background: "#020205", color: "#f5f5f7", fontFamily: "var(--font-sans), system-ui, sans-serif", WebkitFontSmoothing: "antialiased" }}>

        {/* Page shell */}
        <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>

          {/* ── SIDEBAR ── */}
          <aside className="desktop-only" style={{
            width: 220,
            minWidth: 220,
            display: "flex",
            flexDirection: "column",
            background: "#080810",
            borderRight: "1px solid rgba(255,255,255,0.07)",
            overflow: "hidden",
          }}>

            {/* Logo */}
            <div style={{ padding: "18px 20px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <Link href="/" style={{ display: "flex", alignItems: "center", gap: 11, textDecoration: "none" }}>
                <div style={{ position: "relative", flexShrink: 0 }}>
                  <div style={{
                    position: "absolute", inset: -6,
                    background: "radial-gradient(ellipse at center, rgba(0,85,255,0.25), transparent 70%)",
                    pointerEvents: "none",
                  }} />
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src="/dirco-logo.svg" alt="DirCo" style={{ width: 36, height: 36, display: "block", position: "relative" }} />
                </div>
                <div>
                  <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 17, color: "#f5f5f7", letterSpacing: "0.05em", lineHeight: 1 }}>DIRCO</div>
                  <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 8.5, color: "#36363f", letterSpacing: "0.22em", textTransform: "uppercase", marginTop: 3 }}>MEDIA · OS</div>
                </div>
              </Link>
            </div>

            {/* Nav */}
            <div style={{ padding: "14px 10px 6px" }}>
              <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 8.5, color: "#36363f", letterSpacing: "0.22em", textTransform: "uppercase", padding: "0 10px", marginBottom: 6 }}>Navigate</div>
              {NAV.map(({ href, label, icon: Icon }) => (
                <Link key={href} href={href} style={{
                  display: "flex", alignItems: "center", gap: 9,
                  padding: "8px 10px", borderRadius: 8, marginBottom: 1,
                  textDecoration: "none", color: "#8a8a98", fontSize: 13, fontWeight: 500,
                  letterSpacing: "-0.01em", transition: "all 0.15s",
                }} className="sidebar-link">
                  <Icon size={14} strokeWidth={1.75} style={{ flexShrink: 0, opacity: 0.65 }} />
                  {label}
                </Link>
              ))}
            </div>

            {/* Projects */}
            <div style={{ padding: "16px 10px 10px", borderTop: "1px solid rgba(255,255,255,0.05)", marginTop: "auto" }}>
              <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 8.5, color: "#36363f", letterSpacing: "0.22em", textTransform: "uppercase", padding: "0 10px", marginBottom: 8 }}>Projects</div>
              {PROJECTS.map(p => (
                <div key={p.slug} style={{ display: "flex", alignItems: "center", gap: 9, padding: "5px 10px", borderRadius: 6 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: p.color, boxShadow: `0 0 7px ${p.color}99`, flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: "#56565f", letterSpacing: "-0.01em" }}>{p.name}</span>
                </div>
              ))}
            </div>

            {/* Status footer */}
            <div style={{ padding: "12px 20px", borderTop: "1px solid rgba(255,255,255,0.05)", display: "flex", alignItems: "center", gap: 7 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00DD88", boxShadow: "0 0 7px #00DD88", flexShrink: 0 }} />
              <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 8.5, color: "#56565f", letterSpacing: "0.2em", textTransform: "uppercase" }}>Online · v1.0</span>
            </div>
          </aside>

          {/* ── MAIN ── */}
          <main style={{ flex: 1, overflowY: "auto", overflowX: "hidden", minWidth: 0 }}>
            {children}
          </main>
        </div>

        {/* Mobile bottom nav */}
        <nav className="bottom-nav mobile-only">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href}>
              <Icon size={18} strokeWidth={1.75} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>

        <style>{`.sidebar-link:hover { color: #f5f5f7 !important; background: rgba(255,255,255,0.04) !important; }`}</style>
      </body>
    </html>
  );
}
