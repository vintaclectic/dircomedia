import type { ContentStatus } from "@/lib/types";

const STATUS: Record<ContentStatus, { label: string; color: string }> = {
  draft:            { label: "Draft",     color: "#56565f" },
  pending_approval: { label: "Review",    color: "#FFB020" },
  approved:         { label: "Approved",  color: "#00DD88" },
  scheduled:        { label: "Scheduled", color: "#3D8BFF" },
  posted:           { label: "Live",      color: "#00DD88" },
  failed:           { label: "Failed",    color: "#FF3B47" },
};

export function StatusBadge({ status }: { status: ContentStatus }) {
  const { label, color } = STATUS[status] ?? { label: status, color: "#56565f" };
  const pulse = status === "posted" || status === "scheduled" || status === "pending_approval";

  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "3px 9px", borderRadius: 20,
      background: `${color}18`, border: `1px solid ${color}44`,
      fontFamily: "var(--font-mono), monospace", fontSize: 9,
      letterSpacing: "0.18em", textTransform: "uppercase", color,
    }}>
      <span style={{ position: "relative", display: "inline-flex", width: 6, height: 6, flexShrink: 0 }}>
        <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: color, boxShadow: `0 0 6px ${color}` }} />
        {pulse && <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: color, opacity: 0.6, animation: "ping 1.4s ease-out infinite" }} />}
      </span>
      {label}
      <style>{`@keyframes ping{0%{transform:scale(1);opacity:0.6}75%,100%{transform:scale(2);opacity:0}}`}</style>
    </span>
  );
}
