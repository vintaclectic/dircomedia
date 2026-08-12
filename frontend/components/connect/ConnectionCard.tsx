"use client";
/**
 * ConnectionCard — one platform's health, in its own box (YH9AE4D).
 *
 * NO-COLLISION LAW, enforced structurally rather than by eyeballing:
 *  · The card is a vertical flex column. Every child is a block in normal flow,
 *    so nothing can land on top of anything else — there is no absolute
 *    positioning anywhere in this component.
 *  · The identity row uses a fixed-width glyph + `minWidth: 0` text column.
 *    Without minWidth:0 a long handle refuses to shrink and pushes the status
 *    pill out of the card — the classic flex overflow that only shows up at
 *    375px with real data.
 *  · The status pill sits in its own flex-shrink:0 cell and wraps to its own
 *    line on narrow screens (flexWrap on the header row) rather than overlapping
 *    the name.
 *  · Action buttons live in a wrapping flex row, every one min-height 44px.
 *  · Error text is clamped and breaks words, so a 500-char provider error grows
 *    the card downward instead of bleeding sideways.
 */
import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import type { PlatformConnection } from "@/lib/types";
import { PLATFORM_META, STATUS_META, formatExpiry } from "./platformMeta";

const mono: React.CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  letterSpacing: "0.18em",
  textTransform: "uppercase",
};

export function StatusPill({ status }: { status: PlatformConnection["status"] }) {
  const s = STATUS_META[status];
  const pulse = status === "connected" || status === "expiring";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        borderRadius: 20,
        background: `${s.color}18`,
        border: `1px solid ${s.color}44`,
        color: s.color,
        fontSize: 9.5,
        flexShrink: 0,
        whiteSpace: "nowrap",
        ...mono,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: s.color,
          boxShadow: `0 0 6px ${s.color}`,
          flexShrink: 0,
          animation: pulse ? "connPulse 2s ease-in-out infinite" : undefined,
        }}
      />
      {s.label}
      <style>{`@keyframes connPulse{0%,100%{opacity:1}50%{opacity:0.45}}`}</style>
    </span>
  );
}

export function PlatformGlyph({
  platform,
  size = 40,
}: {
  platform: PlatformConnection["platform"];
  size?: number;
}) {
  const meta = PLATFORM_META[platform];
  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        flexShrink: 0,
        borderRadius: 11,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: `${meta.color}14`,
        border: `1px solid ${meta.color}3a`,
        color: meta.color,
        fontFamily: "var(--font-display), sans-serif",
        fontSize: size * 0.45,
        lineHeight: 1,
        letterSpacing: "0.02em",
      }}
    >
      {meta.glyph}
    </div>
  );
}

/** Live countdown that re-renders on a cadence matched to what's left —
 *  every second under an hour, every minute otherwise. A 60-day token ticking
 *  every second would repaint 5 million times for no information gained. */
export function ExpiryCountdown({ conn }: { conn: PlatformConnection }) {
  const [, force] = useState(0);
  useEffect(() => {
    if (conn.expires_at === null) return;
    const remaining = conn.expires_at * 1000 - Date.now();
    const interval = remaining > 0 && remaining < 3600000 ? 1000 : 60000;
    const id = setInterval(() => force((n) => n + 1), interval);
    return () => clearInterval(id);
  }, [conn.expires_at]);

  return (
    <span style={{ fontSize: 11.5, color: "#8a8a98", letterSpacing: "-0.01em" }}>
      {formatExpiry(conn.expires_at, conn.status)}
    </span>
  );
}

export function ConnectionCard({
  conn,
  busy,
  onPrimary,
  actions,
  footer,
}: {
  conn: PlatformConnection;
  busy?: string | null;
  onPrimary?: () => void;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const meta = PLATFORM_META[conn.platform];
  const s = STATUS_META[conn.status];

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        padding: 16,
        borderRadius: 14,
        background: "rgba(255,255,255,0.035)",
        border: "1px solid rgba(255,255,255,0.09)",
        boxShadow: `inset 3px 0 0 0 ${s.color}`,
        // The card owns its width and never exceeds it. minWidth:0 lets it
        // shrink inside a grid track instead of forcing horizontal scroll.
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      {/* ── Row 1: identity + status. Wraps rather than overlaps. ── */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flexWrap: "wrap", minWidth: 0 }}>
        <PlatformGlyph platform={conn.platform} />

        {/* minWidth:0 is load-bearing — it lets long handles ellipsize instead
            of shoving the pill out of the card. */}
        <div style={{ flex: "1 1 120px", minWidth: 0, display: "flex", flexDirection: "column", gap: 3 }}>
          <div
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: "#f5f5f7",
              letterSpacing: "-0.015em",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {conn.label}
          </div>
          <div
            style={{
              fontSize: 11.5,
              color: conn.account_name ? "#8a8a98" : "#56565f",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {conn.account_name ? `@${conn.account_name}` : meta.blurb}
          </div>
        </div>

        <StatusPill status={conn.status} />
      </div>

      {/* ── Row 2: expiry + mode ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", minWidth: 0 }}>
        <ExpiryCountdown conn={conn} />
        {!conn.app_configured && conn.status === "disconnected" && (
          <span style={{ fontSize: 9, color: "#FFB020", ...mono }}>Setup needed</span>
        )}
        {conn.mode === "manual" && (
          <span style={{ fontSize: 9, color: "#56565f", ...mono }}>Guided setup</span>
        )}
      </div>

      {/* ── Row 3: error, if any. Grows downward, never sideways. ── */}
      {conn.last_error && (
        <div
          style={{
            padding: "9px 11px",
            borderRadius: 9,
            background: "rgba(255,59,71,0.07)",
            border: "1px solid rgba(255,59,71,0.24)",
            color: "#FF8A92",
            fontSize: 11.5,
            lineHeight: 1.5,
            overflowWrap: "anywhere",
            wordBreak: "break-word",
            display: "-webkit-box",
            WebkitLineClamp: 4,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            minWidth: 0,
          }}
        >
          {conn.last_error}
        </div>
      )}

      {/* ── Row 4: actions. Wrapping row, 44px targets. ── */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", minWidth: 0 }}>
        {onPrimary && (
          <button
            onClick={onPrimary}
            disabled={!!busy}
            style={{
              flex: "1 1 130px",
              minWidth: 0,
              minHeight: 44,
              padding: "0 16px",
              borderRadius: 10,
              border: `1px solid ${s.color}55`,
              background: `${s.color}16`,
              color: s.color,
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: "-0.01em",
              cursor: busy ? "wait" : "pointer",
              opacity: busy ? 0.55 : 1,
              transition: "background 0.18s, border-color 0.18s",
            }}
          >
            {busy || s.cta}
          </button>
        )}
        {actions}
      </div>

      {footer}
    </div>
  );
}

export function SecondaryButton({
  children,
  onClick,
  disabled,
  tone = "neutral",
  grow = false,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "neutral" | "danger";
  grow?: boolean;
}) {
  const color = tone === "danger" ? "#FF3B47" : "#8a8a98";
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        flex: grow ? "1 1 110px" : "0 1 auto",
        minWidth: 0,
        minHeight: 44,
        padding: "0 14px",
        borderRadius: 10,
        border: `1px solid ${tone === "danger" ? "rgba(255,59,71,0.3)" : "rgba(255,255,255,0.1)"}`,
        background: "transparent",
        color,
        fontSize: 12.5,
        fontWeight: 500,
        letterSpacing: "-0.01em",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.45 : 1,
        whiteSpace: "nowrap",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}
    >
      {children}
    </button>
  );
}

export function DocsLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        minHeight: 44,
        color: "#3D8BFF",
        fontSize: 12.5,
        letterSpacing: "-0.01em",
        overflowWrap: "anywhere",
        minWidth: 0,
      }}
    >
      <ExternalLink size={13} strokeWidth={1.9} style={{ flexShrink: 0 }} />
      <span style={{ minWidth: 0 }}>{label}</span>
    </a>
  );
}
