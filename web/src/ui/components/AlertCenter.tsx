import { useState } from "react";
import type { HostSnapshot } from "../../architecture/hostView";
import {
  type MarketAlertItem,
  type AlertRuleConfig,
  type AlertKind,
  type ConditionType,
  loadUserAlerts,
  saveUserAlerts,
  loadUserAlertRules,
  saveUserAlertRules,
  syncAlertsFromHostSnapshot,
} from "../../architecture/alert";
import { useI18n } from "../../i18n";

type AlertCenterProps = {
  snapshot: HostSnapshot;
};

export function AlertCenter({ snapshot }: AlertCenterProps) {
  const { t } = useI18n();
  const userId = snapshot.security?.userId || "guest_user";

  const [activeTab, setActiveTab] = useState<"alerts" | "rules">("alerts");
  const [rules, setRules] = useState<AlertRuleConfig[]>(() => loadUserAlertRules(userId));
  const [alerts, setAlerts] = useState<MarketAlertItem[]>(() => {
    const loaded = loadUserAlerts(userId);
    return syncAlertsFromHostSnapshot(userId, snapshot, loaded, rules);
  });

  // Filter states
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Rule creation form state
  const [newRuleKind, setNewRuleKind] = useState<AlertKind>("price");
  const [newRuleSymbol, setNewRuleSymbol] = useState<string>("XAUUSD");
  const [newRuleCond, setNewRuleCond] = useState<ConditionType>("price_above");
  const [newRuleThreshold, setNewRuleThreshold] = useState<string>("2700");
  const [newRuleExpectedVal, setNewRuleExpectedVal] = useState<string>("BUY");

  const updateAlerts = (newItems: MarketAlertItem[]) => {
    setAlerts(newItems);
    saveUserAlerts(userId, newItems);
  };

  const updateRules = (newRules: AlertRuleConfig[]) => {
    setRules(newRules);
    saveUserAlertRules(userId, newRules);
    const synced = syncAlertsFromHostSnapshot(userId, snapshot, alerts, newRules);
    setAlerts(synced);
  };

  const handleAcknowledge = (id: string) => {
    updateAlerts(
      alerts.map((a) => (a.id === id ? { ...a, status: "acknowledged" as const } : a))
    );
  };

  const handleResolve = (id: string) => {
    updateAlerts(
      alerts.map((a) => (a.id === id ? { ...a, status: "resolved" as const } : a))
    );
  };

  const handleClearResolved = () => {
    updateAlerts(alerts.filter((a) => a.status !== "resolved"));
  };

  const handleToggleRule = (ruleId: string) => {
    updateRules(
      rules.map((r) => (r.ruleId === ruleId ? { ...r, enabled: !r.enabled } : r))
    );
  };

  const handleDeleteRule = (ruleId: string) => {
    updateRules(rules.filter((r) => r.ruleId !== ruleId));
  };

  const handleCreateRule = (e: React.FormEvent) => {
    e.preventDefault();
    const newRule: AlertRuleConfig = {
      ruleId: `rule_${Date.now()}`,
      kind: newRuleKind,
      symbol: newRuleSymbol,
      conditionType: newRuleCond,
      threshold: newRuleCond.includes("price") || newRuleCond.includes("confidence") ? parseFloat(newRuleThreshold) || 0 : undefined,
      expectedValue: newRuleCond === "signal_action" ? newRuleExpectedVal : undefined,
      timeframe: "1h",
      enabled: true,
      createdAt: new Date().toISOString(),
    };
    updateRules([...rules, newRule]);
  };

  const filteredAlerts = alerts.filter((a) => {
    if (severityFilter !== "all" && a.severity !== severityFilter) return false;
    if (kindFilter !== "all" && a.kind !== kindFilter) return false;
    if (statusFilter !== "all" && a.status !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return a.message.toLowerCase().includes(q) || a.symbol.toLowerCase().includes(q);
    }
    return true;
  });

  const activeCount = alerts.filter((a) => a.status === "active").length;

  return (
    <div className="alert-center">
      <div className="flex items-center justify-between gap-4 mb-6">
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className={`btn ${activeTab === "alerts" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("alerts")}
          >
            {t("nav.alerts") || "Alerts"} ({activeCount})
          </button>
          <button
            className={`btn ${activeTab === "rules" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("rules")}
          >
            Rule Manager ({rules.length})
          </button>
        </div>
        {activeTab === "alerts" && (
          <button className="btn btn-secondary" onClick={handleClearResolved}>
            Clear Resolved Alerts
          </button>
        )}
      </div>

      {activeTab === "alerts" ? (
        <div className="alerts-tab space-y-4">
          <div className="grid cols-4 gap-3 mb-4 card" style={{ padding: 12 }}>
            <div>
              <label className="hint" style={{ fontSize: 11, display: "block" }}>Severity</label>
              <select
                className="select"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                style={{ width: "100%", padding: "6px" }}
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="warning">Warning</option>
                <option value="info">Info</option>
              </select>
            </div>
            <div>
              <label className="hint" style={{ fontSize: 11, display: "block" }}>Kind</label>
              <select
                className="select"
                value={kindFilter}
                onChange={(e) => setKindFilter(e.target.value)}
                style={{ width: "100%", padding: "6px" }}
              >
                <option value="all">All Kinds</option>
                <option value="price">Price</option>
                <option value="signal">Signal</option>
                <option value="freshness">Freshness</option>
                <option value="provider">Provider</option>
                <option value="security">Security</option>
              </select>
            </div>
            <div>
              <label className="hint" style={{ fontSize: 11, display: "block" }}>Status</label>
              <select
                className="select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{ width: "100%", padding: "6px" }}
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="acknowledged">Acknowledged</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>
            <div>
              <label className="hint" style={{ fontSize: 11, display: "block" }}>Search</label>
              <input
                type="text"
                placeholder="Search symbol or message..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: "100%", padding: "6px" }}
              />
            </div>
          </div>

          {filteredAlerts.length === 0 ? (
            <div className="card text-center" style={{ padding: 24 }}>
              <p className="hint">No alerts match the selected criteria.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredAlerts.map((alert) => (
                <div key={alert.id} className="card" style={{ padding: 14 }}>
                  <div className="card-head mb-2">
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className={`status ${alert.severity === "critical" ? "unavailable" : alert.severity === "warning" ? "warn" : "ready"}`}>
                        {alert.severity.toUpperCase()}
                      </span>
                      <strong>{alert.symbol}</strong>
                      <span className="chip" style={{ fontSize: 11 }}>{alert.kind}</span>
                    </div>
                    <span className="chip" style={{ fontSize: 11 }}>{alert.status}</span>
                  </div>
                  <p style={{ margin: "6px 0 10px 0" }}>{alert.message}</p>
                  <div className="flex items-center justify-between text-xs muted">
                    <span>{new Date(alert.createdAt).toLocaleString()}</span>
                    <div style={{ display: "flex", gap: 6 }}>
                      {alert.status === "active" && (
                        <button
                          className="btn btn-secondary"
                          onClick={() => handleAcknowledge(alert.id)}
                          style={{ padding: "4px 8px", fontSize: 11 }}
                        >
                          Acknowledge
                        </button>
                      )}
                      {alert.status !== "resolved" && (
                        <button
                          className="btn btn-primary"
                          onClick={() => handleResolve(alert.id)}
                          style={{ padding: "4px 8px", fontSize: 11 }}
                        >
                          Resolve
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="rules-tab grid cols-2 gap-4">
          <div className="card">
            <div className="card-head mb-3">
              <h3>Configured Alert Rules</h3>
            </div>
            <div className="space-y-3 card-body">
              {rules.length === 0 ? (
                <p className="hint">No custom alert rules configured.</p>
              ) : (
                rules.map((rule) => (
                  <div key={rule.ruleId} className="card" style={{ padding: 10, background: "rgba(255,255,255,0.02)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <strong>{rule.symbol} - {rule.kind.toUpperCase()}</strong>
                        <p className="hint" style={{ fontSize: 12, margin: "2px 0 0 0" }}>
                          Condition: {rule.conditionType}{" "}
                          {rule.threshold != null ? `(${rule.threshold})` : rule.expectedValue ? `(${rule.expectedValue})` : ""}
                        </p>
                      </div>
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <button
                          className={`btn ${rule.enabled ? "btn-primary" : "btn-secondary"}`}
                          onClick={() => handleToggleRule(rule.ruleId)}
                          style={{ padding: "4px 8px", fontSize: 11 }}
                        >
                          {rule.enabled ? "Enabled" : "Disabled"}
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() => handleDeleteRule(rule.ruleId)}
                          style={{ padding: "4px 8px", fontSize: 11 }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-head mb-3">
              <h3>Create Custom Alert Rule</h3>
            </div>
            <form onSubmit={handleCreateRule} className="space-y-3 card-body">
              <div>
                <label className="hint" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>Symbol</label>
                <select
                  className="select"
                  value={newRuleSymbol}
                  onChange={(e) => setNewRuleSymbol(e.target.value)}
                  style={{ width: "100%", padding: "8px" }}
                >
                  <option value="XAUUSD">XAUUSD</option>
                  <option value="EURUSD">EURUSD</option>
                  <option value="GBPUSD">GBPUSD</option>
                  <option value="BTCUSD">BTCUSD</option>
                  <option value="SPX500">SPX500</option>
                </select>
              </div>

              <div>
                <label className="hint" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>Alert Kind</label>
                <select
                  className="select"
                  value={newRuleKind}
                  onChange={(e) => setNewRuleKind(e.target.value as AlertKind)}
                  style={{ width: "100%", padding: "8px" }}
                >
                  <option value="price">Price</option>
                  <option value="signal">Signal</option>
                  <option value="freshness">Freshness</option>
                  <option value="provider">Provider</option>
                  <option value="security">Security</option>
                </select>
              </div>

              <div>
                <label className="hint" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>Condition Type</label>
                <select
                  className="select"
                  value={newRuleCond}
                  onChange={(e) => setNewRuleCond(e.target.value as ConditionType)}
                  style={{ width: "100%", padding: "8px" }}
                >
                  <option value="price_above">Price Above Threshold</option>
                  <option value="price_below">Price Below Threshold</option>
                  <option value="signal_action">Signal Action Matches</option>
                  <option value="confidence_below">Signal Confidence Below Threshold</option>
                  <option value="provider_disconnect">Provider Disconnect</option>
                </select>
              </div>

              {(newRuleCond === "price_above" || newRuleCond === "price_below" || newRuleCond === "confidence_below") && (
                <div>
                  <label className="hint" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>Threshold Value</label>
                  <input
                    type="number"
                    step="any"
                    value={newRuleThreshold}
                    onChange={(e) => setNewRuleThreshold(e.target.value)}
                    style={{ width: "100%", padding: "8px" }}
                    required
                  />
                </div>
              )}

              {newRuleCond === "signal_action" && (
                <div>
                  <label className="hint" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>Expected Action</label>
                  <select
                    className="select"
                    value={newRuleExpectedVal}
                    onChange={(e) => setNewRuleExpectedVal(e.target.value)}
                    style={{ width: "100%", padding: "8px" }}
                  >
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                    <option value="HOLD">HOLD</option>
                  </select>
                </div>
              )}

              <button type="submit" className="btn btn-primary" style={{ width: "100%", marginTop: 12 }}>
                Save Alert Rule
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
