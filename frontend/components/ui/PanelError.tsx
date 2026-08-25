"use client";

import { useState } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { ApiError } from "@/lib/api";

/**
 * PanelError — the banner that makes a broken fetch impossible to mistake for
 * an empty list (H3442HM, 2026-08-25).
 *
 * Why this exists: the HB6H3YW build-time localhost leak took every panel's
 * data to zero, and because SWR's `error` channel was ignored, each panel
 * rendered its friendly empty state ("EMPTY STAGE", "NOTHING HERE", "CLEAR
 * QUEUE"). A total outage was visually identical to a quiet week. Now every
 * data panel renders THIS instead when the fetch failed, and the empty state
 * is only ever reached on a genuine 200-with-zero-rows.
 *
 * No-Collision Law: this is an in-flow block, never absolute/fixed. It owns a
 * defined box, wraps long provider text with overflow-wrap + a line clamp, and
 * grows downward only — it can never land on top of a neighbour at any width.
 */
export function PanelError({
  error,
  onRetry,
  compact = false,
}: {
  error: unknown;
  onRetry?: () => void | Promise<unknown>;
  compact?: boolean;
}) {
  const [retrying, setRetrying] = useState(false);

  const api = error instanceof ApiError ? error : null;
  const headline = api ? api.headline : "Something went wrong";
  const detail = api
    ? api.detail
    : error instanceof Error
    ? error.message
    : String(error ?? "Unknown error");

  const retry = async () => {
    if (!onRetry || retrying) return;
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div
      role="alert"
      style={{
        background: "rgba(255,59,71,0.06)",
        border: "1px solid rgba(255,59,71,0.28)",
        borderRadius: 14,
        padding: compact ? "12px 14px" : "18px 20px",
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        // box discipline: never wider than the parent, never overlaps a sibling
        maxWidth: "100%",
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      <AlertTriangle
        size={compact ? 14 : 16}
        color="#FF3B47"
        style={{ flexShrink: 0, marginTop: 2 }}
        aria-hidden
      />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontFamily: "var(--font-mono), monospace",
            fontSize: compact ? 10 : 11,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "#FF3B47",
            marginBottom: 6,
          }}
        >
          {headline}
        </div>
        <div
          style={{
            fontSize: compact ? 11.5 : 12.5,
            color: "#c4c4ce",
            lineHeight: 1.55,
            overflowWrap: "anywhere",
            wordBreak: "break-word",
            display: "-webkit-box",
            WebkitLineClamp: 4,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {detail}
        </div>

        {onRetry && (
          <button
            onClick={retry}
            disabled={retrying}
            style={{
              marginTop: 12,
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "7px 13px",
              minHeight: 36, // touch target — mobile-first mandate
              borderRadius: 8,
              background: "rgba(255,59,71,0.10)",
              border: "1px solid rgba(255,59,71,0.34)",
              color: "#f5f5f7",
              fontSize: 12,
              fontWeight: 500,
              cursor: retrying ? "default" : "pointer",
              opacity: retrying ? 0.6 : 1,
              transition: "all 0.15s",
            }}
          >
            <RefreshCw
              size={12}
              style={retrying ? { animation: "spin 0.9s linear infinite" } : undefined}
              aria-hidden
            />
            {retrying ? "Retrying…" : "Retry"}
          </button>
        )}
      </div>

      <style>{`@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
