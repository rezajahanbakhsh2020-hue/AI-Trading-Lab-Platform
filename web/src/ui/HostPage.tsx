import { useState } from "react";
import {
  INTEGRATION_FLOW,
  PAGE_COPY,
  type HostSnapshot,
} from "../architecture/hostView";
import { MarketPulse } from "./components/MarketPulse";
import { InteractiveChart } from "./components/InteractiveChart";
import { WatchlistWidget } from "./components/WatchlistWidget";
import { SignalCard } from "./components/SignalCard";
import { StrategyCard } from "./components/StrategyCard";
import { AcademyViewer } from "./components/AcademyViewer";
import { EmptyState } from "./components/EmptyState";
import { NotificationCenter } from "./components/NotificationCenter";
import { AlertCenter } from "./components/AlertCenter";
import { HealthCenter } from "./components/HealthCenter";
import { IntelligenceTimeline } from "./components/IntelligenceTimeline";
import { AIAssistant } from "./components/AIAssistant";
import { BacktestViewer } from "./components/BacktestViewer";
import { PerformanceViewer } from "./components/PerformanceViewer";
import { RiskViewer } from "./components/RiskViewer";
import { IntelligenceWorkspace } from "./components/IntelligenceWorkspace";
import { SignalDeliveryCenter } from "./components/SignalDeliveryCenter";
import { OperationalControlCenter } from "./components/OperationalControlCenter";
import { OrderIntentViewer } from "./components/OrderIntentViewer";
import { UserManagementCenter } from "./components/UserManagementCenter";
import {
  loadUserNotifications,
  saveUserNotifications,
  syncNotificationsFromHostSnapshot,
  type NotificationItem,
} from "../architecture/notification";
import { useI18n, type SupportedLanguage } from "../i18n";

type HostPageProps = {
  pageId: string;
  snapshot: HostSnapshot;
  onSync?: () => void;
  onToggleConnection?: () => void;
  onSelectSymbol?: (symbol: string) => void;
  onSelectTimeframe?: (tf: string) => void;
};

function MetricCard({
  title,
  value,
  status,
  message,
}: {
  title: string;
  value: string;
  status: string;
  message: string;
}) {
  return (
    <section className="card">
      <div className="card-head">
        <h3>{title}</h3>
        <span className={`status ${status}`}>{status}</span>
      </div>
      <div className="card-body">
        <div className="metric muted">{value}</div>
        <p className="hint">{message}</p>
      </div>
    </section>
  );
}

export function HostPage({
  pageId,
  snapshot,
  onSync,
  onToggleConnection,
  onSelectSymbol,
  onSelectTimeframe,
}: HostPageProps) {
  const { t } = useI18n();

  const normalizedPageId =
    pageId === "market"
      ? "markets"
      : pageId === "strategy"
      ? "strategies"
      : pageId === "learning"
      ? "academy"
      : pageId;

  const copyTitle = t(`nav.${normalizedPageId}`) !== `nav.${normalizedPageId}`
    ? t(`nav.${normalizedPageId}`)
    : (PAGE_COPY[normalizedPageId] ?? PAGE_COPY[pageId] ?? PAGE_COPY.dashboard).title;

  const copyKicker = (PAGE_COPY[normalizedPageId] ?? PAGE_COPY[pageId] ?? PAGE_COPY.dashboard).kicker;
  const copySummary = t(`${normalizedPageId}.summary`) !== `${normalizedPageId}.summary`
    ? t(`${normalizedPageId}.summary`)
    : (PAGE_COPY[normalizedPageId] ?? PAGE_COPY[pageId] ?? PAGE_COPY.dashboard).summary;

  return (
    <div className="page-workspace">
      <div className="page-header">
        <div>
          <p className="kicker">{copyKicker}</p>
          <h2>{copyTitle}</h2>
          <p className="lede">{copySummary}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {onToggleConnection && (
            <button
              className={`btn ${snapshot.project1.connected ? "btn-secondary" : "btn-primary"}`}
              onClick={onToggleConnection}
              style={{ fontSize: 13, padding: "6px 12px" }}
            >
              {snapshot.project1.connected
                ? t("buttons.useDisconnectedAdapter")
                : t("buttons.connectProject1Port")}
            </button>
          )}
          <span className="chip">
            <span className={`dot ${snapshot.project1.connected ? "ready" : "warn"}`} />
            {snapshot.project1.connected ? t("status.project1Connected") : t("status.integrationReady")}
          </span>
          {snapshot.security && (
            <span className={`chip ${snapshot.security.isAdmin ? "ready-chip" : ""}`}>
              Role: <strong>{(snapshot.security.role || "user").toUpperCase()}</strong>
            </span>
          )}
        </div>
      </div>

      {(normalizedPageId === "dashboard" || pageId === "dashboard") && (
        <DashboardPage
          snapshot={snapshot}
          onSync={onSync}
          onSelectSymbol={onSelectSymbol}
          onSelectTimeframe={onSelectTimeframe}
        />
      )}
      {normalizedPageId === "timeline" && (
        <TimelinePage snapshot={snapshot} />
      )}
      {normalizedPageId === "screener" && (
        <IntelligenceWorkspace
          snapshot={snapshot}
          onSelectSymbol={onSelectSymbol}
        />
      )}
      {(normalizedPageId === "markets" || pageId === "market") && (
        <MarketsPage
          snapshot={snapshot}
          onSelectSymbol={onSelectSymbol}
          onSelectTimeframe={onSelectTimeframe}
          onRefresh={onSync}
        />
      )}
      {normalizedPageId === "watchlist" && (
        <WatchlistPage snapshot={snapshot} onSelectSymbol={onSelectSymbol} />
      )}
      {normalizedPageId === "signals" && <SignalsPage snapshot={snapshot} onSync={onSync} />}
      {(normalizedPageId === "strategies" || pageId === "strategy") && (
        <StrategiesPage snapshot={snapshot} />
      )}
      {normalizedPageId === "backtest" && <BacktestPage snapshot={snapshot} />}
      {normalizedPageId === "performance" && <PerformancePage snapshot={snapshot} />}
      {normalizedPageId === "risk" && <RiskPage snapshot={snapshot} />}
      {normalizedPageId === "audit" && <OperationalControlCenter snapshot={snapshot} />}
      {normalizedPageId === "intents" && <OrderIntentViewer snapshot={snapshot} />}
      {normalizedPageId === "users" && <UserManagementCenter snapshot={snapshot} />}
      {normalizedPageId === "health" && <HealthCenter snapshot={snapshot} onRefresh={onSync} />}
      {normalizedPageId === "monitoring" && <MonitoringPage snapshot={snapshot} />}
      {normalizedPageId === "providers" && <ProvidersPage snapshot={snapshot} />}
      {(normalizedPageId === "academy" || pageId === "learning") && <AcademyPage />}
      {normalizedPageId === "ai" && <AIAssistant snapshot={snapshot} />}
      {normalizedPageId === "alerts" && <AlertCenter snapshot={snapshot} />}
      {normalizedPageId === "notifications" && <NotificationsPage snapshot={snapshot} />}
      {normalizedPageId === "logs" && <LogsPage />}
      {normalizedPageId === "settings" && <SettingsPage snapshot={snapshot} />}

      <p className="footer-status">
        {snapshot.project1.connected
          ? t("footer.connectedText", { adapter: snapshot.project1.adapterName, port: snapshot.project1.port })
          : t("footer.disconnectedText")}
      </p>
    </div>
  );
}

/* Page Subviews */

function TimelinePage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="timeline-view space-y-6">
      <IntelligenceTimeline snapshot={snapshot} />
    </div>
  );
}

function DashboardPage({
  snapshot,
  onSync,
  onSelectSymbol,
  onSelectTimeframe,
}: {
  snapshot: HostSnapshot;
  onSync?: () => void;
  onSelectSymbol?: (symbol: string) => void;
  onSelectTimeframe?: (tf: string) => void;
}) {
  const { t } = useI18n();
  const quote = snapshot.market.quote;
  const quotePrice = quote?.last ?? quote?.mid ?? quote?.bid ?? snapshot.risk.entry ?? null;

  return (
    <div className="dashboard-view">
      <MarketPulse quotePrice={quotePrice} change24hPct={quote?.changePercent} />

      <div className="grid cols-4" style={{ marginTop: 16 }}>
        <MetricCard
          title={t("dashboard.platformCard")}
          value={t("status.ready")}
          status={snapshot.platform.status}
          message={snapshot.platform.role}
        />
        <MetricCard
          title={t("dashboard.project1Card")}
          value={snapshot.project1.connected ? t("status.connected") : t("status.disconnected")}
          status={snapshot.project1.status}
          message={snapshot.project1.message}
        />
        <MetricCard
          title={t("dashboard.primaryMarketCard")}
          value={snapshot.market.symbol}
          status={snapshot.market.status === "connected" ? "ready" : snapshot.market.status}
          message={snapshot.market.message}
        />
        <MetricCard
          title={t("signal.latestSignal")}
          value={snapshot.signal.action || t("signal.noSignal")}
          status={snapshot.signal.status}
          message={snapshot.signal.message}
        />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <InteractiveChart
          symbol={snapshot.market.symbol}
          timeframe={snapshot.market.timeframe}
          candles={snapshot.market.candles}
          status={snapshot.market.status}
          provider={snapshot.market.provider}
          entryPrice={snapshot.risk.entry}
          stopLossPrice={snapshot.risk.stopLoss}
          takeProfits={snapshot.risk.takeProfits}
          signalAction={snapshot.signal.action}
          isProviderConnected={snapshot.project1.connected && snapshot.market.status === "connected"}
          onTimeframeChange={onSelectTimeframe}
          onRefresh={onSync}
        />

        <SignalCard snapshot={snapshot} onSync={onSync} />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <WatchlistWidget
          quote={snapshot.market.quote}
          provider={snapshot.market.provider}
          userId={snapshot.security?.userId || "user_default"}
          activeSymbol={snapshot.market.symbol}
          onSelectSymbol={onSelectSymbol}
        />

        <div className="card">
          <IntelligenceTimeline snapshot={snapshot} compact={true} />
        </div>
      </div>
    </div>
  );
}

function MarketsPage({
  snapshot,
  onSelectSymbol,
  onSelectTimeframe,
  onRefresh,
}: {
  snapshot: HostSnapshot;
  onSelectSymbol?: (symbol: string) => void;
  onSelectTimeframe?: (tf: string) => void;
  onRefresh?: () => void;
}) {
  const { t, formatCurrency, formatPercent } = useI18n();
  const currentSymbol = snapshot.market.symbol;
  const quote = snapshot.market.quote;
  const isMarketConnected = snapshot.market.status === "connected";

  return (
    <div className="markets-view">
      <MarketPulse
        quotePrice={quote?.last ?? quote?.mid ?? quote?.bid ?? null}
        change24hPct={quote?.changePercent ?? null}
      />

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="card-head">
            <h3>{t("markets.selectorTitle")}</h3>
            <span className="chip">{t("markets.symbolSelected", { symbol: currentSymbol })}</span>
          </div>
          <div className="card-body">
            <div className="market-select-grid">
              {["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "SPX500"].map((sym) => (
                <button
                  key={sym}
                  className={currentSymbol === sym ? "symbol-btn active" : "symbol-btn"}
                  onClick={() => onSelectSymbol && onSelectSymbol(sym)}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "10px 12px" }}
                >
                  <strong>{sym}</strong>
                  <span className={`status ${isMarketConnected && sym === currentSymbol ? "ready" : "disconnected"}`}>
                    {isMarketConnected && sym === currentSymbol ? t("status.connected") : t("status.disconnected")}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{t("markets.quoteTitle", { symbol: currentSymbol })}</h3>
            <span className={`status ${isMarketConnected ? "ready" : snapshot.market.status}`}>
              {isMarketConnected ? t("status.connected") : snapshot.market.status}
            </span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>{t("markets.currentPrice")}</th>
                  <td>
                    {quote?.last != null
                      ? formatCurrency(quote.last)
                      : quote?.mid != null
                      ? formatCurrency(quote.mid)
                      : snapshot.risk.entry
                      ? formatCurrency(snapshot.risk.entry)
                      : t("status.unavailable")}
                  </td>
                </tr>
                <tr>
                  <th>{t("markets.bidAsk")}</th>
                  <td>
                    {quote?.bid != null && quote?.ask != null
                      ? `${formatCurrency(quote.bid)} / ${formatCurrency(quote.ask)}`
                      : t("status.unavailable")}
                  </td>
                </tr>
                <tr>
                  <th>{t("markets.change24h")}</th>
                  <td>
                    {quote?.changePercent != null
                      ? formatPercent(quote.changePercent)
                      : t("status.unavailable")}
                  </td>
                </tr>
                <tr>
                  <th>{t("markets.highLow24h")}</th>
                  <td>
                    {quote?.high24h != null && quote?.low24h != null
                      ? `${formatCurrency(quote.high24h)} / ${formatCurrency(quote.low24h)}`
                      : t("status.unavailable")}
                  </td>
                </tr>
                <tr>
                  <th>{t("markets.timeframe")}</th>
                  <td>{snapshot.market.timeframe || "1h"}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <InteractiveChart
          symbol={currentSymbol}
          timeframe={snapshot.market.timeframe}
          candles={snapshot.market.candles}
          status={snapshot.market.status}
          provider={snapshot.market.provider}
          entryPrice={currentSymbol === snapshot.market.symbol ? snapshot.risk.entry : null}
          stopLossPrice={currentSymbol === snapshot.market.symbol ? snapshot.risk.stopLoss : null}
          takeProfits={currentSymbol === snapshot.market.symbol ? snapshot.risk.takeProfits : []}
          signalAction={currentSymbol === snapshot.market.symbol ? snapshot.signal.action : null}
          isProviderConnected={snapshot.project1.connected && isMarketConnected}
          onTimeframeChange={onSelectTimeframe}
          onRefresh={onRefresh}
        />
      </div>
    </div>
  );
}

function WatchlistPage({
  snapshot,
  onSelectSymbol,
}: {
  snapshot: HostSnapshot;
  onSelectSymbol?: (symbol: string) => void;
}) {
  return (
    <div className="watchlist-view">
      <WatchlistWidget
        quote={snapshot.market.quote}
        provider={snapshot.market.provider}
        userId={snapshot.security?.userId || "user_default"}
        activeSymbol={snapshot.market.symbol}
        onSelectSymbol={onSelectSymbol}
      />
    </div>
  );
}

function SignalsPage({ snapshot, onSync }: { snapshot: HostSnapshot; onSync?: () => void }) {
  return (
    <div className="signals-view space-y-6">
      <SignalCard snapshot={snapshot} onSync={onSync} />
      <SignalDeliveryCenter snapshot={snapshot} />
    </div>
  );
}

function StrategiesPage({ snapshot }: { snapshot: HostSnapshot }) {
  const isAdmin = snapshot.security?.isAdmin ?? false;

  return (
    <div className="strategies-view">
      <StrategyCard snapshot={snapshot} />

      <section className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <h3>Proprietary Indicator & Research Security Gate</h3>
          <span className={`status ${isAdmin ? "ready" : "unavailable"}`}>
            {isAdmin ? "Admin Access Granted" : "Protected Resource"}
          </span>
        </div>
        <div className="card-body">
          {isAdmin ? (
            <div className="admin-secrets-panel">
              <p className="hint">
                Admin view authenticated. Sensitive research results and parameter calibrations are visible to admin roles only.
              </p>
            </div>
          ) : (
            <p className="hint text-red">
              Proprietary indicator logic, sensitive strategy parameters, and research results are restricted to ADMIN accounts. Normal users cannot access trading secrets or parameters through UI, alternate paths, errors, or APIs.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

function BacktestPage({ snapshot }: { snapshot: HostSnapshot }) {
  return <BacktestViewer snapshot={snapshot} />;
}

function PerformancePage({ snapshot }: { snapshot: HostSnapshot }) {
  return <PerformanceViewer snapshot={snapshot} />;
}

function RiskPage({ snapshot }: { snapshot: HostSnapshot }) {
  return <RiskViewer snapshot={snapshot} />;
}

function MonitoringPage({ snapshot }: { snapshot: HostSnapshot }) {
  const { t } = useI18n();
  const obs = snapshot.observability;

  return (
    <div className="monitoring-view space-v-6" data-testid="monitoring-page-view">
      {/* Primary Observability Cards */}
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <MetricCard
          title="Overall Platform Health"
          value={obs?.overall_status || snapshot.platform.status || "HEALTHY"}
          status={obs?.overall_status === "HEALTHY" ? "ready" : obs?.overall_status === "DEGRADED" ? "warn" : "unavailable"}
          message={`Environment: ${obs?.app_env || "production"} | Uptime: ${obs ? Math.round(obs.uptime_seconds) + "s" : "N/A"}`}
        />
        <MetricCard
          title="Market Data Freshness"
          value={obs?.market_data_freshness.freshness || snapshot.monitoring.freshness || t("status.unavailable")}
          status={snapshot.market.status === "connected" ? "ready" : "warn"}
          message={`Provider: ${snapshot.market.provider?.name || "BiQuote"} | Last Sync: ${snapshot.market.lastFetchedAt || "N/A"}`}
        />
        <MetricCard
          title="Execution Boundary Gate"
          value={snapshot.executionGateway?.allows_execution ? "EXECUTION_ALLOWED" : "NON_EXTERNAL_ENFORCED"}
          status="ready"
          message="Fail-closed execution boundary verified active."
        />
        <MetricCard
          title="Recent Failures / Incidents"
          value={`${obs?.recent_failures_count ?? snapshot.operationalFailures?.length ?? 0} Recorded`}
          status={(obs?.recent_failures_count ?? 0) === 0 ? "ready" : "warn"}
          message="Canonical failure log & correlation tracking active."
        />
      </div>

      {/* Subsystem Observability Detailed Matrix */}
      {obs?.components && (
        <section className="card">
          <div className="card-head flex-header-row">
            <h3>👁️ Unified Platform Subsystems & Observability Breakdown</h3>
            <span className="chip ready-chip">Real-Time Observability Active</span>
          </div>
          <div className="card-body">
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Subsystem Component</th>
                    <th>Status State</th>
                    <th>Configured</th>
                    <th>Dependency</th>
                    <th>Diagnostic Details</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(obs.components).map(([key, compVal]) => {
                    const comp = compVal as { name: string; status: string; configured: boolean; dependency: string; message: string };
                    return (
                      <tr key={key}>
                        <td>
                          <strong>{comp.name}</strong>
                        </td>
                        <td>
                          <span className={`status ${comp.status === "HEALTHY" ? "ready" : comp.status === "DEGRADED" ? "warn" : comp.status === "NOT_CONFIGURED" ? "muted-chip" : "unavailable"}`}>
                            {comp.status}
                          </span>
                        </td>
                        <td>
                          <span className={`chip ${comp.configured ? "ready-chip" : "muted-chip"}`}>
                            {comp.configured ? "YES" : "NO"}
                          </span>
                        </td>
                        <td>
                          <code>{comp.dependency}</code>
                        </td>
                        <td style={{ fontSize: 13 }}>{comp.message}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function ProvidersPage({ snapshot }: { snapshot: HostSnapshot }) {
  const { t } = useI18n();
  const providerName = snapshot.market.provider?.name || "BiQuoteProvider";

  return (
    <div className="providers-view">
      <section className="card">
        <div className="card-head">
          <h3>Provider Slots & Registry</h3>
          <span className={`status ${snapshot.project1.connected ? "ready" : "unavailable"}`}>
            {snapshot.project1.connected ? t("status.connected") : t("status.disconnected")}
          </span>
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Slot Category</th>
                  <th>Status</th>
                  <th>Adapter Source</th>
                  <th>Capabilities / Details</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Project 1 Integration Port</td>
                  <td>
                    <span className={`status ${snapshot.project1.connected ? "ready" : "disconnected"}`}>
                      {snapshot.project1.connected ? t("status.connected") : t("status.disconnected")}
                    </span>
                  </td>
                  <td>{snapshot.project1.adapterName}</td>
                  <td>Project1IntegrationPort</td>
                </tr>
                <tr>
                  <td>Market Data Feed (OHLC)</td>
                  <td>
                    <span className={`status ${snapshot.market.status === "connected" ? "ready" : snapshot.market.status}`}>
                      {snapshot.market.status}
                    </span>
                  </td>
                  <td>{providerName}</td>
                  <td>Supported Timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d</td>
                </tr>
                <tr>
                  <td>Real-Time Quotes</td>
                  <td>
                    <span className={`status ${snapshot.market.quote ? "ready" : snapshot.market.status}`}>
                      {snapshot.market.quote ? t("status.connected") : snapshot.market.status}
                    </span>
                  </td>
                  <td>BiQuoteQuoteProvider</td>
                  <td>Public REST quote feed</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="hint" style={{ marginTop: 12 }}>
            {snapshot.providers.message}
          </p>
        </div>
      </section>
    </div>
  );
}

function AcademyPage() {
  return <AcademyViewer />;
}

function NotificationsPage({ snapshot }: { snapshot: HostSnapshot }) {
  const userId = snapshot.security?.userId || "guest_user";
  const [notifications, setNotifications] = useState<NotificationItem[]>(() => {
    const loaded = loadUserNotifications(userId);
    return syncNotificationsFromHostSnapshot(userId, snapshot, loaded);
  });

  const updateNotifications = (newItems: NotificationItem[]) => {
    setNotifications(newItems);
    saveUserNotifications(userId, newItems);
  };

  const handleMarkRead = (id: string) => {
    updateNotifications(
      notifications.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const handleMarkAllRead = () => {
    updateNotifications(notifications.map((n) => ({ ...n, read: true })));
  };

  const handleArchive = (id: string) => {
    updateNotifications(
      notifications.map((n) => (n.id === id ? { ...n, archived: true } : n))
    );
  };

  const handleDelete = (id: string) => {
    updateNotifications(notifications.filter((n) => n.id !== id));
  };

  return (
    <div className="notifications-view">
      <NotificationCenter
        notifications={notifications}
        onMarkRead={handleMarkRead}
        onMarkAllRead={handleMarkAllRead}
        onArchive={handleArchive}
        onDelete={handleDelete}
      />
    </div>
  );
}

function LogsPage() {
  const { t } = useI18n();
  return (
    <div className="logs-view">
      <div className="card">
        <div className="card-head">
          <h3>{t("nav.logs")}</h3>
          <span className="status unavailable">{t("status.empty")}</span>
        </div>
        <div className="card-body">
          <EmptyState
            title={t("empty.noLogsTitle")}
            message={t("empty.noLogsMessage")}
          />
        </div>
      </div>
    </div>
  );
}

function SettingsPage({ snapshot }: { snapshot: HostSnapshot }) {
  const { t, language, setLanguage, supportedLanguages } = useI18n();
  const security = snapshot.security;

  return (
    <div className="settings-view">
      <div className="grid cols-2">
        <section className="card">
          <div className="card-head">
            <h3>Security Boundary & Access Control</h3>
            <span className={`status ${security?.isAdmin ? "ready" : "enforced"}`}>
              {security?.isAdmin ? "Admin Role" : "User Role"}
            </span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>User Identity</th>
                  <td>{security?.userId || "guest_user"}</td>
                </tr>
                <tr>
                  <th>Role</th>
                  <td>
                    <strong>{(security?.role || "user").toUpperCase()}</strong>
                  </td>
                </tr>
                <tr>
                  <th>Permissions</th>
                  <td>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {(security?.permissions || ["read:signals"]).map((p) => (
                        <span key={p} className="chip" style={{ fontSize: 11 }}>
                          {p}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
                <tr>
                  <th>Protected Secrets Boundary</th>
                  <td>{security?.isAdmin ? "Unlocked (Admin)" : "Protected (Restricted to Admin)"}</td>
                </tr>
              </tbody>
            </table>
            <p className="hint" style={{ marginTop: 12 }}>
              {security?.message}
            </p>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h3>{t("settings.policyTitle")}</h3>
            <span className="status ready">{t("status.enforced")}</span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>{t("settings.table.orderExecution")}</th>
                  <td>{t("settings.table.orderExecutionValue")}</td>
                </tr>
                <tr>
                  <th>{t("settings.table.apiKeys")}</th>
                  <td>{t("settings.table.apiKeysValue")}</td>
                </tr>
                <tr>
                  <th>{t("settings.table.source")}</th>
                  <td>{t("settings.table.sourceValue")}</td>
                </tr>
                <tr>
                  <th>{t("settings.table.adapter")}</th>
                  <td>{snapshot.project1.adapterName}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="card" style={{ gridColumn: "1 / -1", marginTop: 16 }}>
          <div className="card-head">
            <h3>{t("settings.flowTitle")}</h3>
            <span className="status">{snapshot.project1.port}</span>
          </div>
          <div className="card-body">
            <div className="flow">
              {INTEGRATION_FLOW.map((step, index) => (
                <div className="flow-step" key={step.id}>
                  <span>0{index + 1}</span>
                  <strong>{step.label}</strong>
                  <p className="hint">{step.role}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="card" style={{ gridColumn: "1 / -1", marginTop: 16 }}>
          <div className="card-head">
            <h3>{t("settings.languageSettings")}</h3>
            <span className="chip ready-chip">{language.toUpperCase()}</span>
          </div>
          <div className="card-body">
            <p className="hint" style={{ marginBottom: 12 }}>
              {t("settings.selectLanguageLabel")}
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
              {supportedLanguages.map((l) => (
                <button
                  key={l.code}
                  className={`btn ${language === l.code ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setLanguage(l.code as SupportedLanguage)}
                  style={{ gap: 10, padding: "10px 14px" }}
                >
                  <span style={{ fontSize: 16 }}>{l.flag}</span>
                  <strong>{l.nativeName}</strong>
                  <span style={{ fontSize: 11, opacity: 0.7 }}>({l.name} - {l.dir.toUpperCase()})</span>
                </button>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
