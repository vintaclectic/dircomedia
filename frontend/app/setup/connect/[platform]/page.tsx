"use client";
/**
 * SCREEN 2 — Per-platform guided setup (/setup/connect/{platform}). YH9AE4D.
 *
 * Two lanes, chosen by the BACKEND's `mode` field, never guessed here:
 *   Mode B (oneclick — X, Reddit, Pinterest): register the dev app, then one
 *     Authorize button drives the OAuth popup.
 *   Mode A (manual — Instagram, TikTok): the same guided steps, ending in a
 *     token paste that is PROBED before it's accepted.
 * Manual paste is also offered as a fallback on one-click platforms, because a
 * wizard with no escape hatch is a wizard that strands you.
 *
 * NO-COLLISION: the whole page is a single-column flex stack. Numbered steps use
 * a fixed 28px badge column + minWidth:0 text column, so long instructions wrap
 * under themselves and never run beneath the number. Nothing is absolutely
 * positioned except Mercurio, which is placed clear of the fixed nav.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Check, ExternalLink, ShieldCheck } from "lucide-react";
import {
  getConnections, saveAppCredentials, saveManualToken, testConnection,
} from "@/lib/api";
import type { PlatformConnection, ConnectPlatform } from "@/lib/types";
import { PLATFORM_META, PLATFORM_ORDER, STATUS_META } from "@/components/connect/platformMeta";
import { PlatformGlyph, StatusPill, SecondaryButton, DocsLink } from "@/components/connect/ConnectionCard";
import { CopyField, SecretInput } from "@/components/connect/CopyField";
import { MercurioWidget } from "@/components/connect/MercurioWidget";
import { useOAuthPopup, cleanError } from "@/components/connect/useOAuthPopup";

const mono: React.CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  letterSpacing: "0.22em",
  textTransform: "uppercase",
};

function Section({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        padding: 16,
        borderRadius: 14,
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.08)",
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      <div style={{ minWidth: 0 }}>
        {eyebrow && (
          <div style={{ ...mono, fontSize: 9, color: "#36363f", marginBottom: 6 }}>{eyebrow}</div>
        )}
        <h2
          style={{
            margin: 0,
            fontSize: 15.5,
            fontWeight: 600,
            color: "#f5f5f7",
            letterSpacing: "-0.015em",
            overflowWrap: "anywhere",
          }}
        >
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

export default function PlatformSetupPage() {
  const params = useParams<{ platform: string }>();
  const router = useRouter();
  const platform = params.platform as ConnectPlatform;
  const valid = PLATFORM_ORDER.includes(platform);

  const [conns, setConns] = useState<PlatformConnection[] | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [refreshTok, setRefreshTok] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setConns(await getConnections());
    } catch (e) {
      setNotice({ ok: false, text: e instanceof Error ? cleanError(e.message) : "Could not load status." });
      setConns([]);
    }
  }, []);

  useEffect(() => {
    if (valid) load();
  }, [valid, load]);

  const { connect, connecting } = useOAuthPopup((r) => {
    setNotice({ ok: r.ok, text: r.message });
    load();
  });

  const conn = useMemo(
    () => conns?.find((c) => c.platform === platform) ?? null,
    [conns, platform]
  );
  const meta = valid ? PLATFORM_META[platform] : null;

  if (!valid || !meta) {
    return (
      <div style={{ padding: "40px 18px", maxWidth: 640, margin: "0 auto" }}>
        <h1 style={{ fontSize: 22, color: "#f5f5f7", margin: "0 0 12px" }}>Unknown platform</h1>
        <p style={{ color: "#8a8a98", fontSize: 14, margin: "0 0 20px" }}>
          &ldquo;{String(params.platform)}&rdquo; isn&apos;t one of the five connectable platforms.
        </p>
        <Link href="/setup/connect" style={{ display: "inline-flex" }}>
          <SecondaryButton>Back to platforms</SecondaryButton>
        </Link>
      </div>
    );
  }

  async function handleSaveApp() {
    if (!clientId.trim() || !clientSecret.trim()) {
      setNotice({ ok: false, text: "Both the client ID and client secret are required." });
      return;
    }
    setBusy("save-app");
    try {
      await saveAppCredentials(platform, clientId.trim(), clientSecret.trim());
      setClientId("");
      setClientSecret("");
      setNotice({
        ok: true,
        text: `${meta!.label} app credentials saved. You can authorize now.`,
      });
      await load();
    } catch (e) {
      setNotice({ ok: false, text: e instanceof Error ? cleanError(e.message) : "Save failed." });
    } finally {
      setBusy(null);
    }
  }

  async function handleSaveToken() {
    if (!accessToken.trim()) {
      setNotice({ ok: false, text: "An access token is required." });
      return;
    }
    setBusy("save-token");
    try {
      const res = await saveManualToken(platform, {
        access_token: accessToken.trim(),
        refresh_token: refreshTok.trim() || undefined,
        expires_in_days: meta!.defaultExpiryDays,
      });
      setAccessToken("");
      setRefreshTok("");
      setNotice({
        ok: true,
        text: res.account_name
          ? `Connected as @${res.account_name}. ${meta!.label} is live.`
          : `${meta!.label} connected and verified.`,
      });
      await load();
    } catch (e) {
      setNotice({ ok: false, text: e instanceof Error ? cleanError(e.message) : "Could not save that token." });
    } finally {
      setBusy(null);
    }
  }

  async function handleTest() {
    setBusy("test");
    try {
      const res = await testConnection(platform);
      setNotice({
        ok: res.ok,
        text: res.ok
          ? `${meta!.label} responded${res.account_name ? ` as @${res.account_name}` : ""}. The connection works.`
          : `${meta!.label} test failed: ${res.error}`,
      });
      await load();
    } catch (e) {
      setNotice({ ok: false, text: e instanceof Error ? cleanError(e.message) : "Test failed." });
    } finally {
      setBusy(null);
    }
  }

  const isConnected = conn?.status === "connected";
  // The manual lane is ALWAYS offered — required for Instagram/TikTok, and an
  // escape hatch on the one-click platforms. A wizard with no fallback is a
  // wizard that strands you when a popup misbehaves.
  const showManualToken = true;

  return (
    <div
      style={{
        padding: "22px 18px calc(env(safe-area-inset-bottom, 0px) + 96px)",
        maxWidth: 720,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: 16,
        minWidth: 0,
      }}
    >
      {/* ── Back ── */}
      <Link
        href="/setup/connect"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          minHeight: 44,
          color: "#8a8a98",
          fontSize: 13,
          alignSelf: "flex-start",
        }}
      >
        <ArrowLeft size={15} strokeWidth={1.9} />
        All platforms
      </Link>

      {/* ── Header ── */}
      <header style={{ display: "flex", alignItems: "flex-start", gap: 13, flexWrap: "wrap", minWidth: 0 }}>
        <PlatformGlyph platform={platform} size={48} />
        <div style={{ flex: "1 1 160px", minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          <h1
            className="display"
            style={{ margin: 0, fontSize: "clamp(24px, 6vw, 34px)", color: "#f5f5f7" }}
          >
            Connect {meta.label}
          </h1>
          <p style={{ margin: 0, fontSize: 13, color: "#8a8a98", lineHeight: 1.55, overflowWrap: "anywhere" }}>
            {meta.blurb}
          </p>
        </div>
        {conn && <StatusPill status={conn.status} />}
      </header>

      {/* ── Notice ── */}
      {notice && (
        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            padding: "11px 13px",
            borderRadius: 11,
            background: notice.ok ? "rgba(0,221,136,0.07)" : "rgba(255,59,71,0.07)",
            border: `1px solid ${notice.ok ? "rgba(0,221,136,0.26)" : "rgba(255,59,71,0.26)"}`,
            color: notice.ok ? "#7ff0bd" : "#FF8A92",
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
              flexShrink: 0, minWidth: 44, minHeight: 44, marginTop: -10, marginRight: -6,
              color: "inherit", opacity: 0.7, cursor: "pointer", background: "transparent",
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Already connected ── */}
      {isConnected && (
        <Section eyebrow="Live" title={`${meta.label} is connected`}>
          <p style={{ margin: 0, fontSize: 13, color: "#8a8a98", lineHeight: 1.6, overflowWrap: "anywhere" }}>
            {conn?.account_name
              ? `Posting as @${conn.account_name}.`
              : "This connection is active."}{" "}
            You can post to {meta.label} from DirCoMedia now.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", minWidth: 0 }}>
            <SecondaryButton onClick={handleTest} disabled={busy === "test"} grow>
              {busy === "test" ? "Testing…" : "Test connection"}
            </SecondaryButton>
            <Link href="/settings/connections" style={{ flex: "1 1 130px", minWidth: 0, display: "flex" }}>
              <SecondaryButton grow>Manage</SecondaryButton>
            </Link>
          </div>
        </Section>
      )}

      {/* ── Steps ── */}
      <Section
        eyebrow={conn?.mode === "manual" ? "Guided setup" : "Setup"}
        title={`Set up the ${meta.label} app`}
      >
        <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 14 }}>
          {meta.steps.map((step, i) => (
            <li key={step.title} style={{ display: "flex", gap: 11, minWidth: 0 }}>
              {/* Fixed-width badge column — text can never run under it. */}
              <span
                style={{
                  flexShrink: 0,
                  width: 26,
                  height: 26,
                  borderRadius: 8,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "rgba(0,85,255,0.14)",
                  border: "1px solid rgba(0,85,255,0.32)",
                  color: "#3D8BFF",
                  fontFamily: "var(--font-mono), monospace",
                  fontSize: 11,
                }}
              >
                {i + 1}
              </span>
              <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 5 }}>
                <div
                  style={{
                    fontSize: 13.5,
                    fontWeight: 600,
                    color: "#e8e8ef",
                    letterSpacing: "-0.01em",
                    overflowWrap: "anywhere",
                  }}
                >
                  {step.title}
                </div>
                <p
                  style={{
                    margin: 0,
                    fontSize: 12.5,
                    lineHeight: 1.6,
                    color: "#8a8a98",
                    overflowWrap: "anywhere",
                  }}
                >
                  {step.detail}
                </p>
                {step.link && <DocsLink href={step.link} label={step.linkLabel || step.link} />}
              </div>
            </li>
          ))}
        </ol>

        {conn && (
          <CopyField
            label="Redirect URI — paste this into the developer app"
            value={conn.redirect_uri}
            hint="Must match exactly: same scheme, host, port and path, with no trailing slash."
          />
        )}
      </Section>

      {/* ── App credentials ── */}
      <Section
        eyebrow={conn?.app_configured ? "Saved" : "Required"}
        title="App credentials"
      >
        {conn?.app_configured ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 12px",
              borderRadius: 10,
              background: "rgba(0,221,136,0.07)",
              border: "1px solid rgba(0,221,136,0.24)",
              color: "#7ff0bd",
              fontSize: 12.5,
              minWidth: 0,
              overflowWrap: "anywhere",
            }}
          >
            <Check size={14} strokeWidth={2.2} style={{ flexShrink: 0 }} />
            <span style={{ minWidth: 0 }}>
              {meta.label} app credentials are stored. Replace them below if you rotated the secret.
            </span>
          </div>
        ) : (
          <p style={{ margin: 0, fontSize: 12.5, color: "#8a8a98", lineHeight: 1.6, overflowWrap: "anywhere" }}>
            Paste the client ID and secret from the developer portal. They&apos;re written to the
            server&apos;s environment file, never to the browser.
          </p>
        )}

        <SecretInput
          label="Client ID"
          value={clientId}
          onChange={setClientId}
          placeholder={conn?.app_configured ? "Replace stored client ID" : "Paste client ID"}
        />
        <SecretInput
          label="Client secret"
          value={clientSecret}
          onChange={setClientSecret}
          placeholder={conn?.app_configured ? "Replace stored secret" : "Paste client secret"}
        />

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", minWidth: 0 }}>
          <button
            onClick={handleSaveApp}
            disabled={busy === "save-app"}
            style={{
              flex: "1 1 160px",
              minWidth: 0,
              minHeight: 44,
              padding: "0 16px",
              borderRadius: 10,
              border: "1px solid rgba(0,85,255,0.5)",
              background: "rgba(0,85,255,0.18)",
              color: "#9ec2ff",
              fontSize: 13,
              fontWeight: 600,
              cursor: busy ? "wait" : "pointer",
              opacity: busy === "save-app" ? 0.6 : 1,
            }}
          >
            {busy === "save-app" ? "Saving…" : "Save credentials"}
          </button>
          <DocsLink href={meta.steps[0].link || conn?.developer_portal || "#"} label="Open developer portal" />
        </div>
      </Section>

      {/* ── Mode B: one-click authorize ── */}
      {conn?.mode === "oneclick" && (
        <Section eyebrow="One click" title={`Authorize ${meta.label}`}>
          <p style={{ margin: 0, fontSize: 12.5, color: "#8a8a98", lineHeight: 1.6, overflowWrap: "anywhere" }}>
            Opens {meta.label} in a popup. Approve the request and the window closes itself —
            the token is encrypted and stored automatically.
          </p>
          <button
            onClick={() => connect(platform)}
            disabled={!conn.app_configured || !!connecting}
            style={{
              width: "100%",
              minHeight: 48,
              padding: "0 18px",
              borderRadius: 11,
              border: `1px solid ${conn.app_configured ? "rgba(0,221,136,0.45)" : "rgba(255,255,255,0.1)"}`,
              background: conn.app_configured ? "rgba(0,221,136,0.14)" : "rgba(255,255,255,0.03)",
              color: conn.app_configured ? "#00DD88" : "#56565f",
              fontSize: 14,
              fontWeight: 600,
              letterSpacing: "-0.01em",
              cursor: conn.app_configured ? (connecting ? "wait" : "pointer") : "not-allowed",
              minWidth: 0,
            }}
          >
            {connecting
              ? "Waiting for authorization…"
              : conn.app_configured
              ? `Authorize ${meta.label}`
              : "Save app credentials first"}
          </button>
        </Section>
      )}

      {/* ── Mode A: manual token paste ── */}
      {(conn?.mode === "manual" || showManualToken) && (
        <Section
          eyebrow={conn?.mode === "manual" ? "Required" : "Fallback"}
          title="Paste an access token"
        >
          <p style={{ margin: 0, fontSize: 12.5, color: "#8a8a98", lineHeight: 1.6, overflowWrap: "anywhere" }}>
            {meta.tokenHelp ||
              "If the one-click flow won't complete, paste a token you generated yourself. It's verified against the platform before it's saved."}
          </p>

          {(meta.tokenFields || [
            { key: "access_token" as const, label: "Access token", hint: "Token generated in the platform's developer tools" },
          ]).map((f) =>
            f.key === "access_token" ? (
              <SecretInput
                key={f.key}
                label={f.label}
                value={accessToken}
                onChange={setAccessToken}
                placeholder="Paste token"
                hint={f.hint}
              />
            ) : (
              <SecretInput
                key={f.key}
                label={f.label}
                value={refreshTok}
                onChange={setRefreshTok}
                placeholder="Paste refresh token (optional)"
                hint={f.hint}
              />
            )
          )}

          <button
            onClick={handleSaveToken}
            disabled={busy === "save-token"}
            style={{
              width: "100%",
              minHeight: 48,
              padding: "0 18px",
              borderRadius: 11,
              border: "1px solid rgba(0,221,136,0.45)",
              background: "rgba(0,221,136,0.14)",
              color: "#00DD88",
              fontSize: 14,
              fontWeight: 600,
              cursor: busy === "save-token" ? "wait" : "pointer",
              opacity: busy === "save-token" ? 0.6 : 1,
              minWidth: 0,
            }}
          >
            {busy === "save-token" ? "Verifying…" : "Save and test connection"}
          </button>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 11.5,
              color: "#56565f",
              minWidth: 0,
              overflowWrap: "anywhere",
            }}
          >
            <ShieldCheck size={13} strokeWidth={1.9} style={{ flexShrink: 0, color: "#00DD88" }} />
            <span style={{ minWidth: 0 }}>
              Encrypted with Fernet before storage. Never logged, never sent to the browser again.
            </span>
          </div>
        </Section>
      )}

      <MercurioWidget platform={platform} />
    </div>
  );
}
