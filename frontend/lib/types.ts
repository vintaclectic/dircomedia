export type ContentType = "text" | "image" | "video" | "reel";
export type ContentStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "scheduled"
  | "posted"
  | "failed";
export type Platform = "twitter" | "tiktok" | "instagram" | "reddit" | "pinterest";

// ── OAuth connection wizard (YH9AE4D, 2026-08-12) ──
// These MUST mirror app/api/v1/oauth.py exactly. The backend derives status in
// one place (_derive_status) and the UI never recomputes it — if these two
// enums ever disagree, the dashboard lies about whether an account can post.

/** Platform keys the wizard manages, in canonical render order. */
export type ConnectPlatform =
  | "twitter" | "reddit" | "pinterest" | "instagram" | "tiktok";

/**
 * connected       — healthy, >3d of life left (or never expires)
 * expiring        — under 3 days; the worker will renew it, but show the clock
 * expired         — past expiry and not yet renewed
 * needs_reconnect — refresh failed permanently; only Vinta can fix it
 * disconnected    — no credential stored at all
 */
export type ConnectionStatus =
  | "connected" | "expiring" | "expired" | "needs_reconnect" | "disconnected";

/** 'oneclick' = full OAuth popup. 'manual' = guided paste (IG/TikTok gating). */
export type ConnectMode = "oneclick" | "manual";

export interface PlatformConnection {
  platform: ConnectPlatform;
  label: string;
  mode: ConnectMode;
  status: ConnectionStatus;
  account_name: string | null;
  expires_at: number | null;        // unix seconds, UTC
  expires_in_days: number | null;
  app_configured: boolean;          // developer app client id+secret present
  needs_reconnect: boolean;
  last_error: string | null;
  scopes: string | null;
  redirect_uri: string;             // exact string to register in the dev app
  developer_portal: string;
  docs_url: string;
}

export interface OAuthStartOut {
  authorize_url: string;
  state: string;
  expires_in: number;
}

export interface OAuthTestOut {
  ok: boolean;
  platform: string;
  account_name?: string | null;
  error?: string;
}

/** postMessage payload the OAuth popup sends its opener on completion. */
export interface OAuthPopupMessage {
  source: "dircomedia-oauth";
  ok: boolean;
  platform: string;
  message: string;
}

export interface Project {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface Content {
  id: string;
  project_id: string;
  content_type: ContentType;
  status: ContentStatus;
  title: string | null;
  body: string | null;
  media_url: string | null;
  platforms: Platform[];
  created_at: string;
}

export interface Schedule {
  id: string;
  content_id: string;
  scheduled_at: string;
  is_posted: boolean;
  platforms: Platform[];
  created_at: string;
}

export interface AnalyticsSummary {
  project_slug: string;
  total_impressions: number;
  total_likes: number;
  avg_engagement_rate: number;
  top_platform: string;
  content_count: number;
}

export interface StrategyInsight {
  project_slug: string;
  insights: string[];
  recommended_content_types: ContentType[];
  recommended_posting_times: Record<string, string[]>;
  best_platforms: Platform[];
}

export interface GenerateRequest {
  project_slug: string;
  content_type: ContentType;
  topic: string;
  platforms: Platform[];
  auto_approve: boolean;
}

export interface VideoJobOut {
  job_id: string;
  status: string;
  content_id?: string;
  message: string;
}

// ── Broadcast Spine (council decree 2026-07-04, Phase 1) ──
export type BroadcastStatus =
  | "pending_approval"
  | "approved"
  | "posting"
  | "posted"
  | "partial"
  | "failed"
  | "vetoed";

export interface Broadcast {
  id: string;
  project_slug: string;
  kind: string;
  source: string;
  title: string | null;
  body: string | null;
  media_url: string | null;
  content_type: string;
  platforms: string[];
  mode: string;
  status: BroadcastStatus;
  results: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string | null;
}
