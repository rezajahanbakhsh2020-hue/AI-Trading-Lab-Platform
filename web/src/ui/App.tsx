import { useState, useEffect } from "react";
import { Route, Routes, useNavigate } from "react-router-dom";
import { HostPage } from "./HostPage";
import { TopBar } from "./components/TopBar";
import { DesktopSidebar } from "./components/DesktopSidebar";
import { MobileBottomNav } from "./components/MobileBottomNav";
import { CommandPalette } from "./components/CommandPalette";
import { LoginModal } from "./components/LoginModal";
import { UserManagementCenter } from "./components/UserManagementCenter";
import { HelpCenter } from "./components/HelpCenter";
import { BoundedPageContainer } from "./components/BoundedPageContainer";
import {
  NAV_ITEMS,
  PROJECT1_GATEWAY_PORT,
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
  fetchHostSnapshot,
  type HostSnapshot,
} from "../architecture/hostView";
import {
  SAMPLE_BIQUOTE_PROVIDER,
  fetchMarketCandles,
  fetchMarketQuote,
  normalizeQuote,
  type Candle,
  type Quote,
} from "../architecture/marketData";
import {
  requestExecutionApi,
  updateOrderIntentStateApi,
} from "../architecture/executionGateway";
import type { OrderIntentPayload, OrderLifecycleState } from "../architecture/orderIntent";
import {
  loadUserNotifications,
  syncNotificationsFromHostSnapshot,
  countUnreadNotifications,
} from "../architecture/notification";
import {
  getStoredAuthState,
  saveSession,
  clearSession,
  StoredAuthState,
  AuthSession,
} from "../architecture/userAuth";

export function App() {
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [authState, setAuthState] = useState<StoredAuthState>(getStoredAuthState);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState("XAUUSD");
  const [selectedTimeframe, setSelectedTimeframe] = useState("1h");
  const [stagedIntents, setStagedIntents] = useState<OrderIntentPayload[]>([]);
  const [backendSnapshot, setBackendSnapshot] = useState<HostSnapshot | null>(null);

  useEffect(() => {
    if (!isConnected) {
      setBackendSnapshot(null);
      return;
    }

    let isMounted = true;
    async function syncBackendHostSnapshot() {
      const token = authState.sessionToken;
      const res = await fetchHostSnapshot(token, selectedSymbol, selectedTimeframe);
      if (!isMounted) return;

      if (res.success && res.snapshot) {
        setBackendSnapshot(res.snapshot);
      } else {
        setBackendSnapshot(null);
      }
    }

    syncBackendHostSnapshot();
    return () => {
      isMounted = false;
    };
  }, [isConnected, selectedSymbol, selectedTimeframe, authState.sessionToken]);

  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  const [liveCandles, setLiveCandles] = useState<Candle[]>([]);
  const [liveQuote, setLiveQuote] = useState<Quote | null>(null);

  useEffect(() => {
    // When disconnected or provider is not active, set candles to empty array and quote to null.
    // Zero sample or synthetic fallbacks are used in production runtime.
    if (!isConnected) {
      setLiveCandles([]);
      setLiveQuote(null);
      return;
    }

    // Immediately invalidate/clear candles and quote upon timeframe or symbol selection change
    setLiveCandles([]);
    setLiveQuote(null);

    let isMounted = true;
    const reqSymbol = selectedSymbol;
    const reqTimeframe = selectedTimeframe;

    async function loadMarketData() {
      const token = authState.sessionToken;
      const [candlesRes, quoteRes] = await Promise.all([
        fetchMarketCandles(token, reqSymbol, reqTimeframe, "biquote"),
        fetchMarketQuote(token, reqSymbol, "biquote"),
      ]);

      // Protect against out-of-order stale async responses
      if (isMounted) {
        if (candlesRes.success && candlesRes.candles && candlesRes.candles.length > 0) {
          setLiveCandles(candlesRes.candles);
        } else {
          setLiveCandles([]);
        }
        if (quoteRes.success && quoteRes.quote && quoteRes.quote.symbol === reqSymbol) {
          setLiveQuote(quoteRes.quote);
        } else {
          setLiveQuote(null);
        }
      }
    }

    loadMarketData();
    return () => {
      isMounted = false;
    };
  }, [isConnected, selectedSymbol, selectedTimeframe, authState.sessionToken]);

  const rawQuoteForSymbol = (liveQuote && liveQuote.symbol === selectedSymbol) ? liveQuote : null;
  const normalizedLiveQuote = normalizeQuote(rawQuoteForSymbol);

  const marketCandles = liveCandles;
  const isMarketConnected = marketCandles.length > 0 || normalizedLiveQuote != null;
  const marketStatus = isMarketConnected ? "connected" as const : "disconnected" as const;

  const marketState = {
    symbol: selectedSymbol,
    timeframe: selectedTimeframe,
    provider: isMarketConnected ? SAMPLE_BIQUOTE_PROVIDER : null,
    quote: normalizedLiveQuote,
    candles: marketCandles,
    status: marketStatus,
    message: isMarketConnected
      ? `Streaming live market data for ${selectedSymbol} via BiQuoteProvider.`
      : `Market data provider disconnected for ${selectedSymbol}.`,
    lastFetchedAt: isMarketConnected ? new Date().toUTCString() : null,
  };

  const baseSnapshot = isConnected
    ? (backendSnapshot || createHostSnapshotFromProject1(
        PROJECT1_GATEWAY_PORT,
        null,
        selectedSymbol,
        selectedTimeframe,
        marketState
      ))
    : createDisconnectedHostSnapshot(selectedSymbol, selectedTimeframe);

  const snapshot = {
    ...baseSnapshot,
    orderIntents: stagedIntents.length > 0
      ? [
          ...stagedIntents,
          ...(baseSnapshot.orderIntents || []).filter(
            (b) => !stagedIntents.some((s) => s.order_intent_id === b.order_intent_id)
          ),
        ]
      : baseSnapshot.orderIntents,
  };

  // Apply authenticated security state override if user is logged in
  if (authState.isLoggedIn && authState.userAccount) {
    snapshot.security = {
      userId: authState.userAccount.userId,
      role: authState.userAccount.role,
      isAdmin: authState.userAccount.role === "admin" || authState.userAccount.isPermanentAdmin,
      permissions: authState.userAccount.permissions || ["read:signals"],
      status: authState.userAccount.isPermanentAdmin ? "permanent_admin" : "active",
      message: authState.userAccount.isPermanentAdmin
        ? "Protected Owner/Admin authentication active."
        : `Authenticated session active for ${authState.userAccount.userId}`,
    };
  }

  const userId = snapshot.security?.userId || "guest_user";
  const userNotifs = loadUserNotifications(userId);
  const syncedNotifs = syncNotificationsFromHostSnapshot(userId, snapshot, userNotifs);
  const unreadCount = countUnreadNotifications(syncedNotifs);

  const handleToggleConnection = () => {
    setIsConnected((prev) => !prev);
  };

  const handleSync = () => {
    if (isConnected) {
      setIsConnected(false);
      setTimeout(() => setIsConnected(true), 100);
    }
  };

  const handleSelectSymbol = (symbol: string) => {
    setSelectedSymbol(symbol);
  };

  const handleStageOrderIntent = () => {
    const sig = snapshot.signal;
    const isBuy = (sig.action || "BUY").toUpperCase() === "BUY";
    const intentId = `ord_intent_${sig.signalId || "staged_" + Date.now()}`;
    const newIntent: OrderIntentPayload = {
      order_intent_id: intentId,
      authorization_id: `auth_${Date.now()}_${sig.strategyName || "Project1"}`,
      user_id: snapshot.security?.userId || "guest_user",
      symbol: selectedSymbol,
      direction: isBuy ? "buy" : "sell",
      order_type: "market",
      requested_price: snapshot.risk.entry ?? null,
      requested_quantity: 1.0,
      stop_loss: snapshot.risk.stopLoss ?? null,
      take_profit_1: snapshot.risk.takeProfits[0] ?? null,
      take_profit_2: snapshot.risk.takeProfits[1] ?? null,
      take_profit_3: snapshot.risk.takeProfits[2] ?? null,
      time_in_force: "GTC",
      idempotency_key: `idemp_${selectedSymbol.toLowerCase()}_${Date.now()}`,
      creation_timestamp: Math.floor(Date.now() / 1000),
      lifecycle_state: "STAGED",
      is_staged: true,
      is_terminal: false,
    };

    setStagedIntents((prev) => {
      const exists = prev.some((i) => i.order_intent_id === newIntent.order_intent_id);
      if (exists) return prev;
      return [newIntent, ...prev];
    });

    navigate("/intents");
  };

  const handleTransitionIntent = async (
    intentId: string,
    targetState: OrderLifecycleState,
    reason?: string
  ) => {
    const token = authState.sessionToken;
    if (token) {
      await updateOrderIntentStateApi(intentId, targetState, reason, token);
    }
    setStagedIntents((prev) =>
      prev.map((i) =>
        i.order_intent_id === intentId
          ? {
              ...i,
              lifecycle_state: targetState,
              is_staged: false,
              is_terminal: true,
              rejection_reason: reason || i.rejection_reason,
            }
          : i
      )
    );
  };

  const handleRequestExecution = async (intentId: string) => {
    const token = authState.sessionToken;
    const res = await requestExecutionApi(intentId, token);
    if (res && res.attempt) {
      setStagedIntents((prev) =>
        prev.map((i) => {
          if (i.order_intent_id === intentId) {
            const attempts = i.execution_attempts ? [...i.execution_attempts] : [];
            attempts.unshift(res.attempt!);
            return {
              ...i,
              execution_attempts: attempts,
            };
          }
          return i;
        })
      );
    }
  };

  const handleSelectTimeframe = (tf: string) => {
    setSelectedTimeframe(tf);
  };

  const handleLoginSuccess = (session: AuthSession) => {
    saveSession(session);
    setAuthState({
      isLoggedIn: true,
      sessionToken: session.token,
      userAccount: session.user,
    });
  };

  const handleLogout = () => {
    const token = authState.sessionToken;
    clearSession();
    setAuthState({
      isLoggedIn: false,
      sessionToken: null,
      userAccount: null,
    });
    if (token) {
      fetch("/api/v1/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {
        // Ignore unhandled logout network error since client session is invalidated
      });
    }
  };

  return (
    <div className="app-shell">
      <TopBar
        unreadNotificationsCount={unreadCount}
        onOpenMobileMenu={() => setIsMobileMenuOpen(true)}
        onOpenSearch={() => setIsCommandPaletteOpen(true)}
        onOpenLogin={() => setIsLoginModalOpen(true)}
        onLogout={handleLogout}
        currentAccount={authState.userAccount}
      />

      <DesktopSidebar />

      <main className="workspace">
        <Routes>
          <Route
            path="/users"
            element={
              <BoundedPageContainer>
                <UserManagementCenter currentAccount={authState.userAccount} />
              </BoundedPageContainer>
            }
          />
          <Route
            path="/help"
            element={
              <BoundedPageContainer>
                <HelpCenter />
              </BoundedPageContainer>
            }
          />
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
                  onStageOrderIntent={handleStageOrderIntent}
                  onTransitionIntent={handleTransitionIntent}
                  onRequestExecution={handleRequestExecution}
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
                onStageOrderIntent={handleStageOrderIntent}
                onTransitionIntent={handleTransitionIntent}
                onRequestExecution={handleRequestExecution}
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
                onStageOrderIntent={handleStageOrderIntent}
                onTransitionIntent={handleTransitionIntent}
                onRequestExecution={handleRequestExecution}
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
                onStageOrderIntent={handleStageOrderIntent}
                onTransitionIntent={handleTransitionIntent}
                onRequestExecution={handleRequestExecution}
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
                onStageOrderIntent={handleStageOrderIntent}
                onTransitionIntent={handleTransitionIntent}
                onRequestExecution={handleRequestExecution}
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

      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        snapshot={snapshot}
        onSelectSymbol={handleSelectSymbol}
      />

      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        onLoginSuccess={handleLoginSuccess}
        currentAccount={authState.userAccount}
      />
    </div>
  );
}
