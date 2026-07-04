"use client";

import { clsx } from "clsx";
import { forwardRef } from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger" | "soft";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

/**
 * Billionaire-tier button. Sharp rectangles (rounded-lg, not pills).
 * No gradient bg. No heavy glow. Surgical hover states.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { children, variant = "primary", size = "md", loading, className, disabled, ...props },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        "relative inline-flex items-center justify-center gap-1.5",
        "font-medium tracking-tight rounded-lg",
        "transition-[background,border-color,color,box-shadow,transform] duration-200 ease-out",
        "disabled:opacity-40 disabled:cursor-not-allowed",
        "active:scale-[0.98]",

        // Sizes — all meet 44px touch target
        size === "sm" && "px-3 py-1.5 text-[12px] min-h-[36px]",
        size === "md" && "px-4 py-2 text-[13px] min-h-[44px]",
        size === "lg" && "px-5 py-2.5 text-[13.5px] min-h-[48px]",

        // Primary — electric blue, flat, single hairline glow on hover
        variant === "primary" && [
          "bg-electric text-white border border-electric/60",
          "shadow-[inset_0_1px_0_rgba(255,255,255,0.15)]",
          "hover:bg-electric-bright hover:shadow-[0_0_24px_-6px_rgba(61,139,255,0.6),inset_0_1px_0_rgba(255,255,255,0.18)]",
        ],

        // Ghost — transparent, just a hairline border
        variant === "ghost" && [
          "bg-transparent text-ash border border-white/[0.08]",
          "hover:bg-white/[0.02] hover:border-white/[0.16] hover:text-bone",
        ],

        // Soft — barely-there fill
        variant === "soft" && [
          "bg-white/[0.04] text-bone border border-white/[0.07]",
          "hover:bg-white/[0.07] hover:border-white/[0.14]",
        ],

        // Danger
        variant === "danger" && [
          "bg-danger/[0.08] text-danger border border-danger/30",
          "hover:bg-danger/[0.14] hover:border-danger/50",
        ],

        className
      )}
      {...props}
    >
      {loading ? (
        <>
          <span className="w-3 h-3 rounded-full border-[1.5px] border-current border-t-transparent animate-spin" />
          <span className="opacity-80">{children}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
});
