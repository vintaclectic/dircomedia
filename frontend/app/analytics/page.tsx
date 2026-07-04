"use client";

import { useState } from "react";
import useSWR from "swr";
import { getProjectSummary, getStrategy, getProjects } from "@/lib/api";
import { PROJECT_COLORS } from "@/components/ProjectSelector";

const mono9: React.CSSProperties = { fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f" };

export default function AnalyticsPage() {
  const { data: projects } = useSWR("projects", getProjects);
  const [selected, setSelected] = useState("dirco");

  const { data: summary } = useSWR(["summary", selected], () => getProjectSummary(selected));
  const { data: strategy } = useSWR(["strategy", selected], () => getStrategy(selected));

  const accent = PROJECT_COLORS[selected] || "#0055FF";

  return (
    <div style={{ minHeight: "100vh" }}>

      {/* Header */}
      <div style={{
        position: "sticky", top: 0, zIndex: 20,
        background: "rgba(2,2,5,0.88)", backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        padding: "18px 32px",
        display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16,
      }}>
        <div>
          <div style={{ ...mono9, marginBottom: 5 }}>Insights</div>
          <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 40, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>ANALYTICS</div>
        </div>
        {/* Project tabs */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {(projects || []).map(p => {
            const c = PROJECT_COLORS[p.slug] || "#666";
            const on = selected === p.slug;
            return (
              <button key={p.slug} onClick={() => setSelected(p.slug)} style={{
                display: "inline-flex", alignItems: "center", gap: 7,
                padding: "6px 12px", borderRadius: 8, minHeight: 34,
                background: on ? `${c}18` : "rgba(255,255,255,0.02)",
                border: `1px solid ${on ? `${c}55` : "rgba(255,255,255,0.08)"}`,
                color: on ? "#f5f5f7" : "#56565f",
                fontSize: 12, fontWeight: 500, cursor: "pointer", transition: "all 0.15s",
              }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: c, boxShadow: on ? `0 0 6px ${c}` : "none", flexShrink: 0 }} />
                {p.name}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ padding: "32px 32px", maxWidth: 1200, margin: "0 auto" }}>

        {/* Stats grid */}
        {summary ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 36 }}>
            {[
              { label: "Impressions", value: String(summary.total_impressions ?? 0) },
              { label: "Likes",       value: String(summary.total_likes ?? 0) },
              { label: "Engagement",  value: `${((summary.avg_engagement_rate ?? 0) * 100).toFixed(1)}%` },
              { label: "Top Platform", value: summary.top_platform ?? "—" },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.09)", borderRadius: 14, padding: "22px 24px 18px", position: "relative", overflow: "hidden" }}>
                <div style={{ position: "absolute", top: -32, right: -32, width: 120, height: 120, borderRadius: "50%", background: accent, opacity: 0.14, filter: "blur(32px)", pointerEvents: "none" }} />
                <div style={{ position: "relative" }}>
                  <div style={{ ...mono9, marginBottom: 14 }}>{label}</div>
                  <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 64, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.02em", textShadow: `0 0 40px ${accent}44` }}>{value}</div>
                  <div style={{ marginTop: 14, height: 1, background: `linear-gradient(90deg, ${accent}88 0%, transparent 65%)` }} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 36 }}>
            {[0,1,2,3].map(i => <div key={i} className="shimmer" style={{ height: 140, borderRadius: 14 }} />)}
          </div>
        )}

        {/* Strategy */}
        {strategy && strategy.insights.length > 0 && (
          <div>
            <div style={{ ...mono9, marginBottom: 16 }}>AI Strategy · {selected}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {strategy.insights.map((insight: string, i: number) => (
                <div key={i} style={{
                  background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 14, padding: "18px 22px",
                  boxShadow: `inset 3px 0 0 0 ${accent}`,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    <span style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 22, color: accent, letterSpacing: "0.04em", lineHeight: 1 }}>0{i + 1}</span>
                  </div>
                  <div style={{ fontSize: 13, color: "#c4c4ce", lineHeight: 1.6 }}>{insight}</div>
                </div>
              ))}
            </div>
            {strategy.best_platforms.length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14 }}>
                <span style={{ ...mono9 }}>Best platforms</span>
                {strategy.best_platforms.map(p => (
                  <span key={p} style={{ ...mono9, padding: "2px 8px", borderRadius: 5, background: `${accent}18`, border: `1px solid ${accent}44`, color: accent }}>{p}</span>
                ))}
              </div>
            )}
          </div>
        )}

        {!summary && !strategy && (
          <div style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: "72px 32px", textAlign: "center" }}>
            <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 44, color: "#f5f5f7", letterSpacing: "0.04em", marginBottom: 10 }}>NO DATA YET</div>
            <div style={{ fontSize: 13, color: "#56565f", lineHeight: 1.6 }}>Post some content first to see analytics.</div>
          </div>
        )}
      </div>
    </div>
  );
}
