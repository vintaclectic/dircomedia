"use client";

import { useState } from "react";
import type { Platform } from "@/lib/types";

interface PlatformDef {
  key: Platform;
  label: string;
  color: string;
  gradient?: string;
  glyph: React.ReactNode;
}

const ICON_SIZE = 20;

const PLATFORMS: PlatformDef[] = [
  {
    key: "twitter",
    label: "X",
    color: "#e7e9ea",
    glyph: (
      <svg viewBox="0 0 24 24" width={ICON_SIZE} height={ICON_SIZE} fill="currentColor" aria-hidden style={{ display: "block" }}>
        {/* Crossed blades */}
        <path d="M3.2 2.4 L5.6 2.4 L21 19.8 L18.6 21.6 Z" />
        <path d="M20.8 2.4 L18.4 2.4 L3 19.8 L5.4 21.6 Z" />
      </svg>
    ),
  },
  {
    key: "tiktok",
    label: "TikTok",
    color: "#25F4EE",
    glyph: (
      <svg viewBox="0 0 24 24" width={ICON_SIZE} height={ICON_SIZE} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter" aria-hidden style={{ display: "block" }}>
        {/* Circuit note */}
        <path d="M9 19 L9 5 L17 5 L17 9" />
        <circle cx="9" cy="19" r="2.6" fill="currentColor" stroke="none" />
        <rect x="15.5" y="7.5" width="3" height="3" fill="currentColor" stroke="none" />
        <path d="M9 5 L6 5" strokeWidth="1.4" opacity="0.6" />
        <path d="M17 9 L20 9" strokeWidth="1.4" opacity="0.6" />
      </svg>
    ),
  },
  {
    key: "instagram",
    label: "Instagram",
    color: "#E1306C",
    gradient: "linear-gradient(135deg, #E1306C 0%, #F77737 50%, #FCAF45 100%)",
    glyph: (
      <svg viewBox="0 0 24 24" width={ICON_SIZE} height={ICON_SIZE} aria-hidden style={{ display: "block" }}>
        <defs>
          <linearGradient id="grid-iris-grad" x1="4" y1="20" x2="20" y2="4" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#E1306C" />
            <stop offset="100%" stopColor="#FCAF45" />
          </linearGradient>
        </defs>
        {/* Iris aperture */}
        <circle cx="12" cy="12" r="10" fill="none" stroke="url(#grid-iris-grad)" strokeWidth="1.5" />
        <path d="M12 3.5 L17.5 6 L12 12 Z" fill="url(#grid-iris-grad)" />
        <path d="M17.5 6 L20.5 11.5 L12 12 Z" fill="url(#grid-iris-grad)" opacity="0.7" />
        <path d="M20.5 11.5 L17.5 18 L12 12 Z" fill="url(#grid-iris-grad)" />
        <path d="M17.5 18 L12 20.5 L12 12 Z" fill="url(#grid-iris-grad)" opacity="0.7" />
        <path d="M12 20.5 L6.5 18 L12 12 Z" fill="url(#grid-iris-grad)" />
        <path d="M6.5 18 L3.5 12.5 L12 12 Z" fill="url(#grid-iris-grad)" opacity="0.7" />
        <path d="M3.5 12.5 L6.5 6 L12 12 Z" fill="url(#grid-iris-grad)" />
        <path d="M6.5 6 L12 3.5 L12 12 Z" fill="url(#grid-iris-grad)" opacity="0.7" />
        <circle cx="12" cy="12" r="2.2" fill="#0b0b14" />
      </svg>
    ),
  },
  {
    key: "reddit",
    label: "Reddit",
    color: "#FF4500",
    glyph: (
      <svg viewBox="0 0 24 24" width={ICON_SIZE} height={ICON_SIZE} fill="currentColor" aria-hidden style={{ display: "block" }}>
        {/* Cosmic mask */}
        <path d="M12 2 L12 4.8" stroke="currentColor" strokeWidth="1.5" fill="none" />
        <circle cx="12" cy="2.2" r="1.1" />
        <path d="M4 9 L12 6 L20 9 L18 18 L12 21 L6 18 Z" />
        <path d="M7.5 11.5 L10.5 11 L10.5 13 L7.5 13.5 Z" fill="#0b0b14" />
        <path d="M16.5 11.5 L13.5 11 L13.5 13 L16.5 13.5 Z" fill="#0b0b14" />
        <path d="M10 16.5 L14 16.5 L13 17.5 L11 17.5 Z" fill="#0b0b14" />
      </svg>
    ),
  },
];

interface PlatformGridProps {
  value: Platform[];
  onChange: (platforms: Platform[]) => void;
}

export function PlatformGrid({ value, onChange }: PlatformGridProps) {
  const [hovered, setHovered] = useState<Platform | null>(null);

  const toggle = (p: Platform) => {
    onChange(value.includes(p) ? value.filter((x) => x !== p) : [...value, p]);
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        gap: 10,
      }}
    >
      {PLATFORMS.map(({ key, label, color, gradient, glyph }) => {
        const selected = value.includes(key);
        const isHover = hovered === key;
        const iconFill = selected ? color : isHover ? "#c8c8d2" : "#56565f";
        const iconBg = selected
          ? gradient || `${color}22`
          : "transparent";

        return (
          <button
            key={key}
            type="button"
            onClick={() => toggle(key)}
            onMouseEnter={() => setHovered(key)}
            onMouseLeave={() => setHovered(null)}
            aria-pressed={selected}
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              gap: 12,
              minHeight: 56,
              minWidth: 80,
              padding: "12px 14px",
              borderRadius: 12,
              background: selected
                ? `${color}14`
                : isHover
                  ? "rgba(255,255,255,0.05)"
                  : "rgba(255,255,255,0.03)",
              border: `1px solid ${
                selected
                  ? `${color}55`
                  : isHover
                    ? "rgba(255,255,255,0.14)"
                    : "rgba(255,255,255,0.08)"
              }`,
              boxShadow: selected
                ? `0 0 20px ${color}22, inset 0 1px 0 rgba(255,255,255,0.06)`
                : "none",
              color: selected ? "#f5f5f7" : "#8a8a98",
              cursor: "pointer",
              transition:
                "background 180ms ease, border-color 180ms ease, box-shadow 220ms ease, transform 120ms ease",
              transform: selected ? "translateY(-1px)" : "translateY(0)",
              overflow: "hidden",
              textAlign: "left",
              WebkitTapHighlightColor: "transparent",
            }}
          >
            {/* Icon tile */}
            <span
              aria-hidden
              style={{
                position: "relative",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 36,
                height: 36,
                borderRadius: 9,
                background: iconBg,
                border: selected
                  ? `1px solid ${color}33`
                  : "1px solid rgba(255,255,255,0.06)",
                flexShrink: 0,
                transition: "background 180ms ease, border-color 180ms ease",
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  color: selected && gradient ? "#ffffff" : iconFill,
                  transition: "color 180ms ease",
                  filter: selected ? `drop-shadow(0 0 6px ${color}55)` : "none",
                }}
              >
                {glyph}
              </span>
            </span>

            {/* Label */}
            <span
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 2,
                minWidth: 0,
                flex: 1,
              }}
            >
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  letterSpacing: "-0.01em",
                  color: selected ? "#f5f5f7" : "#c8c8d2",
                  lineHeight: 1.1,
                }}
              >
                {label}
              </span>
              <span
                style={{
                  fontFamily: "var(--font-mono), monospace",
                  fontSize: 9,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: selected ? `${color}` : "#36363f",
                  opacity: selected ? 0.85 : 1,
                  lineHeight: 1,
                }}
              >
                {selected ? "Selected" : "Tap to add"}
              </span>
            </span>

            {/* Selected indicator dot */}
            {selected && (
              <span
                aria-hidden
                style={{
                  position: "absolute",
                  top: 8,
                  right: 8,
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: color,
                  boxShadow: `0 0 8px ${color}`,
                  flexShrink: 0,
                }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
