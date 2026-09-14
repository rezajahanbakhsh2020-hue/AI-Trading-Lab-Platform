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

export function HostPage({ pageId, snapshot }: HostPageProps) {
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
        <span className="chip">
          <span className="dot warn" />
          Integration-ready
        </span>
      </div>

      {(normalizedPageId === "dashboard" || pageId === "dashboard") && (
        <DashboardPage snapshot={snapshot} />
      )}
      {(normalizedPageId === "markets" || pageId === "market") && (
        <MarketsPage snapshot={snapshot} />
      )}
      {normalizedPageId === "watchlist" && <WatchlistPage />}
      {normalizedPageId === "signals" && <SignalsPage snapshot={snapshot} />}
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
        Presentation layer only. Values stay unavailable until Project 1 and platform adapters supply them.
      </p>
    </div>
  );
}

/* Page Subviews */

function DashboardPage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="dashboard-view">
      <MarketPulse />

      <div className="grid cols-4" style={{ marginTop: 16 }}>
        <MetricCard
          title="Platform"
          value="Ready"
          status={snapshot.platform.status}
          message={snapshot.platform.role}
        />
        <MetricCard
          title="Project 1"
          value="Disconnected"
          status={snapshot.project1.status}
          message={snapshot.project1.message}
        />
        <MetricCard
          title="Primary Market"
          value={snapshot.market.symbol}
          status={snapshot.market.status}
          message={snapshot.market.message}
        />
        <MetricCard
          title="Latest Signal"
          value="No signal"
          status={snapshot.signal.status}
          message={snapshot.signal.message}
        />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <InteractiveChart
          symbol={snapshot.market.symbol}
          isProviderConnected={snapshot.project1.connected}
        />

        <SignalCard snapshot={snapshot} />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <WatchlistWidget />

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

function MarketsPage({ snapshot }: { snapshot: HostSnapshot }) {
  const [selectedSymbol, setSelectedSymbol] = useState("XAUUSD");

  return (
    <div className="markets-view">
      <MarketPulse />

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="card-head">
            <h3>Market Symbol Selector</h3>
            <span className="chip">{selectedSymbol} Selected</span>
          </div>
          <div className="card-body">
            <div className="market-select-grid">
              {["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "SPX500"].map((sym) => (
                <button
                  key={sym}
                  className={selectedSymbol === sym ? "symbol-btn active" : "symbol-btn"}
                  onClick={() => setSelectedSymbol(sym)}
                >
                  <strong>{sym}</strong>
                  <span className="status disconnected">Disconnected</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{selectedSymbol} Real-Time Quote</h3>
            <span className="status unavailable">Disconnected</span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>Current Price</th>
                  <td>Unavailable</td>
                </tr>
                <tr>
                  <th>24h Change</th>
                  <td>Unavailable</td>
                </tr>
                <tr>
                  <th>24h Volume</th>
                  <td>Unavailable</td>
                </tr>
                <tr>
                  <th>Timeframe</th>
                  <td>Provider Session Inactive</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <InteractiveChart
          symbol={selectedSymbol}
          isProviderConnected={snapshot.project1.connected}
        />
      </div>
    </div>
  );
}

function WatchlistPage() {
  return (
    <div className="watchlist-view">
      <WatchlistWidget />
    </div>
  );
}

function SignalsPage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="signals-view">
      <SignalCard snapshot={snapshot} />
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
            <span className="status unavailable">Unavailable</span>
          </div>
          <div className="card-body">
            <div className="levels">
              {levels.map(([label, value]) => (
                <div className="level" key={label}>
                  <span>{label}</span>
                  <b>{value == null ? "Unavailable" : value}</b>
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
          value="Unavailable"
          status={snapshot.monitoring.status}
          message={snapshot.monitoring.message}
        />
        <MetricCard
          title="Health"
          value="Unavailable"
          status="unavailable"
          message="Provider health is evaluated by the existing operational gate."
        />
        <MetricCard
          title="Live Observer"
          value="Idle"
          status="unavailable"
          message="No live observations are currently active."
        />
      </div>
    </div>
  );
}

function ProvidersPage({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="providers-view">
      <section className="card">
        <div className="card-head">
          <h3>Provider Slots & Registry</h3>
          <span className="status unavailable">Unconnected</span>
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Slot Category</th>
                  <th>Status</th>
                  <th>Adapter Source</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Market Data Feed</td>
                  <td>{snapshot.providers.marketData}</td>
                  <td>ProviderRegistry</td>
                </tr>
                <tr>
                  <td>Real-Time Quotes</td>
                  <td>{snapshot.providers.quote}</td>
                  <td>ProviderRegistry</td>
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
                  <th>Primary Market Asset</th>
                  <td>XAUUSD (Spot Gold)</td>
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
