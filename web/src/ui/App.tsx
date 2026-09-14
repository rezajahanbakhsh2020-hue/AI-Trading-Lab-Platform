import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import { HostPage } from "./HostPage";
import { TopBar } from "./components/TopBar";
import { DesktopSidebar } from "./components/DesktopSidebar";
import { MobileBottomNav } from "./components/MobileBottomNav";
import {
  NAV_ITEMS,
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
} from "../architecture/hostView";

export function App() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const snapshot = isConnected
    ? createHostSnapshotFromProject1(SAMPLE_CONNECTED_PORT, SAMPLE_REAL_PROJECT1_SIGNAL)
    : createDisconnectedHostSnapshot();

  const handleToggleConnection = () => {
    setIsConnected((prev) => !prev);
  };

  const handleSync = () => {
    // Re-fetch / re-render snapshot from Project1IntegrationPort
    if (isConnected) {
      setIsConnected(false);
      setTimeout(() => setIsConnected(true), 100);
    }
  };

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
              element={
                <HostPage
                  pageId={item.id}
                  snapshot={snapshot}
                  onSync={handleSync}
                  onToggleConnection={handleToggleConnection}
                />
              }
            />
          ))}
          {/* Aliases for singular/plural path compatibility */}
          <Route
            path="/dashboard"
            element={
              <HostPage
                pageId="dashboard"
                snapshot={snapshot}
                onSync={handleSync}
                onToggleConnection={handleToggleConnection}
              />
            }
          />
          <Route
            path="/market"
            element={
              <HostPage
                pageId="markets"
                snapshot={snapshot}
                onSync={handleSync}
                onToggleConnection={handleToggleConnection}
              />
            }
          />
          <Route
            path="/strategy"
            element={
              <HostPage
                pageId="strategies"
                snapshot={snapshot}
                onSync={handleSync}
                onToggleConnection={handleToggleConnection}
              />
            }
          />
          <Route
            path="/learning"
            element={
              <HostPage
                pageId="academy"
                snapshot={snapshot}
                onSync={handleSync}
                onToggleConnection={handleToggleConnection}
              />
            }
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
