"use client";
/**
 * MERCURIO — the patient teacher who sits beside the wizard (YH9AE4D).
 *
 * Answers the questions that actually stall a setup ("what's a redirect URI?",
 * "where's my client secret?", "why does TikTok want an audit?") from a local
 * knowledge base — no tokens spent, no network round trip, instant answers.
 * Personality: survival-scarred, zero condescension. Nobody feels stupid here.
 *
 * ── NO-COLLISION LAW — why this widget does NOT float. ──
 *
 * The obvious build is a floating bubble pinned to the bottom-right. A real
 * browser audit at 320–1920px proved that design violates the law outright: on
 * a long page (the Instagram wizard) the fixed launcher and panel sat directly
 * on top of live content — instructions, the Copy button, the redirect URI.
 * Overlap is the cardinal sin and layering is Vinta's call, not an accident, so
 * the floating version was removed rather than nudged.
 *
 * What ships instead: Mercurio is IN NORMAL FLOW, docked at the end of the page
 * content. It occupies its own space and pushes nothing:
 *  1. Collapsed, it's a full-width bar in the document — it cannot overlap
 *     anything because it participates in layout like every other block.
 *  2. Expanded, it grows a bounded panel BELOW itself in flow. Long answers
 *     scroll INSIDE the transcript region (min-height:0 + overflow-y:auto), so
 *     content never spills past the panel's edge.
 *  3. Nothing here is position:fixed or absolute. There is no z-index race with
 *     the bottom nav, no safe-area math to get wrong, and no breakpoint where a
 *     floating element can drift onto a neighbor.
 *  4. Every interactive element is >= 44px.
 *
 * The trade: one extra scroll to reach help, versus a guarantee that help never
 * covers the thing you're trying to read. That's the right trade under this law.
 */
import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send } from "lucide-react";
import type { ConnectPlatform } from "@/lib/types";

type QA = { q: string; a: string; keys: string[] };

/** Universal answers — apply on every platform. */
const GENERAL: QA[] = [
  {
    q: "What is a redirect URI?",
    a: "It's the address the platform sends your browser back to after you approve access. Think of it as a return address on an envelope. DirCoMedia shows you the exact one to use with a Copy button — paste it into the developer app's settings without changing a single character. If it differs by even a trailing slash, the platform refuses the connection. That mismatch is the number one reason these setups fail, and it's not your fault when it happens; the error messages are genuinely terrible.",
    keys: ["redirect", "uri", "url", "callback", "return"],
  },
  {
    q: "What's the difference between a client ID and a client secret?",
    a: "The client ID names your app — it's public, like a username. The client secret proves the request really came from your app — it's private, like a password. DirCoMedia needs both to complete a connection. The secret is usually only shown once when you create the app, so copy it right then. If you lost it, you can regenerate it in the developer portal; regenerating invalidates the old one, so paste the new value here afterward.",
    keys: ["client", "id", "secret", "key", "difference", "consumer"],
  },
  {
    q: "Is it safe to paste my tokens here?",
    a: "Yes, and here's exactly why rather than just asking you to trust it. Every access and refresh token is encrypted with Fernet (AES-128 with an HMAC signature) before it's written to the database, using a key that lives only in your .env file and never in the repo. The database file on disk holds ciphertext — if a backup leaked, the tokens in it would be useless. Nothing is ever logged in plaintext, and DirCoMedia is owner-only: every endpoint requires your owner token.",
    keys: ["safe", "secure", "security", "encrypt", "token", "store", "trust", "risk"],
  },
  {
    q: "What does 'Expiring soon' mean?",
    a: "Your access token is within three days of expiring. You almost never need to act on this — a background worker runs every six hours and renews anything inside that window automatically. The warning is there so nothing surprises you. If a renewal ever fails permanently, the card turns red and says 'Action needed', and only then does it want your attention.",
    keys: ["expir", "soon", "warning", "yellow", "countdown", "renew"],
  },
  {
    q: "What is OAuth, actually?",
    a: "It's the handshake that lets DirCoMedia post as you without ever knowing your password. You log into the platform yourself, it asks whether you want to grant DirCoMedia specific permissions, and if you say yes it hands back a token — a key cut for one lock. You can revoke that token any time from the platform's settings or from the Disconnect button here, and your password is never involved at any point.",
    keys: ["oauth", "what", "how", "work", "authorize", "authoriz"],
  },
  {
    q: "The popup closed but nothing happened.",
    a: "Usually one of three things. First, a popup blocker ate the window — check for a blocked-popup icon in the address bar and allow it for this site. Second, the redirect URI in the developer app doesn't match the one shown here exactly. Third, the connection took longer than ten minutes, which expires the security token that protects the flow. Fix whichever applies and press Connect again; nothing was damaged by the failed attempt.",
    keys: ["popup", "closed", "nothing", "blocked", "blank", "stuck", "fail"],
  },
  {
    q: "What happens when I disconnect?",
    a: "The stored credential is deleted outright — not flagged, not archived, deleted. DirCoMedia keeps nothing that could still post on your behalf. If you want to also revoke access on the platform's side, do it in that platform's app or security settings. Reconnecting later is the same flow you ran the first time.",
    keys: ["disconnect", "remove", "delete", "revoke", "unlink"],
  },
];

/** Platform-specific answers — at least three per platform, per the spec. */
const PER_PLATFORM: Record<ConnectPlatform, QA[]> = {
  twitter: [
    {
      q: "Where do I find my X client ID and secret?",
      a: "developer.x.com → your project → your app → the 'Keys and tokens' tab. You want the OAuth 2.0 Client ID and Client Secret, NOT the API Key/Secret pair further up the page — that's a different, older auth scheme. If you don't see OAuth 2.0 credentials at all, go to 'User authentication settings' and set it up first; the credentials appear once that's saved.",
      keys: ["where", "find", "client", "id", "secret", "key", "token"],
    },
    {
      q: "X says my callback URL is invalid.",
      a: "In App settings → User authentication settings → Callback URI, paste the exact redirect URI shown on this page. X is strict about the whole string: scheme, host, port, path, no trailing slash. Copy it with the button rather than typing it. Also confirm 'Type of App' is set to Web App, Automated App or Bot — the other types don't allow this flow.",
      keys: ["callback", "invalid", "url", "uri", "mismatch", "error"],
    },
    {
      q: "Do I need to pay for X API access?",
      a: "Not to start. The Free tier allows 500 posts per month per app, which is plenty for early acquisition. Basic is $200/month for 3,000 user-context posts if volume ever demands it. Connect on Free and only upgrade when you actually hit the ceiling — don't pay ahead of the need.",
      keys: ["pay", "cost", "price", "free", "tier", "basic", "money"],
    },
    {
      q: "What permissions does DirCoMedia need on X?",
      a: "Read and write. It requests tweet.read, tweet.write, users.read, and offline.access. That last one is what lets it refresh the token by itself so you're not reconnecting every couple of hours. It does not request direct-message access.",
      keys: ["permission", "scope", "read", "write", "access", "need"],
    },
  ],
  reddit: [
    {
      q: "Reddit rejected my credentials — what's wrong?",
      a: "Almost always the app type. A 'script' app cannot complete this OAuth flow; you need a 'web app'. Go to reddit.com/prefs/apps, create another app, pick web app, and paste the redirect URI from this page into the redirect uri field. The client ID is the small string directly under the app's name — not the app name itself, which trips up nearly everyone.",
      keys: ["reject", "401", "invalid", "credential", "wrong", "fail", "error", "script"],
    },
    {
      q: "Why does Reddit need 'permanent' duration?",
      a: "Without it Reddit issues an access token that lives one hour and hands back no refresh token, so the connection dies quietly and forever after sixty minutes. DirCoMedia requests duration=permanent automatically so you get a refresh token and the connection actually persists. You don't have to configure anything for this.",
      keys: ["permanent", "duration", "refresh", "expire", "hour"],
    },
    {
      q: "Will Reddit ban me for posting automatically?",
      a: "It can, if you blast promos into subreddits you don't own — that's the fastest route to a shadowban. DirCoMedia is built defensively here: auto-posting is restricted to an allowlist of subs you own, and everything else waits for your explicit approval. The working ratio is roughly nine genuine contributions per promotional post. Reddit rewards being a real community member and punishes drive-by marketing, so it's worth playing straight.",
      keys: ["ban", "shadowban", "spam", "safe", "auto", "promo", "rule"],
    },
  ],
  pinterest: [
    {
      q: "Where do I get Pinterest app credentials?",
      a: "developers.pinterest.com/apps → create an app named DirCoMedia. The App ID and App Secret are shown on the app's page. Add the redirect URI from this page to the allowed redirect URIs list before you try to connect — Pinterest checks it at authorize time.",
      keys: ["where", "credential", "app", "id", "secret", "get", "find"],
    },
    {
      q: "Do I need a business account for Pinterest?",
      a: "Yes for publishing. Converting a personal account to a business account is free and takes about a minute in Pinterest's settings — you keep all your existing pins and followers. The API won't let you create pins from a personal account.",
      keys: ["business", "account", "personal", "convert", "need"],
    },
    {
      q: "Why bother with Pinterest at all?",
      a: "Because the half-life is unlike anything else. A tweet is dead in hours; a pin keeps surfacing in search and feeds for months, sometimes years. For traffic acquisition it's the highest-leverage slow rail available — small effort now, compounding returns later. It's the platform most people underrate.",
      keys: ["why", "bother", "worth", "traffic", "value", "point"],
    },
  ],
  instagram: [
    {
      q: "Why can't I connect Instagram with one click?",
      a: "Because Instagram publishing runs through the Facebook Graph API, and it requires a Professional (Business or Creator) Instagram account linked to a Facebook Page. No OAuth popup can create that link for you — it has to happen inside the Instagram and Facebook apps first. Rather than give you a button that fails for reasons the screen can't explain, DirCoMedia walks you through it and takes the token at the end.",
      keys: ["one", "click", "oneclick", "why", "manual", "cant"],
    },
    {
      q: "Where do I find my Instagram access token?",
      a: "developers.facebook.com/tools/explorer — the Graph API Explorer. Select your app, add the permissions instagram_basic, instagram_content_publish, pages_show_list and pages_read_engagement, then generate the token. That first token only lives about an hour, so exchange it for a 60-day long-lived token using the fb_exchange_token call in the setup steps, and paste THAT one here.",
      keys: ["where", "find", "token", "access", "explorer", "graph", "get"],
    },
    {
      q: "My Instagram token expires in 60 days — then what?",
      a: "Nothing you have to do. Instagram has no refresh token, but a still-valid long-lived token can be traded for a fresh 60-day one, and DirCoMedia does exactly that every six hours. The token in the vault is never more than a few hours old, so the 60-day clock never actually runs out. If the exchange ever fails, the card turns red and tells you.",
      keys: ["60", "sixty", "day", "expire", "refresh", "renew", "then"],
    },
    {
      q: "Do I need Facebook App Review?",
      a: "Not for posting to your own account. As long as you're an admin of the app, it can stay in Development mode and publish to accounts you control. App Review is only needed when other people's accounts use your app — which is a Path B concern, not a today concern.",
      keys: ["review", "approve", "development", "mode", "need"],
    },
  ],
  tiktok: [
    {
      q: "Why does TikTok want an audit?",
      a: "TikTok gates Direct Post — publishing straight to your public profile — behind a manual app audit. It's their anti-spam control and there's no way around it. The good news is you're not blocked while you wait: unaudited apps can still upload, the video just lands in your TikTok inbox as a draft you publish with one tap. That's a working rail, not a failure state.",
      keys: ["audit", "why", "review", "approve", "direct", "post", "wait"],
    },
    {
      q: "Where do I find my TikTok access token?",
      a: "developers.tiktok.com/apps → your app → run the authorization flow against your own account with the video.publish, video.upload and user.info.basic scopes. The portal shows the access token and refresh token at the end. Paste both here — especially the refresh token.",
      keys: ["where", "find", "token", "access", "get", "portal"],
    },
    {
      q: "My TikTok connection keeps expiring.",
      a: "TikTok access tokens live only 24 hours, so without a refresh token you'd be reconnecting daily. Paste the refresh token into the second field and DirCoMedia renews the access token automatically every six hours. If you skipped that field, re-run TikTok's authorization flow and grab it — it's the difference between this working and this being a chore.",
      keys: ["expire", "expiring", "24", "daily", "keeps", "refresh", "again"],
    },
  ],
};

function findAnswer(input: string, platform: ConnectPlatform | null): QA | null {
  const q = input.toLowerCase().trim();
  if (!q) return null;
  const pool = [...(platform ? PER_PLATFORM[platform] : []), ...GENERAL];
  let best: { qa: QA; score: number } | null = null;
  for (const qa of pool) {
    let score = 0;
    for (const k of qa.keys) if (q.includes(k)) score += 2;
    for (const w of qa.q.toLowerCase().split(/\W+/)) {
      if (w.length > 3 && q.includes(w)) score += 1;
    }
    if (score > 0 && (!best || score > best.score)) best = { qa, score };
  }
  return best ? best.qa : null;
}

type Msg = { role: "user" | "mercurio"; text: string };

export function MercurioWidget({ platform = null }: { platform?: ConnectPlatform | null }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && msgs.length === 0) {
      setMsgs([{
        role: "mercurio",
        text: platform
          ? `I'm Mercurio. I've walked people through ${platform === "twitter" ? "X" : platform} setup more times than I can count, and the confusing parts are confusing for real reasons — not because you're missing something obvious. Ask me anything, or tap a question below.`
          : "I'm Mercurio. Connecting these platforms is more annoying than it should be, and none of it is your fault. Ask me anything, or tap one of the common questions below.",
      }]);
    }
  }, [open, platform, msgs.length]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [msgs, open]);

  function ask(text: string) {
    const question = text.trim();
    if (!question) return;
    const found = findAnswer(question, platform);
    setMsgs((m) => [
      ...m,
      { role: "user", text: question },
      {
        role: "mercurio",
        text: found
          ? found.a
          : "I don't have a clean answer for that one, and I'd rather say so than guess and send you down a wrong path. The setup steps on this page cover the full sequence for this platform, and the developer-portal link goes straight to the source. Try rephrasing — I match on words like 'redirect', 'secret', 'token', 'expire', 'audit', or 'safe'.",
      },
    ]);
    setInput("");
  }

  const suggestions = (platform ? PER_PLATFORM[platform] : GENERAL).slice(0, 3);

  // Collapsed: a full-width bar in NORMAL FLOW. It occupies its own space and
  // therefore cannot overlap anything at any width.
  if (!open) {
    return (
      <div style={{ marginTop: 20, minWidth: 0 }}>
        <button
          onClick={() => setOpen(true)}
          aria-label="Ask Mercurio for help"
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 10,
            minHeight: 52,
            padding: "0 16px",
            borderRadius: 14,
            border: "1px solid rgba(0,85,255,0.32)",
            background: "rgba(0,85,255,0.07)",
            color: "#f5f5f7",
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: "-0.01em",
            cursor: "pointer",
            textAlign: "left",
            minWidth: 0,
          }}
        >
          <MessageCircle size={17} strokeWidth={2} style={{ flexShrink: 0, color: "#3D8BFF" }} />
          <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            Ask Mercurio
          </span>
          <span
            style={{
              flexShrink: 0,
              fontFamily: "var(--font-mono), monospace",
              fontSize: 8.5,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              color: "#56565f",
            }}
          >
            Stuck?
          </span>
        </button>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 20, minWidth: 0 }}>
      <div
        role="region"
        aria-label="Mercurio setup assistant"
        style={{
          display: "flex",
          flexDirection: "column",
          height: "min(70vh, 520px)",
          borderRadius: 16,
          border: "1px solid rgba(255,255,255,0.12)",
          background: "rgba(6,6,14,0.92)",
          overflow: "hidden",
          minWidth: 0,
        }}
      >
        {/* Header — fixed row inside the panel, never scrolls away */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 14px",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
            flexShrink: 0,
            minWidth: 0,
          }}
        >
          <div
            style={{
              width: 30, height: 30, borderRadius: 9, flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "rgba(0,85,255,0.16)", border: "1px solid rgba(0,85,255,0.4)",
              color: "#3D8BFF", fontFamily: "var(--font-display), sans-serif", fontSize: 14,
            }}
          >
            M
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: "#f5f5f7", letterSpacing: "-0.015em" }}>
              Mercurio
            </div>
            <div
              style={{
                fontFamily: "var(--font-mono), monospace", fontSize: 8.5,
                letterSpacing: "0.2em", textTransform: "uppercase", color: "#56565f",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}
            >
              Setup guide
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close Mercurio"
            style={{
              flexShrink: 0, width: 44, height: 44, borderRadius: 9,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "transparent", color: "#8a8a98", cursor: "pointer",
            }}
          >
            <X size={17} strokeWidth={2} />
          </button>
        </div>

        {/* Transcript — the ONLY scrolling region. min-height:0 is what actually
            lets a flex child scroll instead of growing past its parent. */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            overflowX: "hidden",
            padding: 14,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          {msgs.map((m, i) => (
            <div
              key={i}
              style={{
                alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "88%",
                minWidth: 0,
                padding: "9px 12px",
                borderRadius: 12,
                background: m.role === "user" ? "rgba(0,85,255,0.16)" : "rgba(255,255,255,0.045)",
                border: `1px solid ${m.role === "user" ? "rgba(0,85,255,0.32)" : "rgba(255,255,255,0.08)"}`,
                color: m.role === "user" ? "#dce8ff" : "#c8c8d2",
                fontSize: 12.5,
                lineHeight: 1.6,
                overflowWrap: "anywhere",
                wordBreak: "break-word",
              }}
            >
              {m.text}
            </div>
          ))}

          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 2, minWidth: 0 }}>
            {suggestions.map((s) => (
              <button
                key={s.q}
                onClick={() => ask(s.q)}
                style={{
                  width: "100%",
                  minHeight: 44,
                  padding: "10px 12px",
                  borderRadius: 10,
                  textAlign: "left",
                  border: "1px solid rgba(255,255,255,0.08)",
                  background: "rgba(255,255,255,0.02)",
                  color: "#8a8a98",
                  fontSize: 12,
                  lineHeight: 1.45,
                  cursor: "pointer",
                  overflowWrap: "anywhere",
                  minWidth: 0,
                }}
              >
                {s.q}
              </button>
            ))}
          </div>
        </div>

        {/* Composer — fixed row at the bottom of the panel */}
        <div
          style={{
            display: "flex",
            gap: 8,
            padding: 12,
            borderTop: "1px solid rgba(255,255,255,0.08)",
            flexShrink: 0,
            minWidth: 0,
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") ask(input); }}
            placeholder="Ask anything about this setup…"
            style={{
              flex: 1, minWidth: 0, minHeight: 44, padding: "0 12px",
              borderRadius: 10, fontSize: 13,
            }}
          />
          <button
            onClick={() => ask(input)}
            aria-label="Send question"
            style={{
              flexShrink: 0, width: 44, height: 44, borderRadius: 10,
              display: "flex", alignItems: "center", justifyContent: "center",
              border: "1px solid rgba(0,85,255,0.45)", background: "rgba(0,85,255,0.16)",
              color: "#3D8BFF", cursor: "pointer",
            }}
          >
            <Send size={16} strokeWidth={2} />
          </button>
        </div>
      </div>
    </div>
  );
}
