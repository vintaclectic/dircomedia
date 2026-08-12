/**
 * Platform presentation + wizard copy (YH9AE4D).
 *
 * Everything a human reads while connecting lives here, so the wizard steps and
 * Mercurio's answers are written once and can't drift apart. The FUNCTIONAL
 * facts (mode, status, redirect_uri, app_configured) all come from the backend
 * /status response — this file never decides behavior, only how it looks and
 * what it says.
 */
import type { ConnectPlatform, ConnectionStatus } from "@/lib/types";

export const PLATFORM_ORDER: ConnectPlatform[] = [
  "twitter", "reddit", "pinterest", "instagram", "tiktok",
];

export interface PlatformMeta {
  label: string;
  color: string;
  /** Single glyph — kept to one character so the badge box never reflows. */
  glyph: string;
  blurb: string;
  /** Manual-setup steps. Each becomes one numbered row in the wizard. */
  steps: { title: string; detail: string; link?: string; linkLabel?: string }[];
  /** Fields for the manual token lane (empty = one-click only). */
  tokenFields?: { key: "access_token" | "refresh_token"; label: string; hint: string }[];
  tokenHelp?: string;
  defaultExpiryDays?: number;
}

export const PLATFORM_META: Record<ConnectPlatform, PlatformMeta> = {
  twitter: {
    label: "X",
    color: "#FFFFFF",
    glyph: "X",
    blurb: "Highest-velocity rail. Post, reply, and thread from DirCoMedia.",
    steps: [
      {
        title: "Open the X developer portal",
        detail: "Sign in with the account that will post. Create a project, then an app named DirCoMedia.",
        link: "https://developer.x.com/en/portal/dashboard",
        linkLabel: "developer.x.com",
      },
      {
        title: "Turn on user authentication",
        detail: "App settings → User authentication settings → Set up. App permissions: Read and write. Type: Web App, Automated App or Bot.",
      },
      {
        title: "Register the callback URL",
        detail: "Paste the redirect URI below into the Callback URI field. It must match character for character — this is the #1 cause of OAuth failures.",
      },
      {
        title: "Copy the OAuth 2.0 Client ID and Secret",
        detail: "Keys and tokens tab → OAuth 2.0 Client ID and Client Secret. Paste them below, then use Authorize.",
      },
    ],
  },
  reddit: {
    label: "Reddit",
    color: "#FF4500",
    glyph: "R",
    blurb: "Community rail. Post to your own subs freely; external subs stay approval-only.",
    steps: [
      {
        title: "Open Reddit app preferences",
        detail: "Scroll to the bottom and choose 'create another app…'.",
        link: "https://www.reddit.com/prefs/apps",
        linkLabel: "reddit.com/prefs/apps",
      },
      {
        title: "Create a WEB app (not a script)",
        detail: "Name it DirCoMedia and pick type 'web app'. A script app cannot complete this OAuth flow — if you already made one, create a web app alongside it.",
      },
      {
        title: "Register the redirect URI",
        detail: "Paste the redirect URI below into the 'redirect uri' field before saving.",
      },
      {
        title: "Copy the client ID and secret",
        detail: "The client ID is the string directly under the app name; the secret is labelled. Paste both below, then use Authorize.",
      },
    ],
  },
  pinterest: {
    label: "Pinterest",
    color: "#E60023",
    glyph: "P",
    blurb: "Long-tail discovery. Pins keep pulling traffic months after posting.",
    steps: [
      {
        title: "Open the Pinterest developer console",
        detail: "Sign in and create an app named DirCoMedia.",
        link: "https://developers.pinterest.com/apps/",
        linkLabel: "developers.pinterest.com",
      },
      {
        title: "Add the redirect URI",
        detail: "In the app's configuration, paste the redirect URI below into the allowed redirect URIs list.",
      },
      {
        title: "Copy the App ID and App Secret",
        detail: "Paste both below, then use Authorize. Pinterest's OAuth flow is the least fussy of the five.",
      },
    ],
  },
  instagram: {
    label: "Instagram",
    color: "#E1306C",
    glyph: "I",
    blurb: "Reels and image posts. Needs a Professional account linked to a Facebook Page.",
    steps: [
      {
        title: "Switch Instagram to Professional",
        detail: "Instagram app → Settings → Account type → switch to Professional (Business or Creator). Publishing does not work on a personal account.",
      },
      {
        title: "Link a Facebook Page",
        detail: "Create or pick a Facebook Page, then link it: Page settings → Linked accounts → Instagram. The Graph API reaches Instagram through the Page.",
      },
      {
        title: "Create a Meta app",
        detail: "Create App → type Business → name it DirCoMedia. Add the Instagram Graph API product.",
        link: "https://developers.facebook.com/apps/",
        linkLabel: "developers.facebook.com",
      },
      {
        title: "Generate a long-lived token",
        detail: "Graph API Explorer → select your app → grant instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement → generate, then exchange it for a 60-day long-lived token. Paste that token below.",
        link: "https://developers.facebook.com/tools/explorer/",
        linkLabel: "Graph API Explorer",
      },
    ],
    tokenFields: [
      { key: "access_token", label: "Long-lived access token", hint: "The 60-day token from the fb_exchange_token step" },
    ],
    tokenHelp:
      "Instagram has no refresh token. DirCoMedia re-exchanges this token for a fresh 60-day one every 6 hours, so it never expires as long as the app stays connected.",
    defaultExpiryDays: 60,
  },
  tiktok: {
    label: "TikTok",
    color: "#25F4EE",
    glyph: "T",
    blurb: "Short-form video. Direct Post needs TikTok's app audit; drafts work before that.",
    steps: [
      {
        title: "Register a TikTok developer app",
        detail: "Create an app named DirCoMedia in the TikTok developer portal.",
        link: "https://developers.tiktok.com/apps",
        linkLabel: "developers.tiktok.com",
      },
      {
        title: "Add the Content Posting API",
        detail: "Request the scopes video.publish, video.upload and user.info.basic.",
      },
      {
        title: "Understand the audit gate",
        detail: "Direct Post requires TikTok to audit the app. Before approval, uploads land in your TikTok inbox as drafts for one-tap publishing — that is a working rail, not a failure.",
      },
      {
        title: "Run TikTok's OAuth flow once",
        detail: "Use the portal's own authorization tool against your account, then paste the access token (and refresh token, if shown) below.",
      },
    ],
    tokenFields: [
      { key: "access_token", label: "Access token", hint: "User access token from the TikTok OAuth step" },
      { key: "refresh_token", label: "Refresh token", hint: "Optional but recommended — access tokens expire in 24h" },
    ],
    tokenHelp:
      "TikTok access tokens live 24 hours. Supply the refresh token and DirCoMedia renews it automatically; without one you will have to reconnect daily.",
    defaultExpiryDays: 1,
  },
};

export const STATUS_META: Record<
  ConnectionStatus,
  { label: string; color: string; cta: string; short: string }
> = {
  connected:       { label: "Connected",    color: "#00DD88", cta: "Manage",    short: "OK" },
  expiring:        { label: "Expiring soon", color: "#FFB020", cta: "Refresh",   short: "SOON" },
  expired:         { label: "Expired",      color: "#FF3B47", cta: "Reconnect", short: "DEAD" },
  needs_reconnect: { label: "Action needed", color: "#FF3B47", cta: "Reconnect", short: "FIX" },
  disconnected:    { label: "Not connected", color: "#56565f", cta: "Connect",   short: "—" },
};

/** Human countdown. Deliberately coarse above a day — a live seconds ticker on
 *  a 60-day token is noise pretending to be information. */
export function formatExpiry(expiresAt: number | null, status: ConnectionStatus): string {
  if (status === "disconnected") return "Not connected";
  if (status === "needs_reconnect") return "Reconnect required";
  if (expiresAt === null) return "Does not expire";
  const remaining = expiresAt * 1000 - Date.now();
  if (remaining <= 0) return "Expired";
  const days = Math.floor(remaining / 86400000);
  const hours = Math.floor((remaining % 86400000) / 3600000);
  const mins = Math.floor((remaining % 3600000) / 60000);
  if (days >= 2) return `Expires in ${days} days`;
  if (days === 1) return `Expires in 1 day ${hours}h`;
  if (hours >= 1) return `Expires in ${hours}h ${mins}m`;
  const secs = Math.floor((remaining % 60000) / 1000);
  return `Expires in ${mins}m ${secs}s`;
}
