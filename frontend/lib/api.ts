import type {
  Project,
  Content,
  Schedule,
  AnalyticsSummary,
  StrategyInsight,
  GenerateRequest,
  VideoJobOut,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const OWNER_TOKEN = process.env.NEXT_PUBLIC_OWNER_TOKEN || "";

function authHeaders(): Record<string, string> {
  return OWNER_TOKEN ? { Authorization: `Bearer ${OWNER_TOKEN}` } : {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
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
    headers: authHeaders(),
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

// Analytics
export const getProjectSummary = (slug: string) =>
  request<AnalyticsSummary>(`/api/v1/analytics/summary/${slug}`);

export const getStrategy = (slug: string) =>
  request<StrategyInsight>(`/api/v1/analytics/strategy/${slug}`);

export const collectAnalytics = (slug: string) =>
  request(`/api/v1/analytics/collect/${slug}`, { method: "POST" });
