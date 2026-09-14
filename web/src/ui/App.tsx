import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import { HostPage } from "./HostPage";
import { TopBar } from "./components/TopBar";
import { DesktopSidebar } from "./components/DesktopSidebar";
import { MobileBottomNav } from "./components/MobileBottomNav";
import {
  NAV_ITEMS,
  createDisconnectedHostSnapshot,
} from "../architecture/hostView";

const snapshot = createDisconnectedHostSnapshot();

export function App() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <div className="app-shell">
      <TopBar
        unreadNotificationsCount={2}
        onOpenMobileMenu={() => setIsMobileMenuOpen(true)}
      />

      <DesktopSidebar />

      <main className="workspace">
        <Routes>
          {NAV_ITEMS.map((item) => (
            <Route
              key={item.id}
              path={item.path}
              element={<HostPage pageId={item.id} snapshot={snapshot} />}
            />
          ))}
          {/* Aliases for singular/plural path compatibility */}
          <Route
            path="/dashboard"
            element={<HostPage pageId="dashboard" snapshot={snapshot} />}
          />
          <Route
            path="/market"
            element={<HostPage pageId="markets" snapshot={snapshot} />}
          />
          <Route
            path="/strategy"
            element={<HostPage pageId="strategies" snapshot={snapshot} />}
          />
          <Route
            path="/learning"
            element={<HostPage pageId="academy" snapshot={snapshot} />}
          />
        </Routes>
      </main>

      <MobileBottomNav
        isMenuOpen={isMobileMenuOpen}
        onToggleMenu={() => setIsMobileMenuOpen((prev) => !prev)}
        onCloseMenu={() => setIsMobileMenuOpen(false)}
      />
    </div>
  );
}
