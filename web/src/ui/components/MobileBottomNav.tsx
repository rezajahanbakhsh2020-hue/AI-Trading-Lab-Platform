import { NavLink, useLocation } from "react-router-dom";
import { NAV_ITEMS } from "../../architecture/hostView";
import { useI18n, type SupportedLanguage } from "../../i18n";

type MobileBottomNavProps = {
  isMenuOpen: boolean;
  onToggleMenu: () => void;
  onCloseMenu: () => void;
};

export function MobileBottomNav({
  isMenuOpen,
  onToggleMenu,
  onCloseMenu,
}: MobileBottomNavProps) {
  const location = useLocation();
  const { t, language, setLanguage, supportedLanguages } = useI18n();

  return (
    <>
      {/* Mobile Drawer / Overlay for full navigation */}
      {isMenuOpen && (
        <div className="mobile-drawer-backdrop" onClick={onCloseMenu}>
          <div
            className="mobile-drawer-content"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mobile-drawer-header">
              <div className="brand">
                <div className="brand-mark">P2</div>
                <div>
                  <h3>{t("topbar.platformTitle")}</h3>
                  <p>{t("topbar.menu")}</p>
                </div>
              </div>
              <button
                className="close-btn"
                onClick={onCloseMenu}
                aria-label={t("topbar.menu")}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
              <div className="lang-selector" style={{ width: "100%", justifyContent: "space-between" }}>
                <span>🌐 {t("settings.selectLanguageLabel")}</span>
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
            </div>

            <div className="mobile-drawer-grid">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.id}
                  to={item.path}
                  end={item.path === "/"}
                  className={({ isActive }) =>
                    isActive
                      ? "mobile-drawer-item active"
                      : "mobile-drawer-item"
                  }
                  onClick={onCloseMenu}
                >
                  <span className="drawer-item-label">{t(`nav.${item.id}`)}</span>
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Mobile Fixed Bottom Dock */}
      <nav className="mobile-bottom-dock" aria-label="Mobile Navigation Dock">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            isActive ? "bottom-dock-tab active" : "bottom-dock-tab"
          }
          onClick={onCloseMenu}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          <span>{t("nav.dashboard")}</span>
        </NavLink>

        <NavLink
          to="/markets"
          className={({ isActive }) =>
            isActive || location.pathname === "/market"
              ? "bottom-dock-tab active"
              : "bottom-dock-tab"
          }
          onClick={onCloseMenu}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          <span>{t("nav.markets")}</span>
        </NavLink>

        <NavLink
          to="/signals"
          className={({ isActive }) =>
            isActive ? "bottom-dock-tab active" : "bottom-dock-tab"
          }
          onClick={onCloseMenu}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
          <span>{t("nav.signals")}</span>
        </NavLink>

        <NavLink
          to="/academy"
          className={({ isActive }) =>
            isActive ? "bottom-dock-tab active" : "bottom-dock-tab"
          }
          onClick={onCloseMenu}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
          <span>{t("nav.academy")}</span>
        </NavLink>

        <button
          className={
            isMenuOpen ? "bottom-dock-tab active" : "bottom-dock-tab"
          }
          onClick={onToggleMenu}
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
            <circle cx="12" cy="12" r="1" />
            <circle cx="12" cy="5" r="1" />
            <circle cx="12" cy="19" r="1" />
          </svg>
          <span>{t("topbar.menu")}</span>
        </button>
      </nav>
    </>
  );
}
