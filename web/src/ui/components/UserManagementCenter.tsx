import React, { useState } from "react";
import { useI18n } from "../../i18n";
import { type HostSnapshot } from "../../architecture/hostView";
import {
  loadManagedAccounts,
  evaluateAccountStatus,
  createCustomerAccount,
  renewCustomerAccount,
  toggleAccountActiveStatus,
  type UserAccount,
} from "../../architecture/userAuth";

interface UserManagementCenterProps {
  currentAccount?: UserAccount | null;
  snapshot?: HostSnapshot;
}

export function UserManagementCenter({ currentAccount, snapshot }: UserManagementCenterProps) {
  const { t } = useI18n();
  const [accounts, setAccounts] = useState<UserAccount[]>(() => loadManagedAccounts());
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [startDaysOffset, setStartDaysOffset] = useState(0);
  const [durationDays, setDurationDays] = useState(30);
  const [allowedSymbolsInput, setAllowedSymbolsInput] = useState("XAUUSD, EURUSD");
  const [notificationMsg, setNotificationMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Fallback requester from snapshot if currentAccount is not explicitly supplied
  const effectiveAccount: UserAccount | null = currentAccount || (snapshot?.security ? {
    userId: snapshot.security.userId,
    role: snapshot.security.role as any,
    isActive: true,
    isPermanentAdmin: snapshot.security.isAdmin,
    activationTimestamp: null,
    expirationTimestamp: null,
    allowedSymbols: ["XAUUSD", "EURUSD"],
    allowedStrategies: [],
    permissions: snapshot.security.permissions,
  } : null);

  const isAdmin = effectiveAccount?.role === "admin" || effectiveAccount?.isPermanentAdmin === true;

  if (!isAdmin) {
    return (
      <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
        <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🔒</div>
        <h3 style={{ color: "#ef4444", marginBottom: "0.5rem" }}>{t("auth.accessDenied")}</h3>
        <p style={{ color: "#94a3b8", fontSize: "0.875rem", maxWidth: "500px", margin: "0 auto" }}>
          This section requires Owner/Admin permissions. Customer accounts cannot modify administrative settings or access user management capabilities.
        </p>
      </div>
    );
  }

  const handleCreateCustomer = (e: React.FormEvent) => {
    e.preventDefault();
    setNotificationMsg(null);

    const symbols = allowedSymbolsInput
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    const res = createCustomerAccount(
      effectiveAccount!,
      newUsername,
      startDaysOffset,
      durationDays,
      symbols.length > 0 ? symbols : ["XAUUSD"],
      accounts
    );

    if (res.success) {
      setAccounts(res.accounts);
      setNotificationMsg({ type: "success", text: res.message });
      setNewUsername("");
      setIsCreateModalOpen(false);
    } else {
      setNotificationMsg({ type: "error", text: res.message });
    }
  };

  const handleRenew = (targetUserId: string) => {
    setNotificationMsg(null);
    const res = renewCustomerAccount(effectiveAccount!, targetUserId, 30, accounts);
    if (res.success) {
      setAccounts(res.accounts);
      setNotificationMsg({ type: "success", text: res.message });
    } else {
      setNotificationMsg({ type: "error", text: res.message });
    }
  };

  const handleToggleStatus = (targetUserId: string) => {
    setNotificationMsg(null);
    const res = toggleAccountActiveStatus(effectiveAccount!, targetUserId, accounts);
    if (res.success) {
      setAccounts(res.accounts);
      setNotificationMsg({ type: "success", text: res.message });
    } else {
      setNotificationMsg({ type: "error", text: res.message });
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header Banner */}
      <div className="card" style={{ padding: "1.25rem", borderLeft: "4px solid #3b82f6" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.25rem", color: "#f8fafc" }}>{t("userMgmt.title")}</h2>
            <p style={{ margin: "0.25rem 0 0 0", color: "#94a3b8", fontSize: "0.875rem" }}>
              {t("userMgmt.subtitle")}
            </p>
          </div>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="btn btn-primary"
            style={{ minHeight: "44px", padding: "0.5rem 1rem", fontWeight: 600 }}
          >
            {t("userMgmt.createAccountButton")}
          </button>
        </div>
      </div>

      {/* Owner/Admin Permanent Protection Disclosure */}
      <div
        className="card"
        style={{
          padding: "1rem",
          backgroundColor: "rgba(168, 85, 247, 0.1)",
          borderColor: "#a855f7",
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
        }}
      >
        <span style={{ fontSize: "1.25rem" }}>🛡️</span>
        <div style={{ fontSize: "0.875rem", color: "#e9d5ff" }}>
          <strong>Owner/Admin Expiration Protection:</strong> The Owner/Admin account holds explicit permanent status and is strictly immune to customer expiration rules.
        </div>
      </div>

      {/* Notification Toast Banner */}
      {notificationMsg && (
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: "6px",
            backgroundColor: notificationMsg.type === "success" ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
            border: `1px solid ${notificationMsg.type === "success" ? "#22c55e" : "#ef4444"}`,
            color: notificationMsg.type === "success" ? "#4ade80" : "#fca5a5",
            fontSize: "0.875rem",
          }}
        >
          {notificationMsg.type === "success" ? "✅ " : "⚠️ "} {notificationMsg.text}
        </div>
      )}

      {/* Account List Grid / Cards */}
      <div className="card" style={{ padding: "1rem", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textWrap: "nowrap" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #334155", textAlign: "left", fontSize: "0.75rem", color: "#94a3b8", textTransform: "uppercase" }}>
              <th style={{ padding: "0.75rem 0.5rem" }}>{t("userMgmt.username")}</th>
              <th style={{ padding: "0.75rem 0.5rem" }}>{t("userMgmt.status")}</th>
              <th style={{ padding: "0.75rem 0.5rem" }}>{t("userMgmt.activationDate")}</th>
              <th style={{ padding: "0.75rem 0.5rem" }}>{t("userMgmt.expirationDate")}</th>
              <th style={{ padding: "0.75rem 0.5rem" }}>{t("userMgmt.allowedSymbolsLabel")}</th>
              <th style={{ padding: "0.75rem 0.5rem", textAlign: "right" }}>{t("userMgmt.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((acc) => {
              const evalRes = evaluateAccountStatus(acc);
              const formatTs = (ts: number | null) => (ts ? new Date(ts * 1000).toLocaleDateString() : "Permanent / No Limit");

              return (
                <tr key={acc.userId} style={{ borderBottom: "1px solid #1e293b", fontSize: "0.875rem" }}>
                  <td style={{ padding: "0.75rem 0.5rem", fontWeight: 600, color: "#f8fafc" }}>
                    {acc.userId} {acc.isPermanentAdmin && "👑"}
                  </td>

                  <td style={{ padding: "0.75rem 0.5rem" }}>
                    <span
                      style={{
                        padding: "0.25rem 0.5rem",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        backgroundColor:
                          evalRes.status === "PERMANENT_ADMIN"
                            ? "rgba(168, 85, 247, 0.2)"
                            : evalRes.status === "ACTIVE"
                            ? "rgba(34, 197, 94, 0.2)"
                            : evalRes.status === "EXPIRED"
                            ? "rgba(239, 68, 68, 0.2)"
                            : "rgba(245, 158, 11, 0.2)",
                        color:
                          evalRes.status === "PERMANENT_ADMIN"
                            ? "#c084fc"
                            : evalRes.status === "ACTIVE"
                            ? "#4ade80"
                            : evalRes.status === "EXPIRED"
                            ? "#fca5a5"
                            : "#fcd34d",
                      }}
                    >
                      {evalRes.status === "PERMANENT_ADMIN"
                        ? t("userMgmt.permanentAdminBadge")
                        : evalRes.status === "ACTIVE"
                        ? t("userMgmt.activeBadge")
                        : evalRes.status === "EXPIRED"
                        ? t("userMgmt.expiredBadge")
                        : evalRes.status === "INACTIVE"
                        ? t("userMgmt.inactiveBadge")
                        : t("userMgmt.futureBadge")}
                    </span>
                  </td>

                  <td style={{ padding: "0.75rem 0.5rem", color: "#cbd5e1" }}>
                    {formatTs(acc.activationTimestamp)}
                  </td>

                  <td style={{ padding: "0.75rem 0.5rem", color: "#cbd5e1" }}>
                    {formatTs(acc.expirationTimestamp)}
                  </td>

                  <td style={{ padding: "0.75rem 0.5rem", color: "#94a3b8", fontSize: "0.8125rem" }}>
                    {acc.allowedSymbols.join(", ")}
                  </td>

                  <td style={{ padding: "0.75rem 0.5rem", textAlign: "right" }}>
                    {acc.isPermanentAdmin ? (
                      <span style={{ fontSize: "0.75rem", color: "#a855f7" }}>Protected Admin</span>
                    ) : (
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                        <button
                          onClick={() => handleRenew(acc.userId)}
                          className="btn btn-secondary"
                          style={{ minHeight: "44px", fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
                          title={t("userMgmt.renewButton")}
                        >
                          🔄 {t("userMgmt.renewButton")}
                        </button>
                        <button
                          onClick={() => handleToggleStatus(acc.userId)}
                          className="btn btn-secondary"
                          style={{
                            minHeight: "44px",
                            fontSize: "0.75rem",
                            padding: "0.25rem 0.5rem",
                            borderColor: acc.isActive ? "#ef4444" : "#22c55e",
                            color: acc.isActive ? "#fca5a5" : "#4ade80",
                          }}
                        >
                          {acc.isActive ? t("userMgmt.deactivateButton") : t("userMgmt.activateButton")}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Creation Modal */}
      {isCreateModalOpen && (
        <div className="command-palette-backdrop" onClick={() => setIsCreateModalOpen(false)}>
          <div
            className="command-palette-modal"
            style={{ maxWidth: "500px", width: "92%" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.125rem", color: "#f8fafc" }}>
                {t("userMgmt.createModalTitle")}
              </h3>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="btn btn-ghost"
                style={{ minHeight: "44px", minWidth: "44px", color: "#94a3b8" }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCustomer} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  {t("userMgmt.username")}
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="e.g. client_investor_01"
                  required
                />
              </div>

              <div>
                <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  {t("userMgmt.startDaysLabel")}
                </label>
                <input
                  type="number"
                  className="search-input"
                  style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                  value={startDaysOffset}
                  onChange={(e) => setStartDaysOffset(parseInt(e.target.value, 10) || 0)}
                  min={0}
                  required
                />
              </div>

              <div>
                <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  {t("userMgmt.durationDaysLabel")}
                </label>
                <input
                  type="number"
                  className="search-input"
                  style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                  value={durationDays}
                  onChange={(e) => setDurationDays(parseInt(e.target.value, 10) || 1)}
                  min={1}
                  required
                />
              </div>

              <div>
                <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  {t("userMgmt.allowedSymbolsLabel")}
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                  value={allowedSymbolsInput}
                  onChange={(e) => setAllowedSymbolsInput(e.target.value)}
                  placeholder="XAUUSD, EURUSD, BTCUSD"
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="btn btn-ghost"
                  style={{ minHeight: "44px", padding: "0.5rem 1rem" }}
                >
                  {t("buttons.cancel")}
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ minHeight: "44px", padding: "0.5rem 1rem", fontWeight: 600 }}
                >
                  {t("buttons.save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
