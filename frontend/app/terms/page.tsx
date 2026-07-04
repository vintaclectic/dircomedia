export default function TermsPage() {
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
      <div style={s.h1}>TERMS OF SERVICE</div>
      <p style={{ ...s.p, color: "#56565f" }}>Last updated: May 2026</p>
      <div style={s.divider} />

      <div style={s.h2}>ACCEPTANCE</div>
      <p style={s.p}>By using DirCo Media OS ("the App"), you agree to these Terms of Service. The App is an internal tool operated by DirCo for managing and distributing content across social media platforms.</p>

      <div style={s.h2}>USE OF THE APP</div>
      <p style={s.p}>The App is intended for use by DirCo team members to create, manage, and publish content to social media platforms including TikTok, Instagram, X (Twitter), and Reddit. You agree to use the App only for lawful purposes and in accordance with each platform's own terms of service.</p>

      <div style={s.h2}>THIRD-PARTY PLATFORMS</div>
      <p style={s.p}>The App integrates with third-party platforms via their official APIs. Your use of those integrations is subject to the respective platform's terms of service. DirCo is not responsible for changes to third-party APIs or platform policies that affect the App's functionality.</p>

      <div style={s.h2}>CONTENT</div>
      <p style={s.p}>You are solely responsible for all content you generate, approve, and publish through the App. You agree not to publish content that violates any platform's community guidelines, infringes intellectual property rights, or violates any applicable law.</p>

      <div style={s.h2}>TIKTOK INTEGRATION</div>
      <p style={s.p}>When using the TikTok integration, you authorize the App to upload and publish video content to your TikTok account using the permissions you grant during the OAuth authentication flow. You may revoke this authorization at any time through TikTok's connected apps settings.</p>

      <div style={s.h2}>INTELLECTUAL PROPERTY</div>
      <p style={s.p}>All content generated through the App's AI features remains your property. The App and its underlying code are proprietary to DirCo.</p>

      <div style={s.h2}>LIMITATION OF LIABILITY</div>
      <p style={s.p}>The App is provided as-is. DirCo is not liable for any damages arising from your use of the App, including failed posts, API downtime, or content that violates third-party platform policies.</p>

      <div style={s.h2}>CHANGES</div>
      <p style={s.p}>These terms may be updated at any time. Continued use of the App constitutes acceptance of the updated terms.</p>

      <div style={s.h2}>CONTACT</div>
      <p style={s.p}>For questions about these terms, contact the DirCo team through the application.</p>

      <div style={s.divider} />
      <p style={{ ...s.p, color: "#36363f" }}>© 2026 DirCo. All rights reserved.</p>
    </div>
  );
}
