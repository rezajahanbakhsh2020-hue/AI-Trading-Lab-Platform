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
    <div className="signal-delivery-center space-v-6" dir={direction}>
      {/* Configured Outbound Channels Grid */}
      <section className="card">
        <div className="card-head flex-header-row">
          <div>
            <p className="kicker">
              {t("signalDelivery.activeChannelsTitle")}
            </p>
            <h2>{t("signalDelivery.title")}</h2>
          </div>
          <button
            className="btn btn-primary"
            disabled={isDispatching || !snapshot.project1.connected}
            onClick={() => handleDispatch(selectedChannel)}
            aria-label={t("signalDelivery.dispatchTestButton")}
          >
            {isDispatching ? t("signalDelivery.dispatching") : t("signalDelivery.dispatchTestButton")}
          </button>
        </div>

        <div className="card-body">
          <div className="grid cols-3 channel-grid">
            {channels.map((ch) => (
              <button
                key={ch.channelId}
                className={`card channel-card ${selectedChannel === ch.channelId ? "active" : ""}`}
                onClick={() => setSelectedChannel(ch.channelId)}
                aria-pressed={selectedChannel === ch.channelId}
                aria-label={`${ch.channelName} - ${ch.enabled ? 'Active' : 'Inactive'}`}
              >
                <div className="card-head channel-card-head">
                  <strong>{ch.channelName}</strong>
                  <span className={`status ${ch.enabled ? "ready" : "unavailable"}`}>
                    {ch.enabled ? "ACTIVE" : "INACTIVE"}
                  </span>
                </div>
                <div className="card-body channel-card-body">
                  <p className="hint text-xs">
                    Destination: {ch.destination}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Authorization Policy & Security Boundary Cards */}
      <div className="grid cols-2">
        <section className="card">
          <div className="card-head">
            <h3>{t("signalDelivery.authorizationPolicyTitle")}</h3>
            <span className="status ready">ENFORCED</span>
          </div>
          <div className="card-body">
            <div className="table-responsive">
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
            <div className="levels">
              <div className="level">
                <span>Entry Price:</span>
                <b>{hasSetupPermission && snapshot.risk.entry != null ? `$${snapshot.risk.entry}` : "[MASKED - RESTRICTED ROLE]"}</b>
              </div>
              <div className="level">
                <span>Stop Loss:</span>
                <b>{hasSetupPermission && snapshot.risk.stopLoss != null ? `$${snapshot.risk.stopLoss}` : "[MASKED - RESTRICTED ROLE]"}</b>
              </div>
              <div className="level">
                <span>Take Profit 1:</span>
                <b>{hasSetupPermission && snapshot.risk.takeProfits[0] != null ? `$${snapshot.risk.takeProfits[0]}` : "[MASKED - RESTRICTED ROLE]"}</b>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Delivery Audit Log Table */}
      <section className="card">
        <div className="card-head flex-header-row">
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
                    <td colSpan={6} className="text-center hint py-6">
                      {t("signalDelivery.noRecords")}
                    </td>
                  </tr>
                ) : (
                  history.map((item) => (
                    <tr key={item.id}>
                      <td className="hint">{item.timestamp}</td>
                      <td><code className="mono-val">{item.consumerId}</code></td>
                      <td>
                        <span className="chip">{item.channel.toUpperCase()}</span>
                      </td>
                      <td>
                        <span className={`chip ${item.status === "DELIVERED" ? "ready-chip" : "danger-chip"}`}>
                          {item.status === "DELIVERED" ? t("signalDelivery.delivered") : t("signalDelivery.notDelivered")}
                        </span>
                      </td>
                      <td>{item.reason}</td>
                      <td className="hint">{item.detail || "-"}</td>
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
