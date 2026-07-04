"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";
import { PlatformChip } from "@/components/ui/PlatformChip";
import { PROJECT_COLORS } from "@/components/ProjectSelector";
import type { Content } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";
import { Send, Clock, Check, Image as ImageIcon, Video, Type, Sparkles } from "lucide-react";
import useSWR from "swr";
import { getProjects } from "@/lib/api";

interface ContentCardProps {
  content: Content;
  onPostNow?: (id: string) => void;
  onSchedule?: (id: string) => void;
  onApprove?: (id: string) => void;
}

const TYPE_ICON = { text: Type, image: ImageIcon, video: Video, reel: Sparkles } as const;

const mono9: React.CSSProperties = { fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase" };

export function ContentCard({ content, onPostNow, onSchedule, onApprove }: ContentCardProps) {
  const { data: projects } = useSWR("projects", getProjects);
  const project = projects?.find(p => p.id === content.project_id);
  const accent = project ? PROJECT_COLORS[project.slug] || "#0055FF" : "#0055FF";
  const TypeIcon = TYPE_ICON[content.content_type] ?? Type;
  const showActions = content.status === "approved" || content.status === "pending_approval";

  return (
    <div style={{
      background: "#0b0b14",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 14,
      padding: "16px 20px",
      position: "relative",
      overflow: "hidden",
      boxShadow: `inset 3px 0 0 0 ${accent}`,
      transition: "border-color 0.2s",
    }}>
      {/* Top hairline */}
      <div style={{ position: "absolute", top: 0, left: 20, right: 20, height: 1, background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.07), transparent)", pointerEvents: "none" }} />

      {/* Meta row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <StatusBadge status={content.status} />
          {project && (
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "3px 9px", borderRadius: 20,
              background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)",
              ...mono9, color: "#8a8a98",
            }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: accent, boxShadow: `0 0 5px ${accent}`, flexShrink: 0 }} />
              {project.slug}
            </span>
          )}
          <span style={{ ...mono9, color: "#36363f" }}>{formatDistanceToNow(new Date(content.created_at), { addSuffix: true })}</span>
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0, flexWrap: "wrap" }}>
          {content.platforms.map(p => (
            <PlatformChip key={p} platform={p} size="sm" />
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
        <div style={{
          flexShrink: 0, width: 38, height: 38, borderRadius: 10,
          display: "flex", alignItems: "center", justifyContent: "center",
          background: `linear-gradient(135deg, ${accent}28, ${accent}08)`,
          border: "1px solid rgba(255,255,255,0.07)",
        }}>
          <TypeIcon size={15} style={{ color: accent }} strokeWidth={1.75} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          {content.title && (
            <div style={{ fontSize: 14, fontWeight: 600, color: "#f5f5f7", marginBottom: 4, letterSpacing: "-0.01em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {content.title}
            </div>
          )}
          {content.body && (
            <div style={{
              fontSize: 13, color: "#8a8a98", lineHeight: 1.6,
              fontFamily: "var(--font-serif), Georgia, serif",
              overflow: "hidden", display: "-webkit-box",
              WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
            }}>
              {content.body}
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      {showActions && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid rgba(255,255,255,0.06)", display: "flex", gap: 8 }}>
          {content.status === "pending_approval" && onApprove && (
            <button onClick={() => onApprove(content.id)} style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "7px 14px", borderRadius: 8, minHeight: 34,
              background: "rgba(0,221,136,0.08)", border: "1px solid rgba(0,221,136,0.25)",
              color: "#00DD88", fontSize: 12, fontWeight: 500, cursor: "pointer",
            }}>
              <Check size={12} strokeWidth={2} /> Approve
            </button>
          )}
          {content.status === "approved" && (
            <>
              {onPostNow && (
                <button onClick={() => onPostNow(content.id)} style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "7px 14px", borderRadius: 8, minHeight: 34,
                  background: "#0055FF", border: "1px solid #0055FF",
                  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.15)",
                  color: "#fff", fontSize: 12, fontWeight: 500, cursor: "pointer",
                }}>
                  <Send size={12} strokeWidth={1.75} /> Post Now
                </button>
              )}
              {onSchedule && (
                <button onClick={() => onSchedule(content.id)} style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "7px 14px", borderRadius: 8, minHeight: 34,
                  background: "transparent", border: "1px solid rgba(255,255,255,0.09)",
                  color: "#8a8a98", fontSize: 12, fontWeight: 500, cursor: "pointer",
                }}>
                  <Clock size={12} strokeWidth={1.75} /> Schedule
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
