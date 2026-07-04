export default function PrivacyPage() {
  const s = {
    page: { minHeight: "100vh", padding: "60px 32px", maxWidth: 800, margin: "0 auto" } as React.CSSProperties,
    eyebrow: { fontFamily: "var(--font-mono), monospace", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase" as const, color: "#36363f", marginBottom: 12 },
    h1: { fontFamily: "var(--font-display), sans-serif", fontSize: 48, lineHeight: 0.9, color: "#f5f5f7", letterSpacing: "0.04em", marginBottom: 40 },
    h2: { fontFamily: "var(--font-display), sans-serif", fontSize: 22, color: "#f5f5f7", letterSpacing: "0.04em", marginBottom: 12, marginTop: 36 },
    p: { fontSize: 14, color: "#8a8a98", lineHeight: 1.8, marginBottom: 16 },
    divider: { height: 1, background: "rgba(255,255,255,0.06)", margin: "40px 0" },
  };

  return (
    <div style={s.page}>
      <div style={s.eyebrow}>Legal</div>
      <div style={s.h1}>PRIVACY POLICY</div>
      <p style={{ ...s.p, color: "#56565f" }}>Last updated: May 2026</p>
      <div style={s.divider} />

      <div style={s.h2}>OVERVIEW</div>
      <p style={s.p}>DirCo Media OS ("the App") is an internal content management and social media distribution platform operated by DirCo. This Privacy Policy explains how we collect, use, and protect information when you use our application.</p>

      <div style={s.h2}>INFORMATION WE COLLECT</div>
      <p style={s.p}>When you authenticate with third-party platforms (TikTok, Instagram, X, Reddit), we receive and store OAuth access tokens necessary to post content on your behalf. We do not collect or store your passwords for any third-party platform.</p>
      <p style={s.p}>We store content you generate within the app, including post text, media files, and scheduling information, solely to facilitate distribution to the platforms you select.</p>

      <div style={s.h2}>HOW WE USE YOUR INFORMATION</div>
      <p style={s.p}>Access tokens are used exclusively to publish content to your connected social media accounts. We do not sell, share, or transfer your data or tokens to any third party. Tokens are stored locally on your server and are never transmitted to external services other than the respective platform APIs.</p>

      <div style={s.h2}>TIKTOK DATA</div>
      <p style={s.p}>When you connect your TikTok account, we access the following scopes: <code style={{ fontFamily: "var(--font-mono), monospace", fontSize: 12, color: "#c8c8d2", background: "rgba(255,255,255,0.06)", padding: "1px 6px", borderRadius: 4 }}>user.info.basic</code> and <code style={{ fontFamily: "var(--font-mono), monospace", fontSize: 12, color: "#c8c8d2", background: "rgba(255,255,255,0.06)", padding: "1px 6px", borderRadius: 4 }}>video.upload</code>. This data is used only to authenticate your account and upload video content you explicitly approve for posting. We do not access your TikTok followers, messages, or any data beyond what is required for video posting.</p>

      <div style={s.h2}>DATA RETENTION</div>
      <p style={s.p}>Access tokens are stored in a local environment configuration file on your own server. You may revoke access at any time by disconnecting the app from your platform's developer settings or by deleting the token from the Settings page.</p>

      <div style={s.h2}>SECURITY</div>
      <p style={s.p}>All data is stored locally on infrastructure you control. We do not operate a cloud backend that stores your credentials. API keys and tokens never leave your server except when making direct API calls to the respective platforms over HTTPS.</p>

      <div style={s.h2}>CONTACT</div>
      <p style={s.p}>For any privacy-related questions, contact the DirCo team through the application or at the address associated with your developer account.</p>

      <div style={s.divider} />
      <p style={{ ...s.p, color: "#36363f" }}>© 2026 DirCo. All rights reserved.</p>
    </div>
  );
}
