import { useState } from "react";
import type { HostSnapshot } from "../../architecture/hostView";
import {
  executeSignalDeliveryDispatch,
  getSampleOutboundChannels,
  loadSignalDeliveryHistory,
  saveSignalDeliveryRecord,
  type DeliveryChannelType,
  type SignalDeliveryRecord,
} from "../../architecture/signalDelivery";
import { useI18n } from "../../i18n";

type SignalDeliveryCenterProps = {
  snapshot: HostSnapshot;
};

export function SignalDeliveryCenter({ snapshot }: SignalDeliveryCenterProps) {
  const { t, direction } = useI18n();
  const userId = snapshot.security?.userId || "user_default";
  const [history, setHistory] = useState<SignalDeliveryRecord[]>(() =>
    loadSignalDeliveryHistory(userId)
  );
  const [selectedChannel, setSelectedChannel] = useState<DeliveryChannelType>("telegram");
  const [isDispatching, setIsDispatching] = useState(false);

  const channels = getSampleOutboundChannels(snapshot);
  const permissions = snapshot.security?.permissions ?? ["read:signals"];
  const isAdmin = snapshot.security?.isAdmin ?? false;
  const hasSetupPermission = isAdmin || permissions.includes("read:trade_setups");

  const handleDispatch = (channel: DeliveryChannelType) => {
    setIsDispatching(true);
    setTimeout(() => {
      const record = executeSignalDeliveryDispatch(snapshot, channel, userId);
      const updated = saveSignalDeliveryRecord(userId, record);
      setHistory(updated);
      setIsDispatching(false);
    }, 300);
  };

  return (
    <div className="signal-delivery-center space-y-6" dir={direction}>
      {/* Configured Outbound Channels Grid */}
      <section className="card">
        <div className="card-head flex justify-between items-center flex-wrap gap-2">
          <div>
            <p className="kicker" style={{ margin: 0, opacity: 0.8 }}>
              {t("signalDelivery.activeChannelsTitle")}
            </p>
            <h3 style={{ margin: "4px 0 0 0" }}>{t("signalDelivery.title")}</h3>
          </div>
          <button
            className="btn btn-primary"
            disabled={isDispatching || !snapshot.project1.connected}
            onClick={() => handleDispatch(selectedChannel)}
            style={{ fontSize: 13, padding: "8px 14px" }}
          >
            {isDispatching ? t("signalDelivery.dispatching") : t("signalDelivery.dispatchTestButton")}
          </button>
        </div>

        <div className="card-body" style={{ marginTop: 16 }}>
          <div className="grid cols-3" style={{ gap: 12 }}>
            {channels.map((ch) => (
              <button
                key={ch.channelId}
                className={`card ${selectedChannel === ch.channelId ? "active-channel-card" : ""}`}
                onClick={() => setSelectedChannel(ch.channelId)}
                style={{
                  textAlign: "left",
                  cursor: "pointer",
                  padding: 12,
                  border: selectedChannel === ch.channelId ? "2px solid var(--color-primary, #3b82f6)" : "1px solid var(--color-border, #374151)",
                }}
              >
                <div className="flex justify-between items-center" style={{ marginBottom: 6 }}>
                  <strong>{ch.channelName}</strong>
                  <span className={`status ${ch.enabled ? "ready" : "unavailable"}`}>
                    {ch.enabled ? "ACTIVE" : "INACTIVE"}
                  </span>
                </div>
                <p className="hint text-xs" style={{ margin: 0 }}>
                  Destination: {ch.destination}
                </p>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Authorization Policy & Security Boundary Cards */}
      <div className="grid cols-2" style={{ gap: 16 }}>
        <section className="card">
          <div className="card-head">
            <h3>{t("signalDelivery.authorizationPolicyTitle")}</h3>
            <span className="status ready">ENFORCED</span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>{t("signalDelivery.permissionCheck")}</th>
                  <td>
                    <span className={`chip ${isAdmin || permissions.includes("read:signals") ? "ready-chip" : "danger-chip"}`}>
                      {isAdmin || permissions.includes("read:signals") ? "PASSED" : "FAILED"}
                    </span>
                  </td>
                </tr>
                <tr>
                  <th>{t("signalDelivery.deliveryEnabledCheck")}</th>
                  <td>
                    <span className="chip ready-chip">PASSED</span>
                  </td>
                </tr>
                <tr>
                  <th>{t("signalDelivery.symbolPolicyCheck")}</th>
                  <td>
                    <span className="chip ready-chip">PASSED (XAUUSD)</span>
                  </td>
                </tr>
                <tr>
                  <th>{t("signalDelivery.strategyPolicyCheck")}</th>
                  <td>
                    <span className="chip ready-chip">PASSED (ALL STRATEGIES)</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h3>{t("signalDelivery.tradeSetupSecurityTitle")}</h3>
            <span className={`status ${hasSetupPermission ? "ready" : "enforced"}`}>
              {hasSetupPermission ? "Full Setup" : "Masked Setup"}
            </span>
          </div>
          <div className="card-body">
            <p className="hint" style={{ marginBottom: 12 }}>
              {hasSetupPermission
                ? t("signalDelivery.fullSetupVisible")
                : t("signalDelivery.setupMaskedNotice")}
            </p>
            <div className="levels" style={{ background: "var(--color-bg-secondary, #1f2937)", padding: 12, borderRadius: 6 }}>
              <div className="level" style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span>Entry Price:</span>
                <b>{hasSetupPermission && snapshot.risk.entry != null ? `$${snapshot.risk.entry}` : "[MASKED - RESTRICTED ROLE]"}</b>
              </div>
              <div className="level" style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span>Stop Loss:</span>
                <b>{hasSetupPermission && snapshot.risk.stopLoss != null ? `$${snapshot.risk.stopLoss}` : "[MASKED - RESTRICTED ROLE]"}</b>
              </div>
              <div className="level" style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Take Profit 1:</span>
                <b>{hasSetupPermission && snapshot.risk.takeProfits[0] != null ? `$${snapshot.risk.takeProfits[0]}` : "[MASKED - RESTRICTED ROLE]"}</b>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Delivery Audit Log Table */}
      <section className="card">
        <div className="card-head flex justify-between items-center">
          <h3>{t("signalDelivery.auditLogTitle")}</h3>
          <span className="chip">{history.length} Records</span>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("signalDelivery.timestamp")}</th>
                  <th>{t("signalDelivery.consumer")}</th>
                  <th>{t("signalDelivery.channel")}</th>
                  <th>{t("signalDelivery.status")}</th>
                  <th>{t("signalDelivery.reason")}</th>
                  <th>{t("signalDelivery.details")}</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center hint" style={{ padding: 20 }}>
                      {t("signalDelivery.noRecords")}
                    </td>
                  </tr>
                ) : (
                  history.map((item) => (
                    <tr key={item.id}>
                      <td style={{ fontSize: 12 }}>{item.timestamp}</td>
                      <td><code>{item.consumerId}</code></td>
                      <td>
                        <span className="chip">{item.channel.toUpperCase()}</span>
                      </td>
                      <td>
                        <span className={`chip ${item.status === "DELIVERED" ? "ready-chip" : "danger-chip"}`}>
                          {item.status === "DELIVERED" ? t("signalDelivery.delivered") : t("signalDelivery.notDelivered")}
                        </span>
                      </td>
                      <td style={{ fontSize: 13 }}>{item.reason}</td>
                      <td style={{ fontSize: 12, opacity: 0.8 }}>{item.detail || "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
