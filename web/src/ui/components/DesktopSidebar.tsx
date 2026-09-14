import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../architecture/hostView";

export function DesktopSidebar() {
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
        <p className="nav-label">Workspace</p>
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
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="nav-group">
        <p className="nav-label">Intelligence & Analysis</p>
        <nav className="nav-list">
          {intelligenceNav.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="nav-group">
        <p className="nav-label">Risk & Platform</p>
        <nav className="nav-list">
          {systemNav.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="nav-group">
        <p className="nav-label">Academy & Config</p>
        <nav className="nav-list">
          {configNav.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="sidebar-note">
        <strong>Project 2 Host Architecture</strong>
        <p>
          presents Project 1 outputs. Strategy, AI, signals & execution remain strictly in Project 1.
        </p>
      </div>
    </aside>
  );
}
