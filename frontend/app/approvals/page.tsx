"use client";
/**
 * APPROVALS — the owner's veto seat over the Broadcast Spine.
 *
 * Everything the brain (or the worklog tap) wants to post lands here first.
 * 2-tap approve: tap APPROVE → tap CONFIRM. Nothing posts without Vinta.
 * Council decree 2026-07-04, Phase 1.
 */
import { useCallback, useEffect, useState } from "react";
import { Radio, Check, X, ShieldAlert } from "lucide-react";
import {
  listPendingBroadcasts,
  listBroadcasts,
  approveBroadcast,
  vetoBroadcast,
} from "@/lib/api";
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

const STATUS_COLORS: Record<BroadcastStatus, string> = {
  pending_approval: "#FFD700",
  approved: "#0055FF",
  posting: "#0055FF",
  posted: "#00DD88",
  partial: "#FF9900",
  failed: "#FF2222",
  vetoed: "#56565f",
};

const mono: React.CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  letterSpacing: "0.18em",
  textTransform: "uppercase",
};

function projectColor(slug: string): string {
  return PROJECT_COLORS[slug] || "#8a8a98";
}

function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function ApprovalsPage() {
  const [pending, setPending] = useState<Broadcast[]>([]);
  const [recent, setRecent] = useState<Broadcast[]>([]);
  const [confirming, setConfirming] = useState<string | null>(null); // 2-tap state
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([listPendingBroadcasts(), listBroadcasts(30)]);
      setPending(p);
      setRecent(r.filter(b => b.status !== "pending_approval"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reach the spine");
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15000);
    return () => clearInterval(t);
  }, [refresh]);

  const act = async (id: string, action: "approve" | "veto") => {
    setBusy(id);
    setConfirming(null);
    try {
      if (action === "approve") await approveBroadcast(id);
      else await vetoBroadcast(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ padding: "28px 28px 96px", maxWidth: 780, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
        <Radio size={22} strokeWidth={1.75} color="#FFD700" />
        <h1 style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 32, letterSpacing: "0.04em", margin: 0 }}>
          APPROVALS
        </h1>
        {pending.length > 0 && (
          <span style={{
            ...mono, fontSize: 10, color: "#020205", background: "#FFD700",
            borderRadius: 20, padding: "3px 10px", fontWeight: 700,
          }}>
            {pending.length} WAITING
          </span>
        )}
      </div>
      <p style={{ color: "#56565f", fontSize: 13, marginTop: 2, marginBottom: 26 }}>
        Nothing posts without your word. Two taps to release, one to kill.
      </p>

      {error && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8, padding: "10px 14px",
          border: "1px solid rgba(255,34,34,0.4)", borderRadius: 10,
          background: "rgba(255,34,34,0.07)", color: "#ff8888", fontSize: 12, marginBottom: 18,
        }}>
          <ShieldAlert size={14} /> {error}
        </div>
      )}

      {/* Pending queue */}
      {pending.length === 0 && !error && (
        <div style={{
          padding: "42px 20px", textAlign: "center", border: "1px dashed rgba(255,255,255,0.1)",
          borderRadius: 14, color: "#36363f",
        }}>
          <div style={{ ...mono, fontSize: 10, marginBottom: 6 }}>Queue clear</div>
          <div style={{ fontSize: 13, color: "#56565f" }}>The brain has nothing waiting on you.</div>
        </div>
      )}

      {pending.map(b => {
        const color = projectColor(b.project_slug);
        const isConfirming = confirming === b.id;
        const isBusy = busy === b.id;
        return (
          <div key={b.id} style={{
            border: `1px solid ${isConfirming ? "rgba(255,215,0,0.5)" : "rgba(255,255,255,0.09)"}`,
            borderLeft: `3px solid ${color}`,
            borderRadius: 14, padding: "16px 18px", marginBottom: 14,
            background: "#080810", transition: "border-color 0.2s",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, boxShadow: `0 0 8px ${color}99` }} />
              <span style={{ ...mono, fontSize: 9.5, color }}>{b.project_slug}</span>
              <span style={{ ...mono, fontSize: 9, color: "#56565f" }}>{b.kind}</span>
              <span style={{ ...mono, fontSize: 9, color: "#36363f" }}>via {b.source}</span>
              <span style={{ ...mono, fontSize: 9, color: "#36363f", marginLeft: "auto" }}>{timeAgo(b.created_at)}</span>
            </div>

            {b.title && <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{b.title}</div>}
            {b.body && <div style={{ fontSize: 13, color: "#b8b8c2", whiteSpace: "pre-wrap", lineHeight: 1.55 }}>{b.body}</div>}

            <div style={{ display: "flex", gap: 6, marginTop: 12, flexWrap: "wrap" }}>
              {b.platforms.map(p => (
                <span key={p} style={{
                  ...mono, fontSize: 8.5, color: "#8a8a98",
                  border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, padding: "3px 8px",
                }}>{p}</span>
              ))}
            </div>

            {/* 2-tap approve / 1-tap veto */}
            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              {!isConfirming ? (
                <button
                  disabled={isBusy}
                  onClick={() => setConfirming(b.id)}
                  style={{
                    flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
                    padding: "11px 0", borderRadius: 10, border: "1px solid rgba(0,221,136,0.35)",
                    background: "rgba(0,221,136,0.08)", color: "#00DD88", fontSize: 13, fontWeight: 600,
                    cursor: "pointer",
                  }}>
                  <Check size={15} /> APPROVE
                </button>
              ) : (
                <button
                  disabled={isBusy}
                  onClick={() => act(b.id, "approve")}
                  style={{
                    flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
                    padding: "11px 0", borderRadius: 10, border: "none",
                    background: "#00DD88", color: "#020205", fontSize: 13, fontWeight: 800,
                    cursor: "pointer",
                  }}>
                  {isBusy ? "RELEASING…" : `CONFIRM → ${b.platforms.length} PLATFORM${b.platforms.length > 1 ? "S" : ""}`}
                </button>
              )}
              <button
                disabled={isBusy}
                onClick={() => (isConfirming ? setConfirming(null) : act(b.id, "veto"))}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                  padding: "11px 18px", borderRadius: 10,
                  border: "1px solid rgba(255,34,34,0.3)", background: "rgba(255,34,34,0.06)",
                  color: "#ff6666", fontSize: 13, fontWeight: 600, cursor: "pointer",
                }}>
                <X size={15} /> {isConfirming ? "BACK" : "VETO"}
              </button>
            </div>
          </div>
        );
      })}

      {/* Recent history — the beginning of the archive wall */}
      {recent.length > 0 && (
        <>
          <div style={{ ...mono, fontSize: 9.5, color: "#36363f", margin: "34px 0 12px" }}>Recent broadcasts</div>
          {recent.map(b => (
            <div key={b.id} style={{
              display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
              border: "1px solid rgba(255,255,255,0.05)", borderRadius: 10, marginBottom: 8,
              background: "rgba(255,255,255,0.015)",
            }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: projectColor(b.project_slug), flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: "#8a8a98", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                {b.title || b.body || "—"}
              </span>
              <span style={{ ...mono, fontSize: 8.5, color: STATUS_COLORS[b.status], flexShrink: 0 }}>
                {b.status.replace("_", " ")}
              </span>
              <span style={{ ...mono, fontSize: 8.5, color: "#36363f", flexShrink: 0 }}>{timeAgo(b.created_at)}</span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
