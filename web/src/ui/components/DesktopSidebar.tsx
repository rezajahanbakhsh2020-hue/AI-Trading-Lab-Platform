import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../architecture/hostView";
import { useI18n } from "../../i18n";

export function DesktopSidebar() {
  const { t } = useI18n();

  const workspaceNav = NAV_ITEMS.filter((item) =>
    ["dashboard", "markets", "watchlist"].includes(item.id)
  );

  const intelligenceNav = NAV_ITEMS.filter((item) =>
    ["signals", "strategies", "backtest", "performance"].includes(item.id)
  );

  const systemNav = NAV_ITEMS.filter((item) =>
    ["risk", "monitoring", "providers", "notifications"].includes(item.id)
  );

  const configNav = NAV_ITEMS.filter((item) =>
    ["academy", "settings"].includes(item.id)
  );

  return (
    <aside className="sidebar">
      <div className="nav-group">
        <p className="nav-label">{t("nav.workspaceGroup")}</p>
        <nav className="nav-list">
          {workspaceNav.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span>{t(`nav.${item.id}`)}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="nav-group">
        <p className="nav-label">{t("nav.intelligenceGroup")}</p>
        <nav className="nav-list">
          {intelligenceNav.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span>{t(`nav.${item.id}`)}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="nav-group">
        <p className="nav-label">{t("nav.systemGroup")}</p>
        <nav className="nav-list">
          {systemNav.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span>{t(`nav.${item.id}`)}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="nav-group">
        <p className="nav-label">{t("nav.configGroup")}</p>
        <nav className="nav-list">
          {configNav.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span>{t(`nav.${item.id}`)}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="sidebar-note">
        <strong>{t("footer.sidebarNoteTitle")}</strong>
        <p>{t("footer.sidebarNoteBody")}</p>
      </div>
    </aside>
  );
}
