"use client";
/**
 * THE LIVING ARCHIVE WALL — Phase 3 (council decree 2026-07-04).
 *
 * Grateful Dead law: the archive is the community's treasure. Every broadcast
 * ever made is a collectible artifact — the tour never ends, the tape keeps
 * rolling. This wall is the machine's memory made visible.
 */
import { useEffect, useMemo, useState } from "react";
import { Archive } from "lucide-react";
import { listBroadcasts } from "@/lib/api";
import type { Broadcast, BroadcastStatus } from "@/lib/types";

const PROJECT_COLORS: Record<string, string> = {
  dirco: "#0055FF",
  "dirhaven-rp": "#FF2222",
  dirhaven_rp: "#FF2222",
  "dirhaven-app": "#00DD88",
  dirhaven_app: "#00DD88",
  dirmegle: "#FF5500",
  medaled: "#FFD700",
  agentis: "#7C3AED",
  vintinuum: "#F0287A",
};

const STATUS_META: Record<BroadcastStatus, { color: string; label: string }> = {
  posted: { color: "#00DD88", label: "POSTED" },
  partial: { color: "#FF9900", label: "PARTIAL" },
  failed: { color: "#FF2222", label: "FAILED" },
  vetoed: { color: "#56565f", label: "VETOED" },
  pending_approval: { color: "#FFD700", label: "PENDING" },
  approved: { color: "#0055FF", label: "QUEUED" },
  posting: { color: "#0055FF", label: "POSTING" },
};

const mono: React.CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  letterSpacing: "0.18em",
  textTransform: "uppercase",
};

export default function ArchivePage() {
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      listBroadcasts(200)
        .then((b) => { setBroadcasts(b); setError(null); })
        .catch((e) => setError(e instanceof Error ? e.message : "unreachable"));
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  const projects = useMemo(
    () => Array.from(new Set(broadcasts.map((b) => b.project_slug))).sort(),
    [broadcasts]
  );
  const shown = filter === "all" ? broadcasts : broadcasts.filter((b) => b.project_slug === filter);
  const postedCount = broadcasts.filter((b) => b.status === "posted" || b.status === "partial").length;

  return (
    <div style={{ padding: "28px 28px 96px", maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
        <Archive size={22} strokeWidth={1.75} color="#FFD700" />
        <h1 style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 32, letterSpacing: "0.04em", margin: 0 }}>
          THE ARCHIVE
        </h1>
        <span style={{ ...mono, fontSize: 10, color: "#56565f", marginLeft: "auto" }}>
          {postedCount} released · {broadcasts.length} artifacts
        </span>
      </div>
      <p style={{ color: "#56565f", fontSize: 13, marginTop: 2, marginBottom: 20 }}>
        Every broadcast this machine ever made. The tour never ends.
      </p>

      {/* Project filter chips */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
        {["all", ...projects].map((slug) => {
          const on = filter === slug;
          const c = slug === "all" ? "#f5f5f7" : PROJECT_COLORS[slug] || "#8a8a98";
          return (
            <button key={slug} onClick={() => setFilter(slug)} style={{
              ...mono, fontSize: 9, padding: "6px 12px", borderRadius: 20, cursor: "pointer",
              background: on ? `${c}22` : "transparent",
              border: `1px solid ${on ? `${c}88` : "rgba(255,255,255,0.1)"}`,
              color: on ? c : "#56565f",
            }}>
              {slug}
            </button>
          );
        })}
      </div>

      {error && (
        <div style={{ color: "#ff8888", fontSize: 12, marginBottom: 16 }}>spine unreachable: {error}</div>
      )}

      {shown.length === 0 && !error && (
        <div style={{
          padding: "60px 20px", textAlign: "center",
          border: "1px dashed rgba(255,255,255,0.1)", borderRadius: 14, color: "#36363f",
        }}>
          <div style={{ ...mono, fontSize: 10, marginBottom: 6 }}>The wall awaits its first artifact</div>
          <div style={{ fontSize: 13, color: "#56565f" }}>Approve a broadcast and it lives here forever.</div>
        </div>
      )}

      {/* The wall */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14 }}>
        {shown.map((b) => {
          const color = PROJECT_COLORS[b.project_slug] || "#8a8a98";
          const status = STATUS_META[b.status] || STATUS_META.pending_approval;
          const platformsHit = b.results
            ? Object.entries(b.results).filter(([, r]) => !(r as Record<string, unknown>)?.error).map(([p]) => p)
            : [];
          return (
            <div key={b.id} style={{
              border: "1px solid rgba(255,255,255,0.08)",
              borderTop: `2px solid ${color}`,
              borderRadius: 12, padding: "14px 16px", background: "#080810",
              display: "flex", flexDirection: "column", gap: 8,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, boxShadow: `0 0 8px ${color}99` }} />
                <span style={{ ...mono, fontSize: 9, color }}>{b.project_slug}</span>
                <span style={{ ...mono, fontSize: 8.5, color: "#36363f" }}>{b.kind}</span>
                <span style={{ ...mono, fontSize: 8.5, color: status.color, marginLeft: "auto" }}>{status.label}</span>
              </div>

              {b.title && <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3 }}>{b.title}</div>}
              {b.body && (
                <div style={{
                  fontSize: 12, color: "#a0a0ac", lineHeight: 1.5,
                  display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", overflow: "hidden",
                }}>
                  {b.body}
                </div>
              )}

              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: "auto", flexWrap: "wrap" }}>
                {b.platforms.map((p) => (
                  <span key={p} style={{
                    ...mono, fontSize: 8, padding: "2px 7px", borderRadius: 5,
                    border: `1px solid ${platformsHit.includes(p) ? "rgba(0,221,136,0.4)" : "rgba(255,255,255,0.1)"}`,
                    color: platformsHit.includes(p) ? "#00DD88" : "#56565f",
                  }}>{p}</span>
                ))}
                <span style={{ ...mono, fontSize: 8, color: "#36363f", marginLeft: "auto" }}>
                  {new Date(b.created_at).toLocaleDateString()} · {b.source}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
