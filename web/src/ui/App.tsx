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
import {
  SAMPLE_BIQUOTE_PROVIDER,
  SAMPLE_BIQUOTE_CANDLES_XAUUSD,
  SAMPLE_BIQUOTE_QUOTE_XAUUSD,
} from "../architecture/marketData";
import {
  loadUserNotifications,
  syncNotificationsFromHostSnapshot,
  countUnreadNotifications,
} from "../architecture/notification";

export function App() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState("XAUUSD");
  const [selectedTimeframe, setSelectedTimeframe] = useState("1h");

  const marketState = isConnected && selectedSymbol === "XAUUSD"
    ? {
        symbol: "XAUUSD",
        timeframe: selectedTimeframe,
        provider: SAMPLE_BIQUOTE_PROVIDER,
        quote: SAMPLE_BIQUOTE_QUOTE_XAUUSD,
        candles: SAMPLE_BIQUOTE_CANDLES_XAUUSD,
        status: "connected" as const,
        message: "Streaming live market data via BiQuoteProvider.",
        lastFetchedAt: new Date().toUTCString(),
      }
    : {
        symbol: selectedSymbol,
        timeframe: selectedTimeframe,
        provider: null,
        quote: null,
        candles: [],
        status: "disconnected" as const,
        message: `Market data provider disconnected for ${selectedSymbol}.`,
        lastFetchedAt: null,
      };

  const snapshot = isConnected
    ? createHostSnapshotFromProject1(
        SAMPLE_CONNECTED_PORT,
        SAMPLE_REAL_PROJECT1_SIGNAL,
        selectedSymbol,
        selectedTimeframe,
        marketState
      )
    : createDisconnectedHostSnapshot(selectedSymbol, selectedTimeframe);

  const userId = snapshot.security?.userId || "guest_user";
  const userNotifs = loadUserNotifications(userId);
  const syncedNotifs = syncNotificationsFromHostSnapshot(userId, snapshot, userNotifs);
  const unreadCount = countUnreadNotifications(syncedNotifs);

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

  const handleSelectSymbol = (symbol: string) => {
    setSelectedSymbol(symbol);
  };

  const handleSelectTimeframe = (tf: string) => {
    setSelectedTimeframe(tf);
  };

  return (
    <div className="app-shell">
      <TopBar
        unreadNotificationsCount={unreadCount}
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
                  onSelectSymbol={handleSelectSymbol}
                  onSelectTimeframe={handleSelectTimeframe}
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
                onSelectSymbol={handleSelectSymbol}
                onSelectTimeframe={handleSelectTimeframe}
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
                onSelectSymbol={handleSelectSymbol}
                onSelectTimeframe={handleSelectTimeframe}
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
                onSelectSymbol={handleSelectSymbol}
                onSelectTimeframe={handleSelectTimeframe}
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
                onSelectSymbol={handleSelectSymbol}
                onSelectTimeframe={handleSelectTimeframe}
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
