import { useState } from "react";
import { useI18n } from "../../i18n";

export function HelpCenter() {
  const { t } = useI18n();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSection, setSelectedSection] = useState<string>("get_started");

  const helpTopics = [
    {
      id: "get_started",
      title: t("help.getStartedTitle") !== "help.getStartedTitle" ? t("help.getStartedTitle") : "Getting Started & Onboarding",
      summary: t("help.getStartedSub") !== "help.getStartedSub" ? t("help.getStartedSub") : "Quick operational start for presenting Project 1 outputs inside Project 2.",
      content: (
        <div>
          <h4>Host Architecture & Strategy Boundaries</h4>
          <p>Project 2 is the presentation, application, and integration host for Project 1 (AI-Trading-Lab). Strategy calculations, signal evaluations, and risk models run exclusively in Project 1.</p>
          <h4>Primary Navigation Workflow</h4>
          <ul>
            <li><strong>Dashboard:</strong> Central operational home summarizing signal status and system health.</li>
            <li><strong>Markets & Watchlist:</strong> Real-time streaming quotes and custom user watchlists.</li>
            <li><strong>Signals & Intents:</strong> Validated signals and pre-execution staged order intents.</li>
            <li><strong>Risk & Performance:</strong> Trade geometry breakdown, R:R calculator, and walk-forward analytics.</li>
            <li><strong>Health & Control:</strong> Provider readiness, audit log tracking, and security gate management.</li>
          </ul>
        </div>
      ),
    },
    {
      id: "auth_security",
      title: t("help.subsystemsTitle") !== "help.subsystemsTitle" ? t("help.subsystemsTitle") : "Authentication & Platform Subsystems",
      summary: "User access control, permanent owner immunity, and session lifetime bounds.",
      content: (
        <div>
          <h4>Account Roles & Expiration Rules</h4>
          <p>The platform enforces server-side identity validation on every protected route:</p>
          <ul>
            <li><strong>Permanent Owner/Admin:</strong> Protected from expiry rules and account deactivation.</li>
            <li><strong>Active Customer:</strong> Time-limited access with strict activation/expiration bounds.</li>
            <li><strong>Expired / Inactive Account:</strong> Fails closed on authentication and API calls.</li>
          </ul>
          <h4>Password Recovery Flow</h4>
          <p>If you forget your password, click 'Forgot password / Recovery' in the login modal. A secure, non-reversible recovery token contract will be generated.</p>
        </div>
      ),
    },
    {
      id: "status_indicators",
      title: t("help.statusesTitle") !== "help.statusesTitle" ? t("help.statusesTitle") : "Status Badges & Security Indicators",
      summary: "Guide to system status icons, execution boundaries, and freshness badges.",
      content: (
        <div>
          <h4>Status Badges Reference</h4>
          <ul>
            <li><span style={{ color: "#4ade80", fontWeight: 700 }}>ACTIVE / READY:</span> System or account is healthy and fully authorized.</li>
            <li><span style={{ color: "#facc15", fontWeight: 700 }}>PENDING / STAGED:</span> Pre-execution intention staged inside Project 2.</li>
            <li><span style={{ color: "#fca5a5", fontWeight: 700 }}>EXPIRED / DEGRADED:</span> Access bounds exceeded or provider connection down.</li>
            <li><span style={{ color: "#c084fc", fontWeight: 700 }}>PERMANENT ADMIN:</span> Immune owner account.</li>
          </ul>
          <h4>Non-Execution Disclosure</h4>
          <p>Order intents in Project 2 represent pre-authorized staged intentions. They are NOT live market fills, broker orders, or exchange submissions.</p>
        </div>
      ),
    },
    {
      id: "troubleshooting",
      title: t("help.troubleshootingTitle") !== "help.troubleshootingTitle" ? t("help.troubleshootingTitle") : "Troubleshooting & Health Diagnostics",
      summary: "What to do if market data or Project 1 integration is unavailable.",
      content: (
        <div>
          <h4>Common Issues & Action Steps</h4>
          <ol>
            <li>
              <strong>Market Data Disconnected:</strong> Visit the Health Center (/health) to view provider freshness age or switch to the disconnected fallback adapter.
            </li>
            <li>
              <strong>Permission Restricted:</strong> If strategy secrets or calibration parameters appear masked, confirm your account role with the system administrator.
            </li>
            <li>
              <strong>Session Expired:</strong> Sessions expire automatically after 24 hours. Simply click Sign In in the top bar to refresh your token.
            </li>
          </ol>
        </div>
      ),
    },
  ];

  const filteredTopics = helpTopics.filter(
    (tItem) =>
      tItem.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tItem.summary.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeTopic = helpTopics.find((tItem) => tItem.id === selectedSection) || helpTopics[0];

  return (
    <div style={{ padding: "1.5rem", color: "#f8fafc" }}>
      <div style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>
          📖 {t("help.title")}
        </h2>
        <p style={{ color: "#94a3b8", fontSize: "0.875rem", marginTop: "0.25rem" }}>
          {t("help.subtitle")}
        </p>
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <input
          type="text"
          className="search-input"
          style={{ width: "100%", minHeight: "44px", padding: "0.5rem 1rem", fontSize: "0.875rem" }}
          placeholder={t("help.searchPlaceholder")}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.5rem" }}>
        {/* Navigation Sidebar */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {filteredTopics.map((topic) => (
            <button
              key={topic.id}
              onClick={() => setSelectedSection(topic.id)}
              className="btn btn-secondary"
              style={{
                textAlign: "left",
                minHeight: "48px",
                padding: "0.75rem 1rem",
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                borderColor: selectedSection === topic.id ? "#3b82f6" : "#334155",
                backgroundColor: selectedSection === topic.id ? "rgba(59, 130, 246, 0.15)" : undefined,
              }}
            >
              <span style={{ fontWeight: 600, fontSize: "0.875rem", color: "#f8fafc" }}>
                {topic.title}
              </span>
              <span style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.25rem" }}>
                {topic.summary}
              </span>
            </button>
          ))}
        </div>

        {/* Content Viewer Panel */}
        <div
          style={{
            padding: "1.5rem",
            borderRadius: "8px",
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            fontSize: "0.875rem",
            lineHeight: 1.6,
          }}
        >
          <h3 style={{ marginTop: 0, color: "#60a5fa", fontSize: "1.25rem" }}>
            {activeTopic.title}
          </h3>
          <p style={{ color: "#94a3b8", fontStyle: "italic", marginBottom: "1rem" }}>
            {activeTopic.summary}
          </p>
          <hr style={{ borderColor: "#334155", marginBottom: "1rem" }} />
          {activeTopic.content}
        </div>
      </div>
    </div>
  );
}
