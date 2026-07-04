"use client";

import type { Platform } from "@/lib/types";

interface PlatformChipProps {
  platform: Platform;
  size?: "sm" | "md";
}

interface PlatformMeta {
  label: string;
  color: string;
  gradient?: string;
  glyph: (size: number) => React.ReactNode;
}

const PLATFORM_META: Record<Platform, PlatformMeta> = {
  twitter: {
    label: "X",
    color: "#e7e9ea",
    glyph: (s) => (
      <svg viewBox="0 0 24 24" width={s} height={s} fill="currentColor" aria-hidden style={{ display: "block" }}>
        {/* Crossed blades — two asymmetric parallelograms meeting at center */}
        <path d="M3.2 2.4 L5.6 2.4 L21 19.8 L18.6 21.6 Z" />
        <path d="M20.8 2.4 L18.4 2.4 L3 19.8 L5.4 21.6 Z" />
      </svg>
    ),
  },
  tiktok: {
    label: "TikTok",
    color: "#25F4EE",
    glyph: (s) => (
      <svg viewBox="0 0 24 24" width={s} height={s} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter" aria-hidden style={{ display: "block" }}>
        {/* Circuit note — stem + right-angle trace with solder pads */}
        <path d="M9 19 L9 5 L17 5 L17 9" />
        <circle cx="9" cy="19" r="2.6" fill="currentColor" stroke="none" />
        <rect x="15.5" y="7.5" width="3" height="3" fill="currentColor" stroke="none" />
        <path d="M9 5 L6 5" strokeWidth="1.4" opacity="0.6" />
        <path d="M17 9 L20 9" strokeWidth="1.4" opacity="0.6" />
      </svg>
    ),
  },
  instagram: {
    label: "Instagram",
    color: "#E1306C",
    gradient: "linear-gradient(135deg, #E1306C 0%, #F77737 50%, #FCAF45 100%)",
    glyph: (s) => (
      <svg viewBox="0 0 24 24" width={s} height={s} aria-hidden style={{ display: "block" }}>
        <defs>
          <linearGradient id="chip-iris-grad" x1="4" y1="20" x2="20" y2="4" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#E1306C" />
            <stop offset="100%" stopColor="#FCAF45" />
          </linearGradient>
        </defs>
        {/* Iris aperture — 8 blades + outer ring + dark pupil */}
        <circle cx="12" cy="12" r="10" fill="none" stroke="url(#chip-iris-grad)" strokeWidth="1.5" />
        <path d="M12 3.5 L17.5 6 L12 12 Z" fill="url(#chip-iris-grad)" />
        <path d="M17.5 6 L20.5 11.5 L12 12 Z" fill="url(#chip-iris-grad)" opacity="0.7" />
        <path d="M20.5 11.5 L17.5 18 L12 12 Z" fill="url(#chip-iris-grad)" />
        <path d="M17.5 18 L12 20.5 L12 12 Z" fill="url(#chip-iris-grad)" opacity="0.7" />
        <path d="M12 20.5 L6.5 18 L12 12 Z" fill="url(#chip-iris-grad)" />
        <path d="M6.5 18 L3.5 12.5 L12 12 Z" fill="url(#chip-iris-grad)" opacity="0.7" />
        <path d="M3.5 12.5 L6.5 6 L12 12 Z" fill="url(#chip-iris-grad)" />
        <path d="M6.5 6 L12 3.5 L12 12 Z" fill="url(#chip-iris-grad)" opacity="0.7" />
        <circle cx="12" cy="12" r="2.2" fill="#0b0b14" />
      </svg>
    ),
  },
  reddit: {
    label: "Reddit",
    color: "#FF4500",
    glyph: (s) => (
      <svg viewBox="0 0 24 24" width={s} height={s} fill="currentColor" aria-hidden style={{ display: "block" }}>
        {/* Cosmic mask — hexagonal helmet, antenna node, slit eyes + mouth */}
        <path d="M12 2 L12 4.8" stroke="currentColor" strokeWidth="1.5" fill="none" />
        <circle cx="12" cy="2.2" r="1.1" />
        <path d="M4 9 L12 6 L20 9 L18 18 L12 21 L6 18 Z" />
        <path d="M7.5 11.5 L10.5 11 L10.5 13 L7.5 13.5 Z" fill="#0b0b14" />
        <path d="M16.5 11.5 L13.5 11 L13.5 13 L16.5 13.5 Z" fill="#0b0b14" />
        <path d="M10 16.5 L14 16.5 L13 17.5 L11 17.5 Z" fill="#0b0b14" />
      </svg>
    ),
  },
};

export function PlatformChip({ platform, size = "sm" }: PlatformChipProps) {
  const meta = PLATFORM_META[platform];
  if (!meta) return null;

  const isMd = size === "md";
  const iconSize = isMd ? 14 : 12;
  const height = isMd ? 28 : 24;
  const padX = isMd ? 12 : 10;
  const fontSize = isMd ? 11 : 10;

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        height,
        padding: `0 ${padX}px`,
        borderRadius: 6,
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.09)",
        whiteSpace: "nowrap",
        lineHeight: 1,
      }}
    >
      <span
        aria-hidden
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: iconSize,
          height: iconSize,
          color: meta.color,
          opacity: 0.7,
          flexShrink: 0,
        }}
      >
        {meta.glyph(iconSize)}
      </span>
      <span
        style={{
          fontFamily: "var(--font-mono), monospace",
          fontSize,
          letterSpacing: "0.04em",
          color: "#8a8a98",
          lineHeight: 1,
        }}
      >
        {meta.label}
      </span>
    </span>
  );
}

export function PlatformChipGroup({ platforms, size = "sm" }: { platforms: Platform[]; size?: "sm" | "md" }) {
  return (
    <span style={{ display: "inline-flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
      {platforms.map((p) => (
        <PlatformChip key={p} platform={p} size={size} />
      ))}
    </span>
  );
}
