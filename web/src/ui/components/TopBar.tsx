import { NavLink } from "react-router-dom";
import { PRIMARY_MARKET } from "../../architecture/hostView";
import { useI18n, type SupportedLanguage } from "../../i18n";
import { type UserAccount } from "../../architecture/userAuth";

type TopBarProps = {
  unreadNotificationsCount?: number;
  onOpenMobileMenu?: () => void;
  onOpenSearch?: () => void;
  onOpenLogin?: () => void;
  onLogout?: () => void;
  currentAccount?: UserAccount | null;
};

export function TopBar({
  unreadNotificationsCount = 2,
  onOpenMobileMenu,
  onOpenSearch,
  onOpenLogin,
  onLogout,
  currentAccount,
}: TopBarProps) {
  const { t, language, setLanguage, supportedLanguages } = useI18n();

  return (
    <header className="topbar">
      <div className="brand">
        <button
          className="mobile-menu-btn"
          onClick={onOpenMobileMenu}
          aria-label={t("topbar.menu")}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <NavLink to="/" className="brand-link">
          <div className="brand-mark">P2</div>
          <div className="brand-text">
            <h1>{t("topbar.platformTitle")}</h1>
            <p>{t("topbar.platformRole")}</p>
          </div>
        </NavLink>
      </div>

      <div className="top-search-trigger" onClick={onOpenSearch}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <span>{t("topbar.searchPlaceholder")}</span>
        <kbd className="search-kbd">⌘K</kbd>
      </div>

      <div className="top-meta">
        <div className="lang-selector">
          <span>🌐</span>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as SupportedLanguage)}
            aria-label={t("buttons.selectLanguage")}
          >
            {supportedLanguages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.flag} {l.nativeName}
              </option>
            ))}
          </select>
        </div>

        <span className="chip">
          <span className="dot ready" />
          {t("topbar.hostReady")}
        </span>
        <span className="chip market-chip">{PRIMARY_MARKET}</span>

        {currentAccount ? (
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontSize: "0.8125rem", color: "#f8fafc", fontWeight: 600 }}>
              👤 {currentAccount.userId} {currentAccount.isPermanentAdmin && "👑"}
            </span>
            <button
              onClick={onLogout}
              className="btn btn-secondary"
              style={{ minHeight: "36px", padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
              aria-label={t("auth.logoutButton")}
            >
              {t("auth.logoutButton")}
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenLogin}
            className="btn btn-secondary"
            style={{ minHeight: "36px", padding: "0.25rem 0.75rem", fontSize: "0.8125rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.375rem" }}
            aria-label={t("auth.loginButton")}
          >
            <span>👤</span>
            <span>Guest</span>
          </button>
        )}

        <NavLink
          to="/help"
          className="notification-icon-btn"
          aria-label={t("nav.help")}
          title={t("nav.help")}
          style={{ textDecoration: "none", fontSize: "1rem" }}
        >
          📖
        </NavLink>

        <NavLink
          to="/notifications"
          className="notification-icon-btn"
          aria-label={t("nav.notifications")}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          {unreadNotificationsCount > 0 && (
            <span className="notification-badge">{unreadNotificationsCount}</span>
          )}
        </NavLink>
      </div>
    </header>
  );
}
