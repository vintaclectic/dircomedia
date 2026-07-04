"use client";

import useSWR from "swr";
import { getProjects } from "@/lib/api";
import { clsx } from "clsx";

// Project colors — corrected to spec
export const PROJECT_COLORS: Record<string, string> = {
  "dirco": "#0055FF",
  "dirhaven-rp": "#FF2222",
  "dirhaven-app": "#00DD88",
  "dirmegle": "#FF5500",
  "medaled": "#FFD700",
  "agentis": "#7C3AED",
  "vintinuum": "#F0287A",
};

interface ProjectSelectorProps {
  value: string;
  onChange: (slug: string) => void;
}

export function ProjectSelector({ value, onChange }: ProjectSelectorProps) {
  const { data: projects } = useSWR("projects", getProjects);

  if (!projects) {
    return (
      <div className="flex gap-2 flex-wrap">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-9 w-24 rounded-lg shimmer" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {projects.map((p) => {
        const color = PROJECT_COLORS[p.slug] || "#666";
        const active = value === p.slug;
        return (
          <button
            key={p.slug}
            data-project={p.slug}
            onClick={() => {
              onChange(p.slug);
              if (typeof document !== "undefined") {
                document.body.setAttribute("data-project", p.slug);
              }
            }}
            className={clsx(
              "group relative inline-flex items-center gap-2 px-3 py-2 rounded-lg",
              "text-[12px] font-medium transition-all duration-300 ease-out-expo",
              "border backdrop-blur-sm touch min-h-[36px]",
              "active:scale-[0.97]",
              active
                ? "text-bone bg-white/[0.06] border-white/[0.18] -translate-y-[1px]"
                : "text-dust border-white/[0.06] hover:border-white/[0.12] hover:text-smoke hover:bg-white/[0.025]"
            )}
            style={
              active
                ? {
                    borderColor: `${color}88`,
                    boxShadow: `0 0 28px -6px ${color}66, inset 0 1px 0 rgba(255,255,255,0.08), 0 0 0 1px ${color}33`,
                  }
                : undefined
            }
          >
            <span className="relative inline-flex items-center justify-center w-3 h-3">
              <span
                className={clsx(
                  "absolute inset-0 rounded-full transition-all duration-500",
                  active ? "opacity-100 blur-[7px] scale-150" : "opacity-40 blur-[3px] group-hover:opacity-70"
                )}
                style={{ background: color }}
              />
              <span
                className="relative w-1.5 h-1.5 rounded-full"
                style={{
                  background: color,
                  boxShadow: active ? `0 0 10px ${color}` : `0 0 5px ${color}80`,
                }}
              />
            </span>
            <span className="tracking-tight">{p.name}</span>
            {active && (
              <span
                className="mono text-[9px] ml-0.5"
                style={{ color }}
              >
                ●
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
