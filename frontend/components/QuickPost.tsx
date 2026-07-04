"use client";

import { useState, useEffect } from "react";
import { ProjectSelector, PROJECT_COLORS } from "@/components/ProjectSelector";
import { PlatformGrid } from "@/components/PlatformGrid";
import { PlatformChip } from "@/components/ui/PlatformChip";
import { generateContent, postNow } from "@/lib/api";
import type { ContentType, Platform, Content } from "@/lib/types";
import { Check, Send, Type, Image as ImageIcon, Video, Film, ArrowRight, RotateCcw, Sparkles } from "lucide-react";

type Step = "compose" | "preview" | "done";

const TYPES: { key: ContentType; label: string; icon: typeof Type }[] = [
  { key: "text",  label: "Text",  icon: Type },
  { key: "image", label: "Image", icon: ImageIcon },
  { key: "video", label: "Video", icon: Video },
  { key: "reel",  label: "Reel",  icon: Film },
];

const STEPS: Step[] = ["compose", "preview", "done"];

// shared style atoms
const mono9: React.CSSProperties = { fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f" };

export function QuickPost() {
  const [step, setStep]           = useState<Step>("compose");
  const [project, setProject]     = useState("dirco");
  const [topic, setTopic]         = useState("");
  const [type, setType]           = useState<ContentType>("text");
  const [platforms, setPlatforms] = useState<Platform[]>(["twitter", "instagram"]);
  const [result, setResult]       = useState<Content | null>(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState("");

  const accent = PROJECT_COLORS[project] || "#0055FF";

  useEffect(() => {
    if (typeof document !== "undefined") document.body.setAttribute("data-project", project);
  }, [project]);

  const generate = async () => {
    if (!topic.trim()) return;
    setLoading(true); setError("");
    try {
      const c = await generateContent({ project_slug: project, content_type: type, topic, platforms, auto_approve: true });
      setResult(c); setStep("preview");
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  };

  const publish = async () => {
    if (!result) return;
    setLoading(true);
    try { await postNow(result.id, platforms); setStep("done"); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  };

  const reset = () => { setStep("compose"); setTopic(""); setResult(null); setError(""); };

  const stepIdx = STEPS.indexOf(step);

  return (
    <div style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.09)", borderRadius: 14, overflow: "hidden", position: "relative" }}>
      {/* hairline */}
      <div style={{ position: "absolute", top: 0, left: 20, right: 20, height: 1, background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.09),transparent)", pointerEvents: "none" }} />

      {/* header */}
      <div style={{ padding: "18px 22px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div>
          <div style={{ ...mono9, marginBottom: 5 }}>Compose</div>
          <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 26, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>QUICK POST</div>
        </div>

        {/* step pips */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {STEPS.map((s, i) => (
            <div key={s} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{
                width: 6, height: 6, borderRadius: "50%",
                background: i <= stepIdx ? accent : "rgba(255,255,255,0.1)",
                boxShadow: i <= stepIdx ? `0 0 7px ${accent}` : "none",
                transform: i === stepIdx ? "scale(1.4)" : "scale(1)",
                transition: "all 0.25s", flexShrink: 0,
              }} />
              <span style={{ ...mono9, color: i <= stepIdx ? "#8a8a98" : "#36363f" }}>{s}</span>
            </div>
          ))}
          {step !== "compose" && (
            <button onClick={reset} style={{ background: "none", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 7, padding: "5px 7px", cursor: "pointer", color: "#56565f", display: "flex", alignItems: "center" }}>
              <RotateCcw size={12} strokeWidth={1.75} />
            </button>
          )}
        </div>
      </div>

      {/* body */}
      <div style={{ padding: 22 }}>

        {/* ── DONE ── */}
        {step === "done" && (
          <div style={{ textAlign: "center", padding: "28px 0" }}>
            <div style={{ position: "relative", display: "inline-block", marginBottom: 20 }}>
              <div style={{ position: "absolute", inset: -14, borderRadius: "50%", background: accent, opacity: 0.25, filter: "blur(16px)" }} />
              <div style={{ position: "relative", width: 52, height: 52, borderRadius: "50%", background: accent, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 0 28px ${accent}88` }}>
                <Check size={22} strokeWidth={2.5} color="#fff" />
              </div>
            </div>
            <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 72, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em", textShadow: `0 0 48px ${accent}44`, marginBottom: 10 }}>LIVE</div>
            <div style={{ ...mono9, marginBottom: 22 }}>broadcast → <span style={{ color: "#8a8a98" }}>{platforms.join(" · ")}</span></div>
            <button onClick={reset} style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 9, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.09)", color: "#c8c8d2", fontSize: 13, cursor: "pointer" }}>
              <Sparkles size={13} /> Compose Another
            </button>
          </div>
        )}

        {/* ── PREVIEW ── */}
        {step === "preview" && result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ ...mono9 }}>Preview</div>
            <div style={{ borderRadius: 11, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.02)", padding: 18, boxShadow: `inset 3px 0 0 0 ${accent}` }}>
              {result.title && <div style={{ fontSize: 14, fontWeight: 600, color: "#f5f5f7", marginBottom: 7, letterSpacing: "-0.01em" }}>{result.title}</div>}
              <div style={{ fontSize: 14, color: "#c8c8d2", lineHeight: 1.65, fontFamily: "var(--font-serif), Georgia, serif" }}>{result.body}</div>
              <div style={{ marginTop: 14, paddingTop: 11, borderTop: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" as const }}>
                <span style={mono9}>To</span>
                {platforms.map(p => (
                  <PlatformChip key={p} platform={p} size="sm" />
                ))}
              </div>
            </div>
            {error && <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 11, color: "#FF3B47", padding: "9px 13px", borderRadius: 8, background: "rgba(255,59,71,0.07)", border: "1px solid rgba(255,59,71,0.22)" }}>{error}</div>}
            <div style={{ display: "flex", gap: 9 }}>
              <button onClick={publish} disabled={loading} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "13px 18px", borderRadius: 10, background: accent, border: `1px solid ${accent}`, color: "#fff", fontSize: 13, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.5 : 1, minHeight: 48 }}>
                {loading ? <><Spin />Posting</> : <><Send size={13} />Post Now<ArrowRight size={13} style={{ opacity: 0.7 }} /></>}
              </button>
              <button onClick={reset} style={{ padding: "13px 18px", borderRadius: 10, background: "transparent", border: "1px solid rgba(255,255,255,0.09)", color: "#8a8a98", fontSize: 13, cursor: "pointer", minHeight: 48 }}>Discard</button>
            </div>
          </div>
        )}

        {/* ── COMPOSE ── */}
        {step === "compose" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>

            <div>
              <div style={{ ...mono9, marginBottom: 8 }}>Project</div>
              <ProjectSelector value={project} onChange={setProject} />
            </div>

            <div>
              <div style={{ ...mono9, marginBottom: 8 }}>Type</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 7 }}>
                {TYPES.map(({ key, label, icon: Icon }) => {
                  const on = type === key;
                  return (
                    <button key={key} onClick={() => setType(key)} style={{
                      display: "flex", flexDirection: "column", alignItems: "center", gap: 5,
                      padding: "10px 6px", borderRadius: 10, minHeight: 54,
                      background: on ? `${accent}18` : "rgba(255,255,255,0.02)",
                      border: `1px solid ${on ? `${accent}55` : "rgba(255,255,255,0.07)"}`,
                      color: on ? "#f5f5f7" : "#56565f", fontSize: 11, cursor: "pointer", transition: "all 0.15s",
                    }}>
                      <Icon size={13} style={{ color: on ? accent : undefined }} strokeWidth={1.75} />
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <div style={mono9}>Story</div>
                <div style={mono9}>⌘↵ launch</div>
              </div>
              <textarea
                value={topic}
                onChange={e => setTopic(e.target.value)}
                placeholder="What story are you about to tell?"
                rows={3}
                onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) generate(); }}
                style={{
                  width: "100%", boxSizing: "border-box",
                  background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.09)",
                  borderRadius: 10, padding: "11px 14px", color: "#f5f5f7", fontSize: 14, lineHeight: 1.6,
                  resize: "none", outline: "none", fontFamily: "var(--font-serif), Georgia, serif",
                  transition: "border-color 0.15s",
                }}
                onFocus={e => { e.target.style.borderColor = `${accent}66`; }}
                onBlur={e => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
              />
            </div>

            <div>
              <div style={{ ...mono9, marginBottom: 8 }}>Distribution</div>
              <PlatformGrid value={platforms} onChange={setPlatforms} />
            </div>

            {error && <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 11, color: "#FF3B47", padding: "9px 13px", borderRadius: 8, background: "rgba(255,59,71,0.07)", border: "1px solid rgba(255,59,71,0.22)" }}>{error}</div>}

            <button
              onClick={generate}
              disabled={!topic.trim() || loading}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                width: "100%", padding: "14px 20px", borderRadius: 10, minHeight: 50,
                background: accent, border: `1px solid ${accent}`,
                boxShadow: `inset 0 1px 0 rgba(255,255,255,0.16), 0 0 0 1px ${accent}44`,
                color: "#fff", fontSize: 13, fontWeight: 600, cursor: (!topic.trim() || loading) ? "not-allowed" : "pointer",
                opacity: (!topic.trim() || loading) ? 0.45 : 1, transition: "opacity 0.2s",
              }}
            >
              {loading
                ? <><Spin />Generating</>
                : <><Sparkles size={14} /><span style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 14, letterSpacing: "0.04em" }}>GENERATE</span><ArrowRight size={14} style={{ opacity: 0.7 }} /></>
              }
            </button>
          </div>
        )}
      </div>

      <style>{`@keyframes _spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

function Spin() {
  return <span style={{ width: 13, height: 13, border: "1.5px solid rgba(255,255,255,0.5)", borderTopColor: "transparent", borderRadius: "50%", animation: "_spin 0.65s linear infinite", flexShrink: 0 }} />;
}
