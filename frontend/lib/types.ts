export type ContentType = "text" | "image" | "video" | "reel";
export type ContentStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "scheduled"
  | "posted"
  | "failed";
export type Platform = "twitter" | "tiktok" | "instagram" | "reddit";

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
