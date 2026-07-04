"use client";

import { useState } from "react";
import useSWR from "swr";
import { listContent, approveContent, postNow } from "@/lib/api";
import { ContentCard } from "@/components/ContentCard";
import type { ContentStatus } from "@/lib/types";

const FILTERS: { value: ContentStatus | "all"; label: string; color: string }[] = [
  { value: "all",              label: "All",       color: "#8a8a98" },
  { value: "approved",         label: "Approved",  color: "#00DD88" },
  { value: "pending_approval", label: "Review",    color: "#FFB020" },
  { value: "scheduled",        label: "Scheduled", color: "#3D8BFF" },
  { value: "posted",           label: "Live",      color: "#00DD88" },
  { value: "failed",           label: "Failed",    color: "#FF3B47" },
];

const mono9: React.CSSProperties = { fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f" };

export default function ContentPage() {
  const [filter, setFilter] = useState<ContentStatus | "all">("all");
  const { data: content, mutate } = useSWR(["content", filter], () =>
    listContent({ status: filter === "all" ? undefined : filter, limit: 50 })
  );

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
          <div style={{ ...mono9, marginBottom: 5 }}>Library</div>
          <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 40, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>CONTENT</div>
        </div>
        <div style={{ ...mono9 }}>{content?.length ?? 0} items</div>
      </div>

      <div style={{ padding: "32px 32px", maxWidth: 1200, margin: "0 auto" }}>

        {/* Filter bar */}
        <div style={{ display: "flex", gap: 8, marginBottom: 28, overflowX: "auto", paddingBottom: 4 }}>
          {FILTERS.map(({ value, label, color }) => {
            const active = filter === value;
            return (
              <button key={value} onClick={() => setFilter(value)} style={{
                flexShrink: 0,
                display: "inline-flex", alignItems: "center", gap: 7,
                padding: "7px 14px", borderRadius: 8, minHeight: 36,
                background: active ? `${color}18` : "rgba(255,255,255,0.02)",
                border: `1px solid ${active ? `${color}55` : "rgba(255,255,255,0.08)"}`,
                color: active ? "#f5f5f7" : "#56565f",
                fontSize: 12, fontWeight: 500, letterSpacing: "-0.01em",
                cursor: "pointer", transition: "all 0.15s",
              }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, boxShadow: active ? `0 0 6px ${color}` : "none", flexShrink: 0 }} />
                {label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        {!content ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[0,1,2,3,4,5].map(i => <div key={i} className="shimmer" style={{ height: 88, borderRadius: 14 }} />)}
          </div>
        ) : content.length === 0 ? (
          <div style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: "72px 32px", textAlign: "center" }}>
            <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 44, color: "#f5f5f7", letterSpacing: "0.04em", marginBottom: 10 }}>NOTHING HERE</div>
            <div style={{ fontSize: 13, color: "#56565f", lineHeight: 1.6 }}>Try a different filter, or compose from the dashboard.</div>
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
    </div>
  );
}
