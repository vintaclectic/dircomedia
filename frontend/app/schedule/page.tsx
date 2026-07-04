"use client";

import useSWR from "swr";
import { listSchedules } from "@/lib/api";
import { format, isPast } from "date-fns";
import type { Schedule } from "@/lib/types";

const mono9: React.CSSProperties = { fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f" };

function Row({ s }: { s: Schedule }) {
  const past = isPast(new Date(s.scheduled_at));
  const accent = s.is_posted ? "#00DD88" : past ? "#FF3B47" : "#3D8BFF";
  return (
    <div style={{
      background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 12, padding: "16px 20px",
      display: "flex", alignItems: "center", gap: 16,
      boxShadow: `inset 3px 0 0 0 ${accent}`,
    }}>
      <div style={{ flexShrink: 0 }}>
        <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 28, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>
          {format(new Date(s.scheduled_at), "dd")}
        </div>
        <div style={{ ...mono9, marginTop: 4 }}>{format(new Date(s.scheduled_at), "MMM")}</div>
      </div>
      <div style={{ width: 1, height: 36, background: "rgba(255,255,255,0.07)", flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#f5f5f7", marginBottom: 3, letterSpacing: "-0.01em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {s.content_id}
        </div>
        <div style={{ ...mono9 }}>{format(new Date(s.scheduled_at), "HH:mm")} · {s.platforms.join(", ")}</div>
      </div>
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "4px 10px", borderRadius: 6,
        background: `${accent}18`, border: `1px solid ${accent}44`,
      }}>
        <div style={{ width: 5, height: 5, borderRadius: "50%", background: accent, boxShadow: `0 0 5px ${accent}` }} />
        <span style={{ ...mono9, color: accent }}>{s.is_posted ? "Posted" : past ? "Missed" : "Upcoming"}</span>
      </div>
    </div>
  );
}

export default function SchedulePage() {
  // upcoming_only=false → everything; derive the three buckets locally.
  const { data: all } = useSWR("schedules-all", () => listSchedules(false));

  const posted   = all?.filter(s => s.is_posted) ?? [];
  const upcoming = all?.filter(s => !s.is_posted && !isPast(new Date(s.scheduled_at))) ?? [];
  const missed   = all?.filter(s => !s.is_posted && isPast(new Date(s.scheduled_at))) ?? [];

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
          <div style={{ ...mono9, marginBottom: 5 }}>Queue</div>
          <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 40, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>SCHEDULE</div>
        </div>
        <div style={{ display: "flex", gap: 20 }}>
          {[
            { label: "Upcoming", value: upcoming.length, color: "#3D8BFF" },
            { label: "Posted",   value: posted?.length ?? 0, color: "#00DD88" },
            { label: "Missed",   value: missed.length, color: "#FF3B47" },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ textAlign: "right" }}>
              <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 28, lineHeight: 0.9, color, letterSpacing: "0.04em" }}>{value}</div>
              <div style={{ ...mono9, marginTop: 3 }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ padding: "32px 32px", maxWidth: 900, margin: "0 auto" }}>
        {!all ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[0,1,2,3].map(i => <div key={i} className="shimmer" style={{ height: 72, borderRadius: 12 }} />)}
          </div>
        ) : all.length === 0 ? (
          <div style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: "72px 32px", textAlign: "center" }}>
            <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 44, color: "#f5f5f7", letterSpacing: "0.04em", marginBottom: 10 }}>CLEAR QUEUE</div>
            <div style={{ fontSize: 13, color: "#56565f", lineHeight: 1.6 }}>No scheduled posts. Generate content and schedule it.</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {upcoming.length > 0 && (
              <div>
                <div style={{ ...mono9, marginBottom: 12 }}>Upcoming · {upcoming.length}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {upcoming.map(s => <Row key={s.id} s={s} />)}
                </div>
              </div>
            )}
            {missed.length > 0 && (
              <div>
                <div style={{ ...mono9, marginBottom: 12 }}>Missed · {missed.length}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {missed.map(s => <Row key={s.id} s={s} />)}
                </div>
              </div>
            )}
            {(posted?.length ?? 0) > 0 && (
              <div>
                <div style={{ ...mono9, marginBottom: 12 }}>Posted · {posted!.length}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {posted!.map(s => <Row key={s.id} s={s} />)}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
