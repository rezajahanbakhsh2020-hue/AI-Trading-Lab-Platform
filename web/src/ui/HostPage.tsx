import { useState } from "react";
import { Link } from "react-router-dom";
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
import { INITIAL_NOTIFICATIONS, type NotificationItem } from "../architecture/marketData";

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
  const normalizedPageId =
    pageId === "market"
      ? "markets"
      : pageId === "strategy"
      ? "strategies"
      : pageId === "learning"
      ? "academy"
      : pageId;

  const copy = PAGE_COPY[normalizedPageId] ?? PAGE_COPY[pageId] ?? PAGE_COPY.dashboard;

  return (
    <div className="page-workspace">
      <div className="page-header">
        <div>
          <p className="kicker">{copy.kicker}</p>
          <h2>{copy.title}</h2>
          <p className="lede">{copy.summary}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {onToggleConnection && (
            <button
              className={`btn ${snapshot.project1.connected ? "btn-secondary" : "btn-primary"}`}
              onClick={onToggleConnection}
              style={{ fontSize: 13, padding: "6px 12px" }}
            >
              {snapshot.project1.connected
                ? "Use Disconnected Adapter"
                : "Connect Project 1 Port"}
            </button>
          )}
          <span className="chip">
            <span className={`dot ${snapshot.project1.connected ? "ready" : "warn"}`} />
            {snapshot.project1.connected ? "Project 1 Connected" : "Integration-ready"}
          </span>
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
      {normalizedPageId === "monitoring" && <MonitoringPage snapshot={snapshot} />}
      {normalizedPageId === "providers" && <ProvidersPage snapshot={snapshot} />}
      {(normalizedPageId === "academy" || pageId === "learning") && <AcademyPage />}
      {normalizedPageId === "notifications" && <NotificationsPage />}
      {normalizedPageId === "logs" && <LogsPage />}
      {normalizedPageId === "settings" && <SettingsPage snapshot={snapshot} />}

      <p className="footer-status">
        {snapshot.project1.connected
          ? `Connected to ${snapshot.project1.adapterName} (${snapshot.project1.port}). Real Project 1 output active.`
          : "Presentation layer only. Values stay unavailable until Project 1 and platform adapters supply them."}
      </p>
    </div>
  );
}

/* Page Subviews */

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
  const quote = snapshot.market.quote;
  const quotePrice = quote?.last ?? quote?.mid ?? quote?.bid ?? snapshot.risk.entry ?? null;

  return (
    <div className="dashboard-view">
      <MarketPulse quotePrice={quotePrice} change24hPct={quote?.changePercent} />

      <div className="grid cols-4" style={{ marginTop: 16 }}>
        <MetricCard
          title="Platform"
          value="Ready"
          status={snapshot.platform.status}
          message={snapshot.platform.role}
        />
        <MetricCard
          title="Project 1"
          value={snapshot.project1.connected ? "Connected" : "Disconnected"}
          status={snapshot.project1.status}
          message={snapshot.project1.message}
        />
        <MetricCard
          title="Primary Market"
          value={snapshot.market.symbol}
          status={snapshot.market.status === "connected" ? "ready" : snapshot.market.status}
          message={snapshot.market.message}
        />
        <MetricCard
          title="Latest Signal"
          value={snapshot.signal.action || "No signal"}
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
          isProviderConnected={snapshot.project1.connected && snapshot.market.status === "connected"}
          onTimeframeChange={onSelectTimeframe}
          onRefresh={onSync}
        />

        <SignalCard snapshot={snapshot} onSync={onSync} />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <WatchlistWidget quote={snapshot.market.quote} onSelectSymbol={onSelectSymbol} />

        <div className="card">
          <div className="card-head">
            <h3>Academy & Quick Learning</h3>
            <span className="chip ready-chip">10 Modules</span>
          </div>
          <div className="card-body">
            <p className="hint">
              Explore original guides on Risk Management, Walk-Forward Validation, Technical Analysis, and Glossary terms.
            </p>
            <div className="academy-banner-box" style={{ marginTop: 16 }}>
              <strong>Master Quantitative Trading Concepts</strong>
              <p className="hint" style={{ marginTop: 6 }}>
                Learn how Project 1 generates signals and how Project 2 validates and presents trading intelligence.
              </p>
              <Link to="/academy" className="btn btn-primary" style={{ marginTop: 12, display: "inline-block" }}>
                Open Trading Academy →
              </Link>
            </div>
          </div>
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
            <h3>Market Symbol Selector</h3>
            <span className="chip">{currentSymbol} Selected</span>
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
                    {isMarketConnected && sym === currentSymbol ? "Connected" : "Disconnected"}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{currentSymbol} Real-Time Quote</h3>
            <span className={`status ${isMarketConnected ? "ready" : snapshot.market.status}`}>
              {isMarketConnected ? "Connected" : snapshot.market.status}
            </span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>Current Price</th>
                  <td>
                    {quote?.last != null
                      ? `$${quote.last.toFixed(2)} USD`
                      : quote?.mid != null
                      ? `$${quote.mid.toFixed(2)} USD`
                      : snapshot.risk.entry
                      ? `$${snapshot.risk.entry.toFixed(2)} USD`
                      : "Unavailable"}
                  </td>
                </tr>
                <tr>
                  <th>Bid / Ask</th>
                  <td>
                    {quote?.bid != null && quote?.ask != null
                      ? `$${quote.bid.toFixed(2)} / $${quote.ask.toFixed(2)}`
                      : "Unavailable"}
                  </td>
                </tr>
                <tr>
                  <th>24h Change</th>
                  <td>
                    {quote?.changePercent != null
                      ? `${quote.changePercent >= 0 ? "+" : ""}${quote.changePercent.toFixed(2)}%`
                      : "Unavailable"}
                  </td>
                </tr>
                <tr>
                  <th>24h High / Low</th>
                  <td>
                    {quote?.high24h != null && quote?.low24h != null
                      ? `$${quote.high24h.toFixed(2)} / $${quote.low24h.toFixed(2)}`
                      : "Unavailable"}
                  </td>
                </tr>
                <tr>
                  <th>Timeframe</th>
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
      <WatchlistWidget quote={snapshot.market.quote} onSelectSymbol={onSelectSymbol} />
    </div>
  );
}

function SignalsPage({ snapshot, onSync }: { snapshot: HostSnapshot; onSync?: () => void }) {
  return (
    <div className="signals-view">
      <SignalCard snapshot={snapshot} onSync={onSync} />
    </div>
  );
}

function StrategiesPage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="strategies-view">
      <StrategyCard snapshot={snapshot} />
    </div>
  );
}

function BacktestPage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="backtest-view">
      <div className="card">
        <div className="card-head">
          <h3>Historical Backtest Surface</h3>
          <span className="status unavailable">Waiting for Project 1</span>
        </div>
        <div className="card-body">
          <EmptyState
            title="No Project 1 backtest connected yet."
            message={snapshot.performance.message}
          />
        </div>
      </div>
    </div>
  );
}

function PerformancePage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="performance-view">
      <div className="card">
        <div className="card-head">
          <h3>Performance Metrics & Equity Curve</h3>
          <span className="status unavailable">Unavailable</span>
        </div>
        <div className="card-body">
          <EmptyState
            title="No performance data connected yet."
            message={snapshot.performance.message}
          />
        </div>
      </div>
    </div>
  );
}

function RiskPage({ snapshot }: { snapshot: HostSnapshot }) {
  const levels = [
    ["Entry Price", snapshot.risk.entry],
    ["Stop Loss (SL)", snapshot.risk.stopLoss],
    ["Take Profit 1 (TP1)", snapshot.risk.takeProfits[0] ?? null],
    ["Take Profit 2 (TP2)", snapshot.risk.takeProfits[1] ?? null],
    ["Take Profit 3 (TP3)", snapshot.risk.takeProfits[2] ?? null],
  ] as const;

  return (
    <div className="risk-view">
      <div className="grid cols-2">
        <section className="card">
          <div className="card-head">
            <h3>Trade Risk Breakdown</h3>
            <span className={`status ${snapshot.risk.status === "available" ? "ready" : "unavailable"}`}>
              {snapshot.risk.status === "available" ? "Active Setup" : "Unavailable"}
            </span>
          </div>
          <div className="card-body">
            <div className="levels">
              {levels.map(([label, value]) => (
                <div className="level" key={label}>
                  <span>{label}</span>
                  <b className={label.includes("Stop") ? "text-red" : label.includes("Take") ? "text-green" : ""}>
                    {value == null ? "Unavailable" : value}
                  </b>
                </div>
              ))}
            </div>
            <p className="hint" style={{ marginTop: 12 }}>
              {snapshot.risk.message}
            </p>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h3>Risk/Reward Calculator View</h3>
            <span className="status ready">1:2 Target</span>
          </div>
          <div className="card-body">
            <p className="hint">
              Position sizing and R:R ratios are evaluated based on 1% equity risk rules.
            </p>
            <div className="calc-preview-box" style={{ marginTop: 14 }}>
              <div className="calc-row">
                <span>Account Risk Limit:</span>
                <b>1.0% per trade</b>
              </div>
              <div className="calc-row">
                <span>Min Target R:R Ratio:</span>
                <b>1 : 2.0</b>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function MonitoringPage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="monitoring-view">
      <div className="grid cols-3">
        <MetricCard
          title="Freshness"
          value={snapshot.monitoring.freshness || "Unavailable"}
          status={snapshot.monitoring.status}
          message={snapshot.monitoring.message}
        />
        <MetricCard
          title="Market Data Provider"
          value={snapshot.market.provider ? snapshot.market.provider.name : "Disconnected"}
          status={snapshot.market.status === "connected" ? "ready" : snapshot.market.status}
          message={snapshot.market.message}
        />
        <MetricCard
          title="Live Observer"
          value={snapshot.project1.connected ? "Active" : "Idle"}
          status={snapshot.project1.connected ? "ready" : "unavailable"}
          message={snapshot.project1.connected ? "Monitoring Project 1 integration port." : "No live observations active."}
        />
      </div>
    </div>
  );
}

function ProvidersPage({ snapshot }: { snapshot: HostSnapshot }) {
  const providerName = snapshot.market.provider?.name || "BiQuoteProvider";

  return (
    <div className="providers-view">
      <section className="card">
        <div className="card-head">
          <h3>Provider Slots & Registry</h3>
          <span className={`status ${snapshot.project1.connected ? "ready" : "unavailable"}`}>
            {snapshot.project1.connected ? "Port Connected" : "Unconnected"}
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
                      {snapshot.project1.connected ? "Connected" : "Disconnected"}
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
                      {snapshot.market.quote ? "connected" : snapshot.market.status}
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

function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>(INITIAL_NOTIFICATIONS);

  const markAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  return (
    <div className="notifications-view">
      <div className="card">
        <div className="card-head">
          <div>
            <h3>Notifications & Feed</h3>
            <p className="hint">System events, integration logs, and alert history.</p>
          </div>
          <button className="btn btn-secondary" onClick={markAllAsRead}>
            Mark all read
          </button>
        </div>

        <div className="card-body">
          <div className="notifications-list">
            {notifications.map((n) => (
              <div
                key={n.id}
                className={n.read ? "notif-item read" : "notif-item unread"}
              >
                <div className="notif-head">
                  <strong className="notif-title">{n.title}</strong>
                  <span className="notif-time">{n.timestamp}</span>
                </div>
                <p className="hint" style={{ marginTop: 4 }}>
                  {n.message}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function LogsPage() {
  return (
    <div className="logs-view">
      <div className="card">
        <div className="card-head">
          <h3>Operational Event Logs</h3>
          <span className="status unavailable">Empty</span>
        </div>
        <div className="card-body">
          <EmptyState
            title="No host activity recorded yet."
            message="Operational logs will appear here when the host records real events."
          />
        </div>
      </div>
    </div>
  );
}

function SettingsPage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="settings-view">
      <div className="grid cols-2">
        <section className="card">
          <div className="card-head">
            <h3>Host Policy & System Guardrails</h3>
            <span className="status ready">Enforced</span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>Order Execution</th>
                  <td>Disabled (Presentation & Delivery Layer Only)</td>
                </tr>
                <tr>
                  <th>Exchange API Keys</th>
                  <td>Not Requested / Not Stored</td>
                </tr>
                <tr>
                  <th>Signal Intelligence Source</th>
                  <td>Project 1 via Project1IntegrationPort Contract</td>
                </tr>
                <tr>
                  <th>Active Adapter</th>
                  <td>{snapshot.project1.adapterName}</td>
                </tr>
                <tr>
                  <th>Primary Market Asset</th>
                  <td>{snapshot.market.symbol}</td>
                </tr>
                <tr>
                  <th>Architecture Pattern</th>
                  <td>Hexagonal Ports and Adapters</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h3>Integration Flow Topology</h3>
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
      </div>
    </div>
  );
}
