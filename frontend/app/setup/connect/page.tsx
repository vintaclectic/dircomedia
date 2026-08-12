"use client";
/**
 * SCREEN 1 — Platform picker (/setup/connect). YH9AE4D.
 *
 * The wall of five. Every card is a grid cell with its own space; the grid uses
 * auto-fit/minmax so it goes 1-up at 375px and multi-column on desktop WITHOUT
 * a single media query — the browser reflows the tracks, so no breakpoint can
 * be missed and no two cards can ever share pixels.
 *
 * Bottom padding reserves the fixed mobile nav's height, the only fixed element
 * on this page — Mercurio sits in normal flow, so nothing floats over content.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ShieldCheck, RefreshCw, AlertTriangle } from "lucide-react";
import { getConnections, getEncryptionStatus } from "@/lib/api";
import type { PlatformConnection } from "@/lib/types";
import { ConnectionCard, SecondaryButton } from "@/components/connect/ConnectionCard";
import { MercurioWidget } from "@/components/connect/MercurioWidget";
import { useOAuthPopup, cleanError } from "@/components/connect/useOAuthPopup";
import { STATUS_META } from "@/components/connect/platformMeta";

const mono: React.CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  letterSpacing: "0.22em",
  textTransform: "uppercase",
};

export default function ConnectPickerPage() {
  const router = useRouter();
  const [conns, setConns] = useState<PlatformConnection[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [encryptionOk, setEncryptionOk] = useState<boolean | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getConnections();
      setConns(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? cleanError(e.message) : "Could not load connections.");
      setConns([]);
    }
  }, []);

  useEffect(() => {
    load();
    getEncryptionStatus()
      .then((r) => setEncryptionOk(r.configured))
      .catch(() => setEncryptionOk(null));
  }, [load]);

  const { connect, connecting } = useOAuthPopup((r) => {
    setNotice({ ok: r.ok, text: r.message });
    load();
  });

  const connectedCount = conns?.filter((c) => c.status === "connected").length ?? 0;
  const total = conns?.length ?? 5;

  return (
    <div
      style={{
        // Bottom padding reserves the fixed mobile nav's height (~67px) plus
        // safe-area inset and a breathing gap. Mercurio is in normal flow, so
        // the nav is the ONLY fixed element this page must clear.
        padding: "26px 18px calc(env(safe-area-inset-bottom, 0px) + 96px)",
        maxWidth: 1080,
        margin: "0 auto",
        minWidth: 0,
      }}
    >
      {/* ── Header ── */}
      <header style={{ marginBottom: 22, minWidth: 0 }}>
        <div style={{ ...mono, fontSize: 9, color: "#36363f", marginBottom: 8 }}>
          Step 1 of 2 · Connect
        </div>
        <h1
          className="display"
          style={{ fontSize: "clamp(28px, 7vw, 44px)", margin: "0 0 10px", color: "#f5f5f7" }}
        >
          Connect your accounts
        </h1>
        <p
          style={{
            margin: 0,
            fontSize: 14,
            lineHeight: 1.6,
            color: "#8a8a98",
            maxWidth: 620,
            overflowWrap: "anywhere",
          }}
        >
          Five platforms, one wall. Connect the ones you want to post to — each takes a
          couple of minutes, and Mercurio is here if a step gets confusing.
        </p>
      </header>

      {/* ── Progress + encryption assurance ── */}
      <div
        style={{
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
          alignItems: "center",
          marginBottom: 20,
          minWidth: 0,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 12px",
            borderRadius: 10,
            background: "rgba(255,255,255,0.035)",
            border: "1px solid rgba(255,255,255,0.09)",
            minWidth: 0,
          }}
        >
          <span style={{ ...mono, fontSize: 9, color: "#56565f", whiteSpace: "nowrap" }}>
            Connected
          </span>
          <span
            style={{
              fontFamily: "var(--font-mono), monospace",
              fontSize: 13,
              color: connectedCount > 0 ? "#00DD88" : "#56565f",
            }}
          >
            {connectedCount}/{total}
          </span>
        </div>

        {encryptionOk === true && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "8px 12px",
              borderRadius: 10,
              background: "rgba(0,221,136,0.07)",
              border: "1px solid rgba(0,221,136,0.24)",
              color: "#00DD88",
              minWidth: 0,
            }}
          >
            <ShieldCheck size={13} strokeWidth={2} style={{ flexShrink: 0 }} />
            <span style={{ ...mono, fontSize: 9 }}>Tokens encrypted</span>
          </div>
        )}

        {encryptionOk === false && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "8px 12px",
              borderRadius: 10,
              background: "rgba(255,59,71,0.08)",
              border: "1px solid rgba(255,59,71,0.3)",
              color: "#FF8A92",
              minWidth: 0,
              maxWidth: "100%",
            }}
          >
            <AlertTriangle size={13} strokeWidth={2} style={{ flexShrink: 0 }} />
            <span style={{ fontSize: 11.5, overflowWrap: "anywhere" }}>
              CREDENTIAL_ENCRYPTION_KEY is missing — connecting is disabled until it&apos;s set.
            </span>
          </div>
        )}

        <SecondaryButton onClick={load}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <RefreshCw size={13} strokeWidth={1.9} />
            Refresh
          </span>
        </SecondaryButton>
      </div>

      {/* ── Notice (in flow — never a floating toast that could overlap) ── */}
      {notice && (
        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            padding: "11px 13px",
            borderRadius: 11,
            marginBottom: 18,
            background: notice.ok ? "rgba(0,221,136,0.07)" : "rgba(255,176,32,0.07)",
            border: `1px solid ${notice.ok ? "rgba(0,221,136,0.26)" : "rgba(255,176,32,0.26)"}`,
            color: notice.ok ? "#7ff0bd" : "#FFD79A",
            fontSize: 12.5,
            lineHeight: 1.55,
            minWidth: 0,
            overflowWrap: "anywhere",
          }}
        >
          <span style={{ flex: 1, minWidth: 0 }}>{notice.text}</span>
          <button
            onClick={() => setNotice(null)}
            aria-label="Dismiss"
            style={{
              flexShrink: 0,
              minWidth: 44,
              minHeight: 44,
              marginTop: -10,
              marginRight: -6,
              color: "inherit",
              opacity: 0.7,
              cursor: "pointer",
              background: "transparent",
            }}
          >
            ✕
          </button>
        </div>
      )}

      {error && (
        <div
          style={{
            padding: "11px 13px",
            borderRadius: 11,
            marginBottom: 18,
            background: "rgba(255,59,71,0.07)",
            border: "1px solid rgba(255,59,71,0.26)",
            color: "#FF8A92",
            fontSize: 12.5,
            lineHeight: 1.55,
            overflowWrap: "anywhere",
            minWidth: 0,
          }}
        >
          {error}
        </div>
      )}

      {/* ── The wall. auto-fit tracks = responsive with zero media queries. ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 290px), 1fr))",
          gap: 14,
          minWidth: 0,
        }}
      >
        {conns === null &&
          Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="shimmer"
              style={{ height: 168, borderRadius: 14, minWidth: 0 }}
            />
          ))}

        {conns?.map((conn) => {
          const isConnecting = connecting === conn.platform;
          // One-click is only offered when the developer app exists. Otherwise
          // the primary action routes to the guided setup that creates it —
          // never a button that opens a popup destined to fail.
          const canOneClick =
            conn.mode === "oneclick" && conn.app_configured && encryptionOk !== false;

          return (
            <ConnectionCard
              key={conn.platform}
              conn={conn}
              busy={isConnecting ? "Connecting…" : null}
              onPrimary={() => {
                if (conn.status === "connected") {
                  router.push(`/settings/connections`);
                } else if (canOneClick) {
                  connect(conn.platform);
                } else {
                  router.push(`/setup/connect/${conn.platform}`);
                }
              }}
              actions={
                <Link
                  href={`/setup/connect/${conn.platform}`}
                  style={{ flex: "0 1 auto", minWidth: 0, display: "flex" }}
                >
                  <SecondaryButton>
                    {conn.app_configured ? "Setup guide" : "Set up"}
                  </SecondaryButton>
                </Link>
              }
            />
          );
        })}
      </div>

      {/* ── Footer link to the dashboard ── */}
      <div style={{ marginTop: 24, display: "flex", gap: 10, flexWrap: "wrap", minWidth: 0 }}>
        <Link href="/settings/connections" style={{ minWidth: 0, display: "flex" }}>
          <SecondaryButton>Go to connection dashboard</SecondaryButton>
        </Link>
      </div>

      <MercurioWidget />
    </div>
  );
}
