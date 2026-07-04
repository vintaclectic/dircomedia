"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { listContent, getProjects, postNow, approveContent } from "@/lib/api";
import { ContentCard } from "@/components/ContentCard";
import { QuickPost } from "@/components/QuickPost";
import { PROJECT_COLORS } from "@/components/ProjectSelector";

// ─── animated counter ────────────────────────────────────────────────────────
function Num({ n }: { n: number }) {
  const [v, setV] = useState(0);
  const prev = useRef(0);
  useEffect(() => {
    const start = performance.now();
    const from = prev.current;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 900);
      const e = 1 - (1 - t) ** 3;
      setV(Math.round(from + (n - from) * e));
      if (t < 1) requestAnimationFrame(tick);
      else prev.current = n;
    };
    requestAnimationFrame(tick);
  }, [n]);
  return <>{v}</>;
}

// ─── live clock ──────────────────────────────────────────────────────────────
function Clock() {
  const [t, setT] = useState("--:--:--");
  useEffect(() => {
    const up = () => setT(new Date().toLocaleTimeString("en-GB"));
    up(); const id = setInterval(up, 1000); return () => clearInterval(id);
  }, []);
  return <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 12, color: "#c8c8d2", letterSpacing: "0.1em" }}>{t}</span>;
}

// ─── stat card ───────────────────────────────────────────────────────────────
function Stat({ label, value, color, sub }: { label: string; value: number; color: string; sub?: string }) {
  return (
    <div style={{
      background: "#0b0b14",
      border: "1px solid rgba(255,255,255,0.09)",
      borderRadius: 14,
      padding: "22px 24px 18px",
      position: "relative",
      overflow: "hidden",
    }}>
      {/* corner glow */}
      <div style={{ position: "absolute", top: -32, right: -32, width: 120, height: 120, borderRadius: "50%", background: color, opacity: 0.18, filter: "blur(32px)", pointerEvents: "none" }} />
      <div style={{ position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#56565f" }}>{label}</span>
          {sub && <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.14em", textTransform: "uppercase", color: "#00DD88" }}>{sub}</span>}
        </div>
        <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 72, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.02em", textShadow: `0 0 48px ${color}44` }}>
          <Num n={value} />
        </div>
        <div style={{ marginTop: 16, height: 1, background: `linear-gradient(90deg, ${color}88 0%, transparent 65%)` }} />
      </div>
    </div>
  );
}

// ─── dashboard ───────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { data: content, mutate } = useSWR("content", () => listContent({ limit: 12 }));
  const { data: projects } = useSWR("projects", getProjects);

  const total     = content?.length ?? 0;
  const posted    = content?.filter(c => c.status === "posted").length ?? 0;
  const scheduled = content?.filter(c => c.status === "scheduled").length ?? 0;
  const nProjects = projects?.length ?? 0;

  return (
    <div style={{ minHeight: "100vh" }}>

      {/* header */}
      <div style={{
        position: "sticky", top: 0, zIndex: 20,
        background: "rgba(2,2,5,0.88)",
        backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        padding: "18px 32px",
        display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16,
      }}>
        <div>
          <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f", marginBottom: 5 }}>Command Center</div>
          <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 40, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>DASHBOARD</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 8.5, letterSpacing: "0.2em", textTransform: "uppercase", color: "#36363f", marginBottom: 3 }}>Local</div>
            <Clock />
          </div>
          <div style={{ width: 1, height: 32, background: "rgba(255,255,255,0.07)" }} />
          <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "7px 12px", borderRadius: 8, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00DD88", boxShadow: "0 0 7px #00DD88" }} />
            <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "#c8c8d2" }}>Nominal</span>
          </div>
        </div>
      </div>

      {/* body */}
      <div style={{ padding: "36px 32px", maxWidth: 1560, margin: "0 auto" }}>

        {/* stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 40 }}>
          <Stat label="Projects"  value={nProjects} color="#0055FF" sub={nProjects > 0 ? "live" : undefined} />
          <Stat label="Content"   value={total}     color="#7C3AED" />
          <Stat label="Posted"    value={posted}    color="#00DD88" sub={posted > 0 ? `+${posted}` : undefined} />
          <Stat label="Scheduled" value={scheduled} color="#FF5500" />
        </div>

        {/* two-col */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 400px", gap: 24 }}>

          {/* stream */}
          <div>
            <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 18 }}>
              <div>
                <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f", marginBottom: 5 }}>Stream</div>
                <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 28, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>RECENT CONTENT</div>
              </div>
              <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, color: "#36363f", letterSpacing: "0.16em", textTransform: "uppercase" }}>{total} items</span>
            </div>

            {!content ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[0,1,2,3].map(i => <div key={i} className="shimmer" style={{ height: 88, borderRadius: 14 }} />)}
              </div>
            ) : content.length === 0 ? (
              <div style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: "60px 32px", textAlign: "center" }}>
                <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 44, color: "#f5f5f7", letterSpacing: "0.04em", marginBottom: 10 }}>EMPTY STAGE</div>
                <div style={{ fontSize: 13, color: "#56565f", lineHeight: 1.6 }}>Generate your first post to see the stream.</div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {content.map(c => (
                  <ContentCard key={c.id} content={c}
                    onPostNow={async id => { await postNow(id); mutate(); }}
                    onApprove={async id => { await approveContent(id); mutate(); }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* compose + galaxy */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <QuickPost />

            {projects && projects.length > 0 && (
              <div style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: "18px 18px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f" }}>Galaxy</span>
                  <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, color: "#26262f" }}>{projects.length} orbits</span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
                  {projects.map(p => {
                    const c = PROJECT_COLORS[p.slug] || "#666";
                    return (
                      <div key={p.slug} style={{ display: "flex", alignItems: "center", gap: 7, padding: "5px 10px", borderRadius: 8, background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: c, boxShadow: `0 0 6px ${c}`, flexShrink: 0 }} />
                        <span style={{ fontSize: 12, color: "#c8c8d2", letterSpacing: "-0.01em" }}>{p.name}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @media(max-width:1100px){.two-col{grid-template-columns:1fr !important}}
        @media(max-width:640px){.stat-grid{grid-template-columns:repeat(2,1fr) !important}}
      `}</style>
    </div>
  );
}
