"use client";

import { useEffect, useState } from "react";
import { Check, Eye, EyeOff, Save, ExternalLink } from "lucide-react";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const mono9: React.CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  fontSize: 9, letterSpacing: "0.22em",
  textTransform: "uppercase", color: "#36363f",
};

// ─── platform groups ──────────────────────────────────────────────────────────
const GROUPS = [
  {
    id: "twitter",
    label: "X / Twitter",
    color: "#ffffff",
    docsUrl: "https://developer.x.com/en/portal/dashboard",
    fields: [
      { key: "twitter_api_key",       label: "API Key",         hint: "Consumer Key" },
      { key: "twitter_api_secret",    label: "API Secret",      hint: "Consumer Secret" },
      { key: "twitter_access_token",  label: "Access Token",    hint: "From your app dashboard" },
      { key: "twitter_access_secret", label: "Access Secret",   hint: "Access Token Secret" },
      { key: "twitter_bearer_token",  label: "Bearer Token",    hint: "App-only auth" },
    ],
  },
  {
    id: "tiktok",
    label: "TikTok",
    color: "#25F4EE",
    docsUrl: "https://developers.tiktok.com/",
    fields: [
      { key: "tiktok_client_key",    label: "Client Key",    hint: "From TikTok developer portal" },
      { key: "tiktok_client_secret", label: "Client Secret", hint: "" },
      { key: "tiktok_access_token",  label: "Access Token",  hint: "User access token" },
    ],
  },
  {
    id: "instagram",
    label: "Instagram",
    color: "#E1306C",
    docsUrl: "https://developers.facebook.com/apps/",
    fields: [
      { key: "instagram_app_id",       label: "App ID",          hint: "Facebook App ID" },
      { key: "instagram_app_secret",   label: "App Secret",      hint: "Facebook App Secret" },
      { key: "instagram_access_token", label: "Access Token",    hint: "Long-lived page token" },
    ],
  },
  {
    id: "reddit",
    label: "Reddit",
    color: "#FF4500",
    docsUrl: "https://www.reddit.com/prefs/apps",
    fields: [
      { key: "reddit_client_id",     label: "Client ID",     hint: "Under your app name" },
      { key: "reddit_client_secret", label: "Client Secret", hint: "" },
      { key: "reddit_username",      label: "Username",      hint: "Your reddit username", plain: true },
      { key: "reddit_password",      label: "Password",      hint: "Your reddit password" },
    ],
  },
  {
    id: "video",
    label: "Video Pipeline",
    color: "#7C3AED",
    docsUrl: "https://creatomate.com/",
    fields: [
      { key: "creatomate_api_key", label: "Creatomate API Key", hint: "Video assembly" },
      { key: "runway_api_key",     label: "Runway API Key",     hint: "AI video generation" },
      { key: "heygen_api_key",     label: "HeyGen API Key",     hint: "AI voiceover / avatar" },
    ],
  },
];

type FieldDef = { key: string; label: string; hint: string; plain?: boolean };

function Field({
  def, value, onChange, visible, onToggleVisible, saved,
}: {
  def: FieldDef;
  value: string;
  onChange: (v: string) => void;
  visible: boolean;
  onToggleVisible: () => void;
  saved: boolean;
}) {
  const isMasked = value && value.includes("•");
  const inputType = def.plain ? "text" : visible ? "text" : "password";

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <label style={{ fontSize: 12, fontWeight: 500, color: "#c8c8d2", letterSpacing: "-0.01em" }}>{def.label}</label>
        {def.hint && <span style={{ ...mono9, fontSize: 8.5 }}>{def.hint}</span>}
      </div>
      <div style={{ position: "relative" }}>
        <input
          type={inputType}
          value={value}
          placeholder={isMasked ? "" : "Not set"}
          onChange={e => onChange(e.target.value)}
          onFocus={e => { if (isMasked) { onChange(""); } }}
          style={{
            width: "100%", boxSizing: "border-box",
            background: "rgba(255,255,255,0.03)",
            border: `1px solid ${saved ? "rgba(0,221,136,0.4)" : "rgba(255,255,255,0.09)"}`,
            borderRadius: 9, padding: "10px 40px 10px 14px",
            color: isMasked ? "#56565f" : "#f5f5f7",
            fontSize: 13, outline: "none", letterSpacing: isMasked ? "0.08em" : "normal",
            fontFamily: "var(--font-mono), monospace",
            transition: "border-color 0.2s",
          }}
          onMouseEnter={e => { (e.target as HTMLInputElement).style.borderColor = "rgba(255,255,255,0.18)"; }}
          onMouseLeave={e => { (e.target as HTMLInputElement).style.borderColor = saved ? "rgba(0,221,136,0.4)" : "rgba(255,255,255,0.09)"; }}
        />
        {!def.plain && (
          <button
            onClick={onToggleVisible}
            style={{
              position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
              background: "none", border: "none", color: "#36363f", cursor: "pointer", padding: 4,
              display: "flex", alignItems: "center",
            }}
          >
            {visible ? <EyeOff size={13} /> : <Eye size={13} />}
          </button>
        )}
        {saved && (
          <div style={{ position: "absolute", right: def.plain ? 10 : 32, top: "50%", transform: "translateY(-50%)" }}>
            <Check size={12} color="#00DD88" />
          </div>
        )}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [values, setValues]   = useState<Record<string, string>>({});
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [saved, setSaved]     = useState<Record<string, boolean>>({});
  const [saving, setSaving]   = useState(false);
  const [flash, setFlash]     = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BASE}/api/v1/settings/`)
      .then(r => r.json())
      .then(data => { setValues(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const set = (key: string, val: string) => {
    setValues(v => ({ ...v, [key]: val }));
    setSaved(s => ({ ...s, [key]: false }));
  };

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${BASE}/api/v1/settings/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      const data = await res.json();
      // Mark saved fields
      const savedMap: Record<string, boolean> = {};
      for (const k of (data.keys || [])) {
        // map env key back to field key
        const fieldKey = k.toLowerCase();
        savedMap[fieldKey] = true;
      }
      setSaved(savedMap);
      setFlash(`${data.saved} key${data.saved !== 1 ? "s" : ""} saved`);
      setTimeout(() => setFlash(""), 3000);
    } catch {
      setFlash("Save failed");
      setTimeout(() => setFlash(""), 3000);
    }
    setSaving(false);
  };

  return (
    <div style={{ minHeight: "100vh" }}>

      {/* Header */}
      <div style={{
        position: "sticky", top: 0, zIndex: 20,
        background: "rgba(2,2,5,0.88)", backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        padding: "18px 32px",
        display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16,
      }}>
        <div>
          <div style={{ ...mono9, marginBottom: 5 }}>Configuration</div>
          <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 40, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>SETTINGS</div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {flash && (
            <span style={{ ...mono9, color: flash.includes("failed") ? "#FF3B47" : "#00DD88" }}>{flash}</span>
          )}
          <button
            onClick={save}
            disabled={saving || loading}
            style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "10px 20px", borderRadius: 9, minHeight: 40,
              background: "#0055FF", border: "1px solid #0055FF",
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.15), 0 0 0 1px rgba(0,85,255,0.3)",
              color: "#fff", fontSize: 13, fontWeight: 600,
              cursor: saving ? "not-allowed" : "pointer",
              opacity: saving ? 0.6 : 1, transition: "opacity 0.2s",
            }}
          >
            {saving
              ? <><span style={{ width: 12, height: 12, border: "1.5px solid rgba(255,255,255,0.5)", borderTopColor: "transparent", borderRadius: "50%", animation: "_spin 0.65s linear infinite" }} />Saving</>
              : <><Save size={13} />Save All</>
            }
          </button>
        </div>
      </div>

      <div style={{ padding: "32px 32px", maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>

        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {[0,1,2].map(i => <div key={i} className="shimmer" style={{ height: 180, borderRadius: 14 }} />)}
          </div>
        ) : (
          GROUPS.map(group => (
            <div key={group.id} style={{
              background: "#0b0b14",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 14, overflow: "hidden",
              boxShadow: `inset 3px 0 0 0 ${group.color}66`,
            }}>
              {/* Group header */}
              <div style={{
                padding: "16px 22px 14px",
                borderBottom: "1px solid rgba(255,255,255,0.06)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: group.color, boxShadow: `0 0 8px ${group.color}` }} />
                  <span style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 20, color: "#f5f5f7", letterSpacing: "0.04em" }}>{group.label.toUpperCase()}</span>
                </div>
                <a
                  href={group.docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: "inline-flex", alignItems: "center", gap: 5, ...mono9, color: "#56565f", textDecoration: "none" }}
                >
                  Get keys <ExternalLink size={10} />
                </a>
              </div>

              {/* Fields */}
              <div style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
                {group.fields.map(f => (
                  <Field
                    key={f.key}
                    def={f}
                    value={values[f.key] || ""}
                    onChange={v => set(f.key, v)}
                    visible={!!visible[f.key]}
                    onToggleVisible={() => setVisible(v => ({ ...v, [f.key]: !v[f.key] }))}
                    saved={!!saved[f.key.toUpperCase()] || !!saved[f.key]}
                  />
                ))}
              </div>
            </div>
          ))
        )}

        <div style={{
          background: "rgba(255,176,32,0.06)", border: "1px solid rgba(255,176,32,0.2)",
          borderRadius: 12, padding: "14px 18px",
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#FFB020", boxShadow: "0 0 6px #FFB020", flexShrink: 0, marginTop: 3 }} />
          <div style={{ fontSize: 12, color: "#8a8a98", lineHeight: 1.6 }}>
            Keys are stored in your local <code style={{ fontFamily: "var(--font-mono), monospace", fontSize: 11, color: "#c8c8d2", background: "rgba(255,255,255,0.06)", padding: "1px 5px", borderRadius: 4 }}>.env</code> file on your server and never transmitted externally. Existing keys are masked — click a field and type a new value to replace it.
          </div>
        </div>
      </div>

      <style>{`@keyframes _spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
