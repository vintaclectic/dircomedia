import type {
  Project,
  Content,
  Schedule,
  AnalyticsSummary,
  StrategyInsight,
  GenerateRequest,
  VideoJobOut,
  Broadcast,
  PlatformConnection,
  OAuthStartOut,
  OAuthTestOut,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "";

// NOTE (2026-08-21): The gateway attaches Authorization server-side after session
// verification (SFM8BJE). The browser NEVER carries the owner token — it would be
// inlined into client JS chunks and shipped publicly. Credentials=include so the
// HttpOnly session cookie rides along; the gateway turns that into a bearer token.
function authHeaders(): Record<string, string> {
  return {}; // gateway handles auth; browser sends session cookie only
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "include", // send HttpOnly session cookie
    headers: { "Content-Type": "application/json", ...authHeaders(), ...options?.headers },
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API ${res.status}: ${error}`);
  }
  return res.json();
}

// Projects
export const getProjects = () => request<Project[]>("/api/v1/projects/");
export const getProject = (slug: string) => request<Project>(`/api/v1/projects/${slug}`);
export const seedProjects = () => request("/api/v1/projects/seed", { method: "POST" });

// Content
export const generateContent = (body: GenerateRequest) =>
  request<Content>("/api/v1/content/generate", { method: "POST", body: JSON.stringify(body) });

export const listContent = (params?: {
  project_slug?: string;
  status?: string;
  limit?: number;
}) => {
  const qs = new URLSearchParams(params as Record<string, string>).toString();
  return request<Content[]>(`/api/v1/content/${qs ? `?${qs}` : ""}`);
};

export const getContent = (id: string) => request<Content>(`/api/v1/content/${id}`);
export const approveContent = (id: string) =>
  request<Content>(`/api/v1/content/${id}/approve`, { method: "PATCH" });

// Video
export const generateHypeClip = (body: {
  project_slug: string;
  description: string;
  duration?: number;
  style?: string;
  platforms?: string[];
}) =>
  request<VideoJobOut>("/api/v1/video/hype-clip", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getVideoJob = (jobId: string) =>
  request<VideoJobOut>(`/api/v1/video/job/${jobId}`);

export const uploadRecording = async (
  file: File,
  projectSlug: string,
  platforms: string[]
): Promise<VideoJobOut> => {
  const form = new FormData();
  form.append("file", file);
  form.append("project_slug", projectSlug);
  form.append("platforms", platforms.join(","));
  const res = await fetch(`${BASE}/api/v1/video/process-recording`, {
    method: "POST",
    credentials: "include", // send session cookie
    // no Content-Type header for FormData — browser sets multipart/form-data with boundary
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
};

// Distribution
export const postNow = (contentId: string, platforms?: string[]) =>
  request("/api/v1/distribution/post-now", {
    method: "POST",
    body: JSON.stringify({ content_id: contentId, platforms }),
  });

export const schedulePost = (contentId: string, scheduledAt: string, platforms?: string[]) =>
  request<Schedule>("/api/v1/distribution/schedule", {
    method: "POST",
    body: JSON.stringify({ content_id: contentId, scheduled_at: scheduledAt, platforms }),
  });

export const listSchedules = (upcomingOnly = true) =>
  request<Schedule[]>(`/api/v1/distribution/schedules?upcoming_only=${upcomingOnly}`);

// Broadcast Spine (approve-first loop — council decree 2026-07-04)
export const listPendingBroadcasts = () =>
  request<Broadcast[]>("/api/v1/broadcast/pending");

export const listBroadcasts = (limit = 50) =>
  request<Broadcast[]>(`/api/v1/broadcast/?limit=${limit}`);

export const approveBroadcast = (id: string) =>
  request<Broadcast>(`/api/v1/broadcast/${id}/approve`, { method: "POST" });

export const vetoBroadcast = (id: string) =>
  request<Broadcast>(`/api/v1/broadcast/${id}/veto`, { method: "POST" });

// Connection health (Phase 2 — the rail)
export type PlatformHealth = { configured: boolean | null; live: boolean | null; error?: string };
export const getConnectionHealth = () =>
  request<Record<string, PlatformHealth>>("/api/v1/distribution/health");

// ── OAuth connection wizard (YH9AE4D, 2026-08-12) ──
export const getConnections = () =>
  request<PlatformConnection[]>("/api/v1/oauth/status");

export const getEncryptionStatus = () =>
  request<{ configured: boolean }>("/api/v1/oauth/encryption-status");

export const startOAuth = (platform: string) =>
  request<OAuthStartOut>(`/api/v1/oauth/${platform}/start`);

export const saveAppCredentials = (platform: string, clientId: string, clientSecret: string) =>
  request<{ saved: boolean; app_configured: boolean }>(`/api/v1/oauth/${platform}/app`, {
    method: "POST",
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
  });

export const saveManualToken = (
  platform: string,
  body: { access_token: string; refresh_token?: string; expires_in_days?: number }
) =>
  request<{ connected: boolean; account_name: string | null; expires_at: number | null }>(
    `/api/v1/oauth/${platform}/manual-token`,
    { method: "POST", body: JSON.stringify(body) }
  );

export const testConnection = (platform: string) =>
  request<OAuthTestOut>(`/api/v1/oauth/${platform}/test`, { method: "POST" });

export const refreshConnection = (platform: string) =>
  request<{ ok: boolean; expires_at: number | null; expires_in_days: number | null }>(
    `/api/v1/oauth/${platform}/refresh`,
    { method: "POST" }
  );

export const disconnectPlatform = (platform: string) =>
  request<{ disconnected: boolean }>(`/api/v1/oauth/${platform}`, { method: "DELETE" });

// Analytics
export const getProjectSummary = (slug: string) =>
  request<AnalyticsSummary>(`/api/v1/analytics/summary/${slug}`);

export const getStrategy = (slug: string) =>
  request<StrategyInsight>(`/api/v1/analytics/strategy/${slug}`);

export const collectAnalytics = (slug: string) =>
  request(`/api/v1/analytics/collect/${slug}`, { method: "POST" });
