import { NavLink } from "react-router-dom";
import {
  PLATFORM_NAME,
  PLATFORM_ROLE,
  PRIMARY_MARKET,
} from "../../architecture/hostView";

type TopBarProps = {
  unreadNotificationsCount?: number;
  onOpenMobileMenu?: () => void;
  onOpenSearch?: () => void;
};

export function TopBar({
  unreadNotificationsCount = 2,
  onOpenMobileMenu,
  onOpenSearch,
}: TopBarProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <button
          className="mobile-menu-btn"
          onClick={onOpenMobileMenu}
          aria-label="Open Navigation Menu"
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
            <h1>{PLATFORM_NAME}</h1>
            <p>{PLATFORM_ROLE}</p>
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
        <span>Search markets, signals, academy...</span>
        <kbd className="search-kbd">⌘K</kbd>
      </div>

      <div className="top-meta">
        <span className="chip">
          <span className="dot ready" />
          Host ready
        </span>
        <span className="chip warn-chip">
          <span className="dot warn" />
          Project 1 disconnected
        </span>
        <span className="chip market-chip">{PRIMARY_MARKET}</span>

        <NavLink
          to="/notifications"
          className="notification-icon-btn"
          aria-label="Notifications"
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
