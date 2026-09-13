import {
  INTEGRATION_FLOW,
  PAGE_COPY,
  type HostSnapshot,
} from "../architecture/hostView";

type HostPageProps = {
  pageId: string;
  snapshot: HostSnapshot;
};

function Unavailable({ title, message }: { title: string; message: string }) {
  return (
    <div className="empty">
      <h4>{title}</h4>
      <p className="hint">{message}</p>
    </div>
  );
}

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
  const copy = PAGE_COPY[pageId] ?? PAGE_COPY.dashboard;

  return (
    <div>
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

      {pageId === "dashboard" ? <Dashboard snapshot={snapshot} /> : null}
      {pageId === "market" ? <Market snapshot={snapshot} /> : null}
      {pageId === "strategy" ? <Strategy snapshot={snapshot} /> : null}
      {pageId === "backtest" ? (
        <Unavailable
          title="No Project 1 backtest connected yet."
          message={snapshot.performance.message}
        />
      ) : null}
      {pageId === "signals" ? <Signals snapshot={snapshot} /> : null}
      {pageId === "performance" ? (
        <Unavailable
          title="No performance data connected yet."
          message={snapshot.performance.message}
        />
      ) : null}
      {pageId === "risk" ? <Risk snapshot={snapshot} /> : null}
      {pageId === "monitoring" ? <Monitoring snapshot={snapshot} /> : null}
      {pageId === "providers" ? <Providers snapshot={snapshot} /> : null}
      {pageId === "logs" ? (
        <Unavailable
          title="No host activity recorded yet."
          message="Operational logs will appear here when the host records real events."
        />
      ) : null}
      {pageId === "settings" ? <Settings /> : null}

      <p className="footer-status">
        Presentation layer only. Values stay unavailable until Project 1 and
        platform adapters supply them.
      </p>
    </div>
  );
}

function Dashboard({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <>
      <div className="grid cols-4">
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
          title="Market"
          value={snapshot.market.symbol}
          status={snapshot.market.status}
          message={snapshot.market.message}
        />
        <MetricCard
          title="Signal"
          value="No signal"
          status={snapshot.signal.status}
          message={snapshot.signal.message}
        />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <section className="card">
          <div className="card-head">
            <h3>Integration path</h3>
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
        <section className="card">
          <div className="card-head">
            <h3>Recent activity</h3>
            <span className="status unavailable">empty</span>
          </div>
          <div className="card-body">
            <Unavailable
              title="No Project 1 data connected yet."
              message="This feed will list real host events after the integration port is attached."
            />
          </div>
        </section>
      </div>
    </>
  );
}

function Market({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <div className="grid cols-2">
      <section className="card">
        <div className="card-head">
          <h3>{snapshot.market.symbol} workspace</h3>
          <span className="status unavailable">chart unavailable</span>
        </div>
        <div className="card-body">
          <div className="chart-frame">
            Candlestick and volume panes are reserved for provider candles.
            No candles are loaded.
          </div>
        </div>
      </section>
      <section className="card">
        <div className="card-head">
          <h3>Quote</h3>
          <span className="status unavailable">unavailable</span>
        </div>
        <div className="card-body">
          <table className="table">
            <tbody>
              <tr>
                <th>Current price</th>
                <td>Unavailable</td>
              </tr>
              <tr>
                <th>Change</th>
                <td>Unavailable</td>
              </tr>
              <tr>
                <th>Volume</th>
                <td>Unavailable</td>
              </tr>
              <tr>
                <th>Timeframe</th>
                <td>Unavailable</td>
              </tr>
            </tbody>
          </table>
          <p className="hint" style={{ marginTop: 12 }}>
            {snapshot.market.message}
          </p>
        </div>
      </section>
    </div>
  );
}

function Strategy({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <section className="card">
      <div className="card-head">
        <h3>Strategy presentation</h3>
        <span className="status unavailable">owned by Project 1</span>
      </div>
      <div className="card-body">
        <table className="table">
          <tbody>
            <tr>
              <th>Strategy name</th>
              <td>Unavailable</td>
            </tr>
            <tr>
              <th>Stability score</th>
              <td>Unavailable</td>
            </tr>
            <tr>
              <th>Validation state</th>
              <td>Unavailable</td>
            </tr>
          </tbody>
        </table>
        <p className="hint" style={{ marginTop: 12 }}>
          {snapshot.strategy.message}
        </p>
      </div>
    </section>
  );
}

function Signals({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <section className="card">
      <div className="card-head">
        <h3>Signal board</h3>
        <span className="status unavailable">waiting</span>
      </div>
      <div className="card-body">
        <div className="grid cols-4">
          {["BUY", "SELL", "HOLD", "NO SIGNAL"].map((label) => (
            <div className="flow-step" key={label}>
              <span>state</span>
              <strong>{label}</strong>
              <p className="hint">Inactive until Project 1 emits a signal.</p>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 16 }}>
          <Unavailable
            title="No Project 1 data connected yet."
            message={snapshot.signal.message}
          />
        </div>
      </div>
    </section>
  );
}

function Risk({ snapshot }: { snapshot: HostSnapshot }) {
  const levels = [
    ["Entry", snapshot.risk.entry],
    ["Stop loss", snapshot.risk.stopLoss],
    ["TP1", snapshot.risk.takeProfits[0] ?? null],
    ["TP2", snapshot.risk.takeProfits[1] ?? null],
    ["TP3", snapshot.risk.takeProfits[2] ?? null],
  ] as const;

  return (
    <section className="card">
      <div className="card-head">
        <h3>Risk levels</h3>
        <span className="status unavailable">unavailable</span>
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
  );
}

function Monitoring({ snapshot }: { snapshot: HostSnapshot }) {
  return (
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
        title="Live status"
        value="Idle"
        status="unavailable"
        message="No live observations are being presented."
      />
    </div>
  );
}

function Providers({ snapshot }: { snapshot: HostSnapshot }) {
  return (
    <section className="card">
      <div className="card-head">
        <h3>Provider slots</h3>
        <span className="status unavailable">unconnected</span>
      </div>
      <div className="card-body">
        <table className="table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Status</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Market data</td>
              <td>{snapshot.providers.marketData}</td>
              <td>ProviderRegistry</td>
            </tr>
            <tr>
              <td>Quote</td>
              <td>{snapshot.providers.quote}</td>
              <td>ProviderRegistry</td>
            </tr>
          </tbody>
        </table>
        <p className="hint" style={{ marginTop: 12 }}>
          {snapshot.providers.message}
        </p>
      </div>
    </section>
  );
}

function Settings() {
  return (
    <section className="card">
      <div className="card-head">
        <h3>Host policy</h3>
        <span className="status ready">enforced</span>
      </div>
      <div className="card-body">
        <table className="table">
          <tbody>
            <tr>
              <th>Order execution</th>
              <td>Not part of this host</td>
            </tr>
            <tr>
              <th>Exchange API keys</th>
              <td>Not stored</td>
            </tr>
            <tr>
              <th>Signal source</th>
              <td>Project 1 via Project1IntegrationPort</td>
            </tr>
            <tr>
              <th>Primary market</th>
              <td>XAUUSD</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
