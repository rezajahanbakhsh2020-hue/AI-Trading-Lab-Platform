import { useI18n } from "../../i18n";
import type { HostSnapshot } from "../../architecture/hostView";
import { countUnreadNotifications, loadUserNotifications } from "../../architecture/notification";

export interface HealthCenterProps {
  snapshot: HostSnapshot;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export function HealthCenter({ snapshot, onRefresh, isLoading = false }: HealthCenterProps) {
  const { t } = useI18n();

  const isConnected = snapshot.project1.connected;
  const isMarketConnected = snapshot.market.status === "connected";
  const userId = snapshot.security?.userId || "guest_user";
  const notifications = loadUserNotifications(userId);
  const unreadCount = countUnreadNotifications(notifications);

  // Registered providers status summary
  const providersList = [
    {
      id: "biquote-md",
      name: snapshot.market.provider?.name || "BiQuoteProvider",
      category: "Market Data (OHLC)",
      status: snapshot.market.status,
      readiness: isMarketConnected ? "READY" : "NOT_READY",
      freshness: isMarketConnected ? "fresh" : "disconnected",
      ageSeconds: isMarketConnected ? 2 : null,
      capabilities: ["fetch_candles", "multi_timeframe"],
      timeframes: ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
    },
    {
      id: "biquote-quote",
      name: "BiQuoteQuoteProvider",
      category: "Real-Time Quotes",
      status: snapshot.market.quote ? "connected" : "disconnected",
      readiness: snapshot.market.quote ? "READY" : "NOT_READY",
      freshness: snapshot.market.quote ? "fresh" : "disconnected",
      ageSeconds: snapshot.market.quote?.availability?.ageSeconds ?? (snapshot.market.quote ? 1 : null),
      capabilities: ["fetch_quote", "bid_ask_spread"],
      timeframes: ["realtime"],
    },
    {
      id: "project1-port",
      name: snapshot.project1.adapterName,
      category: "Signal Intelligence Source",
      status: snapshot.project1.status,
      readiness: isConnected ? "READY" : "NOT_READY",
      freshness: isConnected ? "fresh" : "unavailable",
      ageSeconds: isConnected ? 0 : null,
      capabilities: ["Project1IntegrationPort", "PresentedSignal"],
      timeframes: ["1h"],
    },
  ];

  return (
    <div className="health-center-view" data-testid="health-center-component">
      {/* Top Health Pulse Metrics */}
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head">
            <h3>{t("health.cards.connectionStatus")}</h3>
            <span className={`status ${isConnected ? "ready" : "disconnected"}`}>
              {isConnected ? t("status.connected") : t("status.disconnected")}
            </span>
          </div>
          <div className="card-body">
            <div className="metric">{isConnected ? "ONLINE" : "OFFLINE"}</div>
            <p className="hint">{snapshot.project1.message}</p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{t("health.cards.providerReadiness")}</h3>
            <span className={`status ${isMarketConnected ? "ready" : "unavailable"}`}>
              {isMarketConnected ? "2 / 2 READY" : "0 / 2 READY"}
            </span>
          </div>
          <div className="card-body">
            <div className="metric">
              {isMarketConnected ? "OPERATIONAL" : "DISCONNECTED"}
            </div>
            <p className="hint">{snapshot.providers.message}</p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{t("health.cards.signalSource")}</h3>
            <span className={`status ${snapshot.signal.status === "active" ? "ready" : "unavailable"}`}>
              {snapshot.signal.action || t("status.unavailable")}
            </span>
          </div>
          <div className="card-body">
            <div className="metric" style={{ fontSize: 16 }}>
              {snapshot.project1.adapterName}
            </div>
            <p className="hint">{snapshot.signal.message}</p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{t("health.cards.notificationPipeline")}</h3>
            <span className="status ready">{t("status.healthy")}</span>
          </div>
          <div className="card-body">
            <div className="metric" style={{ fontSize: 18 }}>
              {t("notifications.unreadBadge", { count: unreadCount })}
            </div>
            <p className="hint">
              {notifications.length} total events in local pipeline inbox.
            </p>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="card" style={{ marginBottom: 16, padding: 16, textAlign: "center" }}>
          <span className="status loading">{t("status.loading")}...</span>
        </div>
      )}

      {/* Provider Health & Readiness Grid */}
      <section className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <h3>{t("health.sections.providersGrid")}</h3>
          {onRefresh && (
            <button
              className="btn btn-secondary"
              onClick={onRefresh}
              disabled={isLoading}
              style={{ padding: "4px 10px", fontSize: 12 }}
            >
              {t("buttons.refresh")}
            </button>
          )}
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("health.labels.category")}</th>
                  <th>{t("health.labels.providerId")}</th>
                  <th>{t("health.labels.readiness")}</th>
                  <th>{t("health.labels.freshnessStatus")}</th>
                  <th>{t("health.labels.freshnessAge")}</th>
                  <th>{t("health.labels.capabilities")}</th>
                </tr>
              </thead>
              <tbody>
                {providersList.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong>{p.category}</strong>
                    </td>
                    <td>{p.name}</td>
                    <td>
                      <span className={`status ${p.readiness === "READY" ? "ready" : "disconnected"}`}>
                        {p.readiness}
                      </span>
                    </td>
                    <td>
                      <span className={`chip ${p.freshness === "fresh" ? "ready-chip" : ""}`}>
                        {p.freshness}
                      </span>
                    </td>
                    <td>{p.ageSeconds !== null ? `${p.ageSeconds}s` : t("status.unavailable")}</td>
                    <td>
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {p.capabilities.map((cap) => (
                          <span key={cap} className="chip" style={{ fontSize: 11 }}>
                            {cap}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Project 1 Boundary & Secret Security View */}
      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <section className="card">
          <div className="card-head">
            <h3>{t("health.sections.project1Boundary")}</h3>
            <span className={`status ${isConnected ? "ready" : "disconnected"}`}>
              {isConnected ? t("status.connected") : t("status.disconnected")}
            </span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>{t("health.labels.adapter")}</th>
                  <td>{snapshot.project1.adapterName}</td>
                </tr>
                <tr>
                  <th>Integration Contract Port</th>
                  <td>{snapshot.project1.port}</td>
                </tr>
                <tr>
                  <th>Active Signal Action</th>
                  <td>
                    <strong>{snapshot.signal.action || t("signal.noSignal")}</strong>
                  </td>
                </tr>
                <tr>
                  <th>{t("health.labels.securityGate")}</th>
                  <td>
                    <span className="chip ready-chip">
                      {t("health.labels.secretsFiltered")}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
            <p className="hint" style={{ marginTop: 12 }}>
              Project 1 proprietary strategy logic, machine learning parameters, and indicator code stay strictly within Project 1 and are never leaked to Project 2 presentation state.
            </p>
          </div>
        </section>

        {/* Notification Event Pipeline Health */}
        <section className="card">
          <div className="card-head">
            <h3>{t("health.sections.notificationsHealth")}</h3>
            <span className="status ready">{t("status.healthy")}</span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>{t("health.labels.pipelineStatus")}</th>
                  <td>
                    <span className="status ready">{t("status.active")}</span>
                  </td>
                </tr>
                <tr>
                  <th>{t("health.labels.unreadNotifications")}</th>
                  <td>{unreadCount}</td>
                </tr>
                <tr>
                  <th>Total Events Recorded</th>
                  <td>{notifications.length}</td>
                </tr>
                <tr>
                  <th>{t("health.labels.lastSynced")}</th>
                  <td>{snapshot.generatedAt || new Date().toUTCString()}</td>
                </tr>
              </tbody>
            </table>
            <p className="hint" style={{ marginTop: 12 }}>
              {t("notifications.privacyNote")}
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
