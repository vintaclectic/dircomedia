"use client";

import { useState } from "react";
import { ProjectSelector } from "@/components/ProjectSelector";
import { PlatformGrid } from "@/components/PlatformGrid";
import { generateHypeClip, uploadRecording } from "@/lib/api";
import type { Platform, VideoJobOut } from "@/lib/types";
import { PROJECT_COLORS } from "@/components/ProjectSelector";
import { Video, Upload, Sparkles, CheckCircle, Loader } from "lucide-react";

const mono9: React.CSSProperties = { fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f" };

const STYLES = ["cinematic", "hype", "documentary", "vlog"];

export default function VideoPage() {
  const [project, setProject]       = useState("dirco");
  const [platforms, setPlatforms]   = useState<Platform[]>(["tiktok", "instagram"]);
  const [description, setDescription] = useState("");
  const [duration, setDuration]     = useState(30);
  const [style, setStyle]           = useState("cinematic");
  const [job, setJob]               = useState<VideoJobOut | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");
  const [dragOver, setDragOver]     = useState(false);
  const [uploading, setUploading]   = useState(false);
  const [uploadResult, setUploadResult] = useState<VideoJobOut | null>(null);

  const accent = PROJECT_COLORS[project] || "#0055FF";

  const generateClip = async () => {
    if (!description.trim()) return;
    setLoading(true); setError("");
    try {
      const j = await generateHypeClip({ project_slug: project, description, duration, style, platforms });
      setJob(j);
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    setUploading(true); setError("");
    try {
      const j = await uploadRecording(file, project, platforms);
      setUploadResult(j);
    } catch (e) { setError((e as Error).message); }
    finally { setUploading(false); }
  };

  const btnStyle = (disabled: boolean): React.CSSProperties => ({
    display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
    width: "100%", padding: "13px 20px", borderRadius: 10, minHeight: 48,
    background: accent, border: `1px solid ${accent}`,
    boxShadow: `inset 0 1px 0 rgba(255,255,255,0.15), 0 0 0 1px ${accent}44`,
    color: "#fff", fontSize: 13, fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.45 : 1, transition: "opacity 0.2s",
  });

  return (
    <div style={{ minHeight: "100vh" }}>

      {/* Header */}
      <div style={{
        position: "sticky", top: 0, zIndex: 20,
        background: "rgba(2,2,5,0.88)", backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        padding: "18px 32px",
        display: "flex", alignItems: "flex-end", gap: 16,
      }}>
        <div>
          <div style={{ ...mono9, marginBottom: 5 }}>Pipeline</div>
          <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 40, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>VIDEO</div>
        </div>
      </div>

      <div style={{ padding: "32px 32px", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>

          {/* Upload recording */}
          <div style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, overflow: "hidden" }}>
            <div style={{ padding: "18px 22px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <div style={{ ...mono9, marginBottom: 5 }}>Upload</div>
              <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 22, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>RECORDING</div>
            </div>
            <div style={{ padding: 22, display: "flex", flexDirection: "column", gap: 18 }}>
              <div>
                <div style={{ ...mono9, marginBottom: 8 }}>Project</div>
                <ProjectSelector value={project} onChange={setProject} />
              </div>
              <div>
                <div style={{ ...mono9, marginBottom: 8 }}>Platforms</div>
                <PlatformGrid value={platforms} onChange={setPlatforms} />
              </div>

              {/* Drop zone */}
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                style={{
                  borderRadius: 12,
                  border: `2px dashed ${dragOver ? accent : "rgba(255,255,255,0.12)"}`,
                  background: dragOver ? `${accent}0a` : "rgba(255,255,255,0.015)",
                  padding: "40px 24px",
                  textAlign: "center",
                  transition: "all 0.2s",
                  cursor: "pointer",
                }}
              >
                {uploading ? (
                  <>
                    <Loader size={28} color={accent} style={{ margin: "0 auto 12px", animation: "_spin 0.8s linear infinite" }} />
                    <div style={{ fontSize: 13, color: "#8a8a98" }}>Processing…</div>
                  </>
                ) : uploadResult ? (
                  <>
                    <CheckCircle size={28} color="#00DD88" style={{ margin: "0 auto 12px" }} />
                    <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 22, color: "#00DD88", letterSpacing: "0.04em", marginBottom: 4 }}>UPLOADED</div>
                    <div style={{ ...mono9 }}>Job · {uploadResult.job_id}</div>
                  </>
                ) : (
                  <>
                    <Upload size={28} color="#56565f" style={{ margin: "0 auto 12px" }} />
                    <div style={{ fontSize: 13, color: "#56565f", lineHeight: 1.6 }}>Drop a video file here<br />MP4, MOV, AVI</div>
                  </>
                )}
              </div>
              {error && <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 11, color: "#FF3B47", padding: "9px 13px", borderRadius: 8, background: "rgba(255,59,71,0.07)", border: "1px solid rgba(255,59,71,0.22)" }}>{error}</div>}
            </div>
          </div>

          {/* Hype clip generator */}
          <div style={{ background: "#0b0b14", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, overflow: "hidden" }}>
            <div style={{ padding: "18px 22px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <div style={{ ...mono9, marginBottom: 5 }}>Generate</div>
              <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 22, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em" }}>HYPE CLIP</div>
            </div>
            <div style={{ padding: 22, display: "flex", flexDirection: "column", gap: 18 }}>

              <div>
                <div style={{ ...mono9, marginBottom: 8 }}>Project</div>
                <ProjectSelector value={project} onChange={setProject} />
              </div>

              <div>
                <div style={{ ...mono9, marginBottom: 8 }}>Description</div>
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="What's this clip about?"
                  rows={3}
                  style={{
                    width: "100%", boxSizing: "border-box",
                    background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.09)",
                    borderRadius: 10, padding: "11px 14px", color: "#f5f5f7", fontSize: 14, lineHeight: 1.6,
                    resize: "none", outline: "none", fontFamily: "var(--font-sans), sans-serif",
                  }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <div style={{ ...mono9, marginBottom: 8 }}>Duration (s)</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {[15, 30, 60].map(d => (
                      <button key={d} onClick={() => setDuration(d)} style={{
                        flex: 1, padding: "8px 6px", borderRadius: 8, minHeight: 36,
                        background: duration === d ? `${accent}18` : "rgba(255,255,255,0.02)",
                        border: `1px solid ${duration === d ? `${accent}55` : "rgba(255,255,255,0.07)"}`,
                        color: duration === d ? "#f5f5f7" : "#56565f",
                        fontSize: 12, fontWeight: 500, cursor: "pointer", transition: "all 0.15s",
                      }}>{d}s</button>
                    ))}
                  </div>
                </div>
                <div>
                  <div style={{ ...mono9, marginBottom: 8 }}>Style</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {STYLES.map(s => (
                      <button key={s} onClick={() => setStyle(s)} style={{
                        padding: "8px 10px", borderRadius: 8, minHeight: 36,
                        background: style === s ? `${accent}18` : "rgba(255,255,255,0.02)",
                        border: `1px solid ${style === s ? `${accent}55` : "rgba(255,255,255,0.07)"}`,
                        color: style === s ? "#f5f5f7" : "#56565f",
                        fontSize: 11, cursor: "pointer", transition: "all 0.15s", textTransform: "capitalize",
                      }}>{s}</button>
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <div style={{ ...mono9, marginBottom: 8 }}>Platforms</div>
                <PlatformGrid value={platforms} onChange={setPlatforms} />
              </div>

              {job && (
                <div style={{ background: "rgba(0,221,136,0.06)", border: "1px solid rgba(0,221,136,0.25)", borderRadius: 10, padding: "14px 16px", display: "flex", alignItems: "center", gap: 10 }}>
                  <CheckCircle size={16} color="#00DD88" />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#00DD88", marginBottom: 2 }}>Job queued</div>
                    <div style={{ ...mono9, color: "#56565f" }}>{job.job_id}</div>
                  </div>
                </div>
              )}

              {error && <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 11, color: "#FF3B47", padding: "9px 13px", borderRadius: 8, background: "rgba(255,59,71,0.07)", border: "1px solid rgba(255,59,71,0.22)" }}>{error}</div>}

              <button onClick={generateClip} disabled={!description.trim() || loading} style={btnStyle(!description.trim() || loading)}>
                {loading
                  ? <><span style={{ width: 13, height: 13, border: "1.5px solid rgba(255,255,255,0.5)", borderTopColor: "transparent", borderRadius: "50%", animation: "_spin 0.65s linear infinite", flexShrink: 0 }} />Generating</>
                  : <><Sparkles size={14} /><span style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 14, letterSpacing: "0.04em" }}>GENERATE CLIP</span></>
                }
              </button>
            </div>
          </div>
        </div>
      </div>
      <style>{`@keyframes _spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
