"use client";
/**
 * SCREEN 3 — Connection dashboard (/settings/connections). YH9AE4D.
 *
 * The health wall. Every platform's real state, live expiry countdowns, and the
 * four actions that fix things: Reconnect, Refresh Now, Test, Disconnect.
 *
 * Polls /status every 60s so a token renewed by the background worker shows up
 * without a manual reload — the countdown resets on its own and Vinta sees the
 * machine taking care of itself.
 *
 * NO-COLLISION: same auto-fit grid as Screen 1 (no media queries, no possible
 * breakpoint gap). Disconnect uses an INLINE two-tap confirm inside the card
 * rather than a modal — a modal over a card is exactly the overlay this codebase
 * forbids by default, and the inline confirm is faster on a phone anyway.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  RefreshCw, ShieldCheck, Radio, AlertTriangle, ArrowLeft,
} from "lucide-react";
import {
  getConnections, testConnection, refreshConnection, disconnectPlatform,
} from "@/lib/api";
import type { PlatformConnection } from "@/lib/types";
import { ConnectionCard, SecondaryButton } from "@/components/connect/ConnectionCard";
import { MercurioWidget } from "@/components/connect/MercurioWidget";
import { useOAuthPopup, cleanError } from "@/components/connect/useOAuthPopup";

const mono: React.CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  letterSpacing: "0.22em",
  textTransform: "uppercase",
};

const POLL_MS = 60_000;

export default function ConnectionsDashboard() {
  const [conns, setConns] = useState<PlatformConnection[] | null>(null);
  const [busy, setBusy] = useState<Record<string, string>>({});
  const [confirmKill, setConfirmKill] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setConns(await getConnections());
    } catch (e) {
      setNotice({ ok: false, text: e instanceof Error ? cleanError(e.message) : "Could not load connections." });
      setConns([]);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const { connect, connecting } = useOAuthPopup((r) => {
    setNotice({ ok: r.ok, text: r.message });
    load();
  });

  function setPlatformBusy(platform: string, label: string | null) {
    setBusy((b) => {
      const next = { ...b };
      if (label) next[platform] = label;
      else delete next[platform];
      return next;
    });
  }

  async function act(
    platform: string,
    label: string,
    fn: () => Promise<{ ok?: boolean; error?: string; account_name?: string | null; expires_in_days?: number | null; disconnected?: boolean }>,
    success: (r: Awaited<ReturnType<typeof fn>>) => string
  ) {
    setPlatformBusy(platform, label);
    try {
      const res = await fn();
      const ok = res.ok !== false;
      setNotice({ ok, text: ok ? success(res) : `${platform}: ${res.error}` });
    } catch (e) {
      setNotice({ ok: false, text: e instanceof Error ? cleanError(e.message) : `${label} failed.` });
    } finally {
      setPlatformBusy(platform, null);
      setConfirmKill(null);
      await load();
    }
  }

  const healthy = conns?.filter((c) => c.status === "connected").length ?? 0;
  const attention = conns?.filter(
    (c) => c.status === "expired" || c.status === "needs_reconnect"
  ).length ?? 0;
  const soon = conns?.filter((c) => c.status === "expiring").length ?? 0;

  return (
    <div
      style={{
        padding: "26px 18px calc(env(safe-area-inset-bottom, 0px) + 96px)",
        maxWidth: 1080,
        margin: "0 auto",
        minWidth: 0,
      }}
    >
      <Link
        href="/settings"
        style={{
          display: "inline-flex", alignItems: "center", gap: 7, minHeight: 44,
          color: "#8a8a98", fontSize: 13, marginBottom: 6,
        }}
      >
        <ArrowLeft size={15} strokeWidth={1.9} />
        Settings
      </Link>

      <header style={{ marginBottom: 20, minWidth: 0 }}>
        <div style={{ ...mono, fontSize: 9, color: "#36363f", marginBottom: 8 }}>
          Connection health
        </div>
        <h1
          className="display"
          style={{ fontSize: "clamp(28px, 7vw, 44px)", margin: "0 0 10px", color: "#f5f5f7" }}
        >
          Your rails
        </h1>
        <p
          style={{
            margin: 0, fontSize: 14, lineHeight: 1.6, color: "#8a8a98",
            maxWidth: 620, overflowWrap: "anywhere",
          }}
        >
          Every connected account, its real state, and how long it has left. Tokens renew
          themselves every six hours — you only ever act when a card turns red.
        </p>
      </header>

      {/* ── Stat row: three separate boxes in a wrapping flex row ── */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 18, minWidth: 0 }}>
        {[
          { label: "Healthy", value: healthy, color: "#00DD88", icon: ShieldCheck },
          { label: "Expiring", value: soon, color: "#FFB020", icon: RefreshCw },
          { label: "Needs you", value: attention, color: attention > 0 ? "#FF3B47" : "#56565f", icon: AlertTriangle },
        ].map(({ label, value, color, icon: Icon }) => (
          <div
            key={label}
            style={{
              flex: "1 1 130px",
              minWidth: 0,
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "11px 13px",
              borderRadius: 12,
              background: "rgba(255,255,255,0.035)",
              border: "1px solid rgba(255,255,255,0.09)",
            }}
          >
            <Icon size={16} strokeWidth={1.9} style={{ flexShrink: 0, color }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 17, color, lineHeight: 1.1 }}>
                {conns === null ? "—" : value}
              </div>
              <div style={{ ...mono, fontSize: 8.5, color: "#56565f", marginTop: 3, whiteSpace: "nowrap" }}>
                {label}
              </div>
            </div>
          </div>
        ))}
      </div>

      {notice && (
        <div
          style={{
            display: "flex", gap: 10, alignItems: "flex-start",
            padding: "11px 13px", borderRadius: 11, marginBottom: 18,
            background: notice.ok ? "rgba(0,221,136,0.07)" : "rgba(255,59,71,0.07)",
            border: `1px solid ${notice.ok ? "rgba(0,221,136,0.26)" : "rgba(255,59,71,0.26)"}`,
            color: notice.ok ? "#7ff0bd" : "#FF8A92",
            fontSize: 12.5, lineHeight: 1.55, minWidth: 0, overflowWrap: "anywhere",
          }}
        >
          <span style={{ flex: 1, minWidth: 0 }}>{notice.text}</span>
          <button
            onClick={() => setNotice(null)}
            aria-label="Dismiss"
            style={{
              flexShrink: 0, minWidth: 44, minHeight: 44, marginTop: -10, marginRight: -6,
              color: "inherit", opacity: 0.7, cursor: "pointer", background: "transparent",
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── The wall ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))",
          gap: 14,
          minWidth: 0,
        }}
      >
        {conns === null &&
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="shimmer" style={{ height: 190, borderRadius: 14, minWidth: 0 }} />
          ))}

        {conns?.map((conn) => {
          const platformBusy = busy[conn.platform] || (connecting === conn.platform ? "Connecting…" : null);
          const live = conn.status !== "disconnected";
          const canRefresh = live && conn.status !== "connected";
          const killing = confirmKill === conn.platform;

          return (
            <ConnectionCard
              key={conn.platform}
              conn={conn}
              busy={platformBusy}
              onPrimary={() => {
                if (conn.status === "connected") {
                  act(conn.platform, "Testing…", () => testConnection(conn.platform), (r) =>
                    `${conn.label} responded${r.account_name ? ` as @${r.account_name}` : ""}. Connection is live.`
                  );
                } else if (conn.mode === "oneclick" && conn.app_configured) {
                  connect(conn.platform);
                } else {
                  window.location.href = `/setup/connect/${conn.platform}`;
                }
              }}
              actions={
                <>
                  {canRefresh && (
                    <SecondaryButton
                      onClick={() =>
                        act(conn.platform, "Refreshing…", () => refreshConnection(conn.platform), (r) =>
                          `${conn.label} refreshed${
                            r.expires_in_days != null ? ` — ${r.expires_in_days} days of life` : ""
                          }.`
                        )
                      }
                      disabled={!!platformBusy}
                    >
                      Refresh now
                    </SecondaryButton>
                  )}

                  {live && !killing && (
                    <SecondaryButton
                      tone="danger"
                      onClick={() => setConfirmKill(conn.platform)}
                      disabled={!!platformBusy}
                    >
                      Disconnect
                    </SecondaryButton>
                  )}

                  {/* Two-tap confirm, INLINE. No modal, no overlay, no collision. */}
                  {killing && (
                    <>
                      <SecondaryButton
                        tone="danger"
                        grow
                        onClick={() =>
                          act(conn.platform, "Disconnecting…", () => disconnectPlatform(conn.platform), () =>
                            `${conn.label} disconnected. The stored token was deleted.`
                          )
                        }
                        disabled={!!platformBusy}
                      >
                        Confirm delete
                      </SecondaryButton>
                      <SecondaryButton onClick={() => setConfirmKill(null)}>Cancel</SecondaryButton>
                    </>
                  )}
                </>
              }
              footer={
                killing ? (
                  <p
                    style={{
                      margin: 0, fontSize: 11.5, lineHeight: 1.55, color: "#FF8A92",
                      overflowWrap: "anywhere", minWidth: 0,
                    }}
                  >
                    This deletes the stored token outright. You&apos;ll need to reconnect to post
                    to {conn.label} again.
                  </p>
                ) : null
              }
            />
          );
        })}
      </div>

      <div style={{ marginTop: 24, display: "flex", gap: 10, flexWrap: "wrap", minWidth: 0 }}>
        <Link href="/setup/connect" style={{ minWidth: 0, display: "flex" }}>
          <SecondaryButton>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Radio size={13} strokeWidth={1.9} />
              Add a platform
            </span>
          </SecondaryButton>
        </Link>
        <SecondaryButton onClick={load}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <RefreshCw size={13} strokeWidth={1.9} />
            Refresh status
          </span>
        </SecondaryButton>
      </div>

      <MercurioWidget />
    </div>
  );
}
