export default function LogoPage() {
  const projects = [
    { name: "DirCo",       color: "#0055FF" },
    { name: "DirHaven RP", color: "#FF2222" },
    { name: "DirHaven App",color: "#00DD88" },
    { name: "DirMegle",    color: "#FF5500" },
    { name: "Medaled",     color: "#FFD700" },
    { name: "Agentis",     color: "#7C3AED" },
    { name: "Vintinuum",   color: "#F0287A" },
  ];

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 40 }}>
      <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "#36363f", marginBottom: 16 }}>
        DirCo Media OS · Identity
      </div>

      {/* Logo — large */}
      <div style={{ position: "relative", marginBottom: 48 }}>
        <div style={{
          position: "absolute", inset: -60,
          background: "radial-gradient(ellipse at center, rgba(0,85,255,0.12), transparent 70%)",
          pointerEvents: "none",
        }} />
        <img src="/dirco-logo.svg" alt="DirCo Media OS" style={{ width: 320, height: 320, position: "relative" }} />
      </div>

      {/* Wordmark */}
      <div style={{ fontFamily: "var(--font-display), sans-serif", fontSize: 52, color: "#f5f5f7", letterSpacing: "0.1em", marginBottom: 6 }}>
        DIRCO MEDIA
      </div>
      <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase", color: "#36363f", marginBottom: 56 }}>
        Automated Content OS
      </div>

      {/* Color legend */}
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", justifyContent: "center" }}>
        {projects.map(p => (
          <div key={p.name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: p.color, boxShadow: `0 0 8px ${p.color}` }} />
            <span style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.16em", textTransform: "uppercase", color: "#56565f" }}>{p.name}</span>
          </div>
        ))}
      </div>

      {/* Size variants */}
      <div style={{ marginTop: 64, display: "flex", alignItems: "center", gap: 32 }}>
        <img src="/dirco-logo.svg" alt="" style={{ width: 80, height: 80 }} />
        <img src="/dirco-logo.svg" alt="" style={{ width: 48, height: 48 }} />
        <img src="/dirco-logo.svg" alt="" style={{ width: 32, height: 32 }} />
        <img src="/dirco-logo.svg" alt="" style={{ width: 20, height: 20 }} />
        <img src="/dirco-logo.svg" alt="" style={{ width: 14, height: 14 }} />
      </div>
      <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "#36363f", marginTop: 12 }}>
        320 · 80 · 48 · 32 · 20 · 14
      </div>
    </div>
  );
}
