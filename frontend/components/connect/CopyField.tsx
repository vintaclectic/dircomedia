"use client";
/**
 * CopyField — a value you must paste somewhere else, with one-tap copy (YH9AE4D).
 *
 * The redirect URI is the single highest-friction string in the whole wizard:
 * one typo and OAuth fails with an error the platform words unhelpfully. Retyping
 * it by hand on a phone is where this flow would actually break, so copy is a
 * 44px target and the value wraps instead of scrolling out of view.
 *
 * NO-COLLISION: value and button are separate flex cells; the value column has
 * minWidth:0 + overflowWrap so a long URI grows the box downward. The button
 * never sits on top of the text.
 */
import { useState } from "react";
import { Copy, Check } from "lucide-react";

export function CopyField({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Clipboard API needs a secure context; on plain http:// LAN dev it
      // throws. Fall back to a selection-based copy so the button still works
      // rather than silently doing nothing.
      const ta = document.createElement("textarea");
      ta.value = value;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch {}
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
      <label
        style={{
          fontFamily: "var(--font-mono), monospace",
          fontSize: 9,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          color: "#56565f",
        }}
      >
        {label}
      </label>
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
          gap: 8,
          padding: 8,
          borderRadius: 10,
          background: "rgba(7,7,14,0.7)",
          border: "1px solid rgba(255,255,255,0.08)",
          minWidth: 0,
        }}
      >
        <code
          style={{
            flex: "1 1 auto",
            minWidth: 0,
            display: "flex",
            alignItems: "center",
            fontFamily: "var(--font-mono), monospace",
            fontSize: 11.5,
            color: "#c8c8d2",
            lineHeight: 1.5,
            overflowWrap: "anywhere",
            wordBreak: "break-all",
          }}
        >
          {value}
        </code>
        <button
          onClick={copy}
          aria-label={`Copy ${label}`}
          style={{
            flexShrink: 0,
            minWidth: 44,
            minHeight: 44,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "0 12px",
            borderRadius: 8,
            border: `1px solid ${copied ? "rgba(0,221,136,0.4)" : "rgba(255,255,255,0.1)"}`,
            background: copied ? "rgba(0,221,136,0.12)" : "rgba(255,255,255,0.04)",
            color: copied ? "#00DD88" : "#8a8a98",
            fontSize: 11.5,
            fontWeight: 500,
            cursor: "pointer",
            transition: "all 0.18s",
          }}
        >
          {copied ? <Check size={14} strokeWidth={2.2} /> : <Copy size={14} strokeWidth={1.9} />}
          <span style={{ whiteSpace: "nowrap" }}>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      {hint && (
        <p style={{ margin: 0, fontSize: 11.5, color: "#56565f", lineHeight: 1.5, overflowWrap: "anywhere" }}>
          {hint}
        </p>
      )}
    </div>
  );
}

export function SecretInput({
  label,
  value,
  onChange,
  placeholder,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  hint?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
      <label
        style={{
          fontFamily: "var(--font-mono), monospace",
          fontSize: 9,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          color: "#56565f",
        }}
      >
        {label}
      </label>
      <div style={{ display: "flex", gap: 8, minWidth: 0 }}>
        <input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          style={{
            flex: "1 1 auto",
            minWidth: 0,
            width: "100%",
            minHeight: 44,
            padding: "0 12px",
            borderRadius: 10,
            fontFamily: "var(--font-mono), monospace",
            fontSize: 12.5,
          }}
        />
        <button
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? `Hide ${label}` : `Show ${label}`}
          style={{
            flexShrink: 0,
            minWidth: 44,
            minHeight: 44,
            borderRadius: 10,
            border: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(255,255,255,0.04)",
            color: "#8a8a98",
            fontSize: 11,
            fontFamily: "var(--font-mono), monospace",
            letterSpacing: "0.1em",
            cursor: "pointer",
          }}
        >
          {visible ? "HIDE" : "SHOW"}
        </button>
      </div>
      {hint && (
        <p style={{ margin: 0, fontSize: 11.5, color: "#56565f", lineHeight: 1.5, overflowWrap: "anywhere" }}>
          {hint}
        </p>
      )}
    </div>
  );
}
