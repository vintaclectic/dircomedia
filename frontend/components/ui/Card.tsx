import { forwardRef } from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: "glass" | "solid" | "outline";
  accent?: string;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { children, variant = "glass", accent, style, onClick, className, ...rest },
  ref
) {
  return (
    <div
      ref={ref}
      onClick={onClick}
      className={className}
      style={{
        position: "relative",
        borderRadius: 14,
        overflow: "hidden",
        background: variant === "solid" ? "#0d0d1a" : "rgba(255,255,255,0.035)",
        border: variant === "outline" ? "1px solid rgba(255,255,255,0.12)" : "1px solid rgba(255,255,255,0.09)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        cursor: onClick ? "pointer" : undefined,
        ...(accent ? { boxShadow: `inset 3px 0 0 0 ${accent}` } : {}),
        ...style,
      }}
      {...rest}
    >
      {/* Top hairline */}
      <div style={{
        position: "absolute", top: 0, left: 16, right: 16, height: 1, pointerEvents: "none",
        background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.09), transparent)",
      }} />
      {children}
    </div>
  );
});
