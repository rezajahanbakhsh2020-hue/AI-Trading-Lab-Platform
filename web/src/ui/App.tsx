import { NavLink, Route, Routes } from "react-router-dom";
import { HostPage } from "./HostPage";
import {
  NAV_ITEMS,
  PLATFORM_NAME,
  PLATFORM_ROLE,
  PRIMARY_MARKET,
  createDisconnectedHostSnapshot,
} from "../architecture/hostView";

const snapshot = createDisconnectedHostSnapshot();

export function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">P2</div>
          <div>
            <h1>{PLATFORM_NAME}</h1>
            <p>{PLATFORM_ROLE}</p>
          </div>
        </div>
        <div className="top-meta">
          <span className="chip">
            <span className="dot ready" />
            Host ready
          </span>
          <span className="chip">
            <span className="dot warn" />
            Project 1 disconnected
          </span>
          <span className="chip">{PRIMARY_MARKET}</span>
        </div>
      </header>
      <aside className="sidebar">
        <div>
          <p className="nav-label">Workspace</p>
          <nav className="nav-list">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) =>
                  isActive ? "nav-link active" : "nav-link"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="sidebar-note">
          Project 2 hosts and presents Project 1. It does not generate signals,
          run strategies, or execute orders.
        </div>
      </aside>
      <main className="workspace">
        <Routes>
          {NAV_ITEMS.map((item) => (
            <Route
              key={item.id}
              path={item.path}
              element={<HostPage pageId={item.id} snapshot={snapshot} />}
            />
          ))}
        </Routes>
      </main>
    </div>
  );
}
