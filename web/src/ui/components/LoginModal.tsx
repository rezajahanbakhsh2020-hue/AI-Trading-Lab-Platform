import React, { useState } from "react";
import { useI18n } from "../../i18n";
import { OperationalErrorBanner } from "./OperationalErrorBanner";
import {
  loadManagedAccounts,
  evaluateAccountStatus,
  saveSession,
  type UserAccount,
  type AuthSession,
} from "../../architecture/userAuth";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (session: AuthSession) => void;
  currentAccount?: UserAccount | null;
}

export function LoginModal({
  isOpen,
  onClose,
  onLoginSuccess,
  currentAccount,
}: LoginModalProps) {
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorReason, setErrorReason] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showRecovery, setShowRecovery] = useState(false);
  const [recoveryEmail, setRecoveryEmail] = useState("");
  const [recoverySuccessMsg, setRecoverySuccessMsg] = useState<string | null>(null);
  const [recoveryDeliveryInfo, setRecoveryDeliveryInfo] = useState<{ status: string; detail: string; token?: string | null } | null>(null);

  if (!isOpen) return null;

  const handleRecoveryRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorReason(null);
    setRecoverySuccessMsg(null);
    setRecoveryDeliveryInfo(null);

    const cleanEmail = recoveryEmail.trim();
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setErrorReason(t("auth.invalidCredentials"));
      return;
    }

    try {
      const res = await fetch("/api/v1/auth/recovery/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: username.trim() || "admin_owner", recovery_email: cleanEmail }),
      });
      const data = await res.json();
      setRecoveryDeliveryInfo({
        status: data.delivery_status || "NOT_CONFIGURED",
        detail: data.delivery_detail || "External email provider is Not Configured.",
        token: data.recovery_token || null,
      });
      setRecoverySuccessMsg(t("auth.recoverySentMsg"));
    } catch {
      setRecoveryDeliveryInfo({
        status: "NOT_CONFIGURED",
        detail: "External email provider is Not Configured. Follow recovery contract procedures.",
      });
      setRecoverySuccessMsg(t("auth.recoverySentMsg"));
    }
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (showRecovery) {
      handleRecoveryRequest(e);
      return;
    }

    setErrorReason(null);
    setIsSubmitting(true);

    const cleanUser = username.trim().toLowerCase();
    const cleanPwd = password.trim();

    if (!cleanUser || !cleanPwd) {
      setErrorReason(t("auth.invalidCredentials"));
      setIsSubmitting(false);
      return;
    }

    const accounts = loadManagedAccounts();
    const account = accounts.find((a) => a.userId.toLowerCase() === cleanUser);

    if (!account) {
      setErrorReason(t("auth.invalidCredentials"));
      setIsSubmitting(false);
      return;
    }

    // Evaluate expiration and activation state
    const evalRes = evaluateAccountStatus(account);
    if (!evalRes.isValid) {
      if (evalRes.status === "INACTIVE") {
        setErrorReason(t("auth.accountInactive"));
      } else if (evalRes.status === "EXPIRED") {
        setErrorReason(t("auth.accountExpired"));
      } else if (evalRes.status === "NOT_ACTIVE_YET") {
        setErrorReason(t("auth.accountNotActiveYet"));
      } else {
        setErrorReason(t("auth.accessDenied"));
      }
      setIsSubmitting(false);
      return;
    }

    const session: AuthSession = {
      token: `sess_${Date.now()}_${account.userId}`,
      user: account,
      loginTime: Math.floor(Date.now() / 1000),
    };

    saveSession(session);
    onLoginSuccess(session);
    setIsSubmitting(false);
    onClose();
  };

  const handleQuickLogin = (acc: UserAccount) => {
    setErrorReason(null);
    const evalRes = evaluateAccountStatus(acc);
    if (!evalRes.isValid) {
      if (evalRes.status === "INACTIVE") setErrorReason(t("auth.accountInactive"));
      else if (evalRes.status === "EXPIRED") setErrorReason(t("auth.accountExpired"));
      else if (evalRes.status === "NOT_ACTIVE_YET") setErrorReason(t("auth.accountNotActiveYet"));
      else setErrorReason(t("auth.accessDenied"));
      return;
    }

    const session: AuthSession = {
      token: `sess_${Date.now()}_${acc.userId}`,
      user: acc,
      loginTime: Math.floor(Date.now() / 1000),
    };
    saveSession(session);
    onLoginSuccess(session);
    onClose();
  };

  const accounts = loadManagedAccounts();

  return (
    <div className="command-palette-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="command-palette-modal"
        style={{ maxWidth: "480px", width: "92%" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, fontSize: "1.25rem", color: "#f8fafc" }}>{t("auth.loginTitle")}</h3>
          <button
            onClick={onClose}
            className="btn btn-ghost"
            style={{ minHeight: "44px", minWidth: "44px", color: "#94a3b8" }}
            aria-label={t("commandCenter.close")}
          >
            ✕
          </button>
        </div>

        <p style={{ color: "#94a3b8", fontSize: "0.875rem", marginBottom: "1.25rem" }}>
          {t("auth.loginSub")}
        </p>

        {errorReason && (
          <OperationalErrorBanner
            error={{
              whatHappenedKey: errorReason,
              whyLikelyKey: "errors.authFailedWhy",
              whatToCancelKey: "errors.authFailedAction",
              whatIfContinuesKey: "errors.authFailedSupport",
              correlationId: `auth_err_${Date.now().toString(16)}`,
            }}
            onDismiss={() => setErrorReason(null)}
          />
        )}

        <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {!showRecovery ? (
            <>
              <div>
                <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  {t("auth.usernameLabel")}
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. admin or trader_active"
                  required
                />
              </div>

              <div>
                <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  {t("auth.passwordLabel")}
                </label>
                <input
                  type="password"
                  className="search-input"
                  style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: "100%", minHeight: "44px", marginTop: "0.5rem", fontWeight: 600 }}
                disabled={isSubmitting}
              >
                {isSubmitting ? t("auth.loggingIn") : t("auth.loginButton")}
              </button>
            </>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem" }}>
                {t("auth.recoveryEmailLabel")}
              </label>
              <input
                type="email"
                className="search-input"
                style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                value={recoveryEmail}
                onChange={(e) => setRecoveryEmail(e.target.value)}
                placeholder="owner@domain.com"
                required
              />
              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: "100%", minHeight: "44px", fontWeight: 600 }}
              >
                {t("auth.requestRecoveryToken")}
              </button>
              {recoverySuccessMsg && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.25rem" }}>
                  <div style={{ color: "#4ade80", fontSize: "0.875rem" }}>
                    ✓ {recoverySuccessMsg}
                  </div>
                  {recoveryDeliveryInfo && (
                    <div
                      style={{
                        padding: "0.5rem 0.75rem",
                        borderRadius: "4px",
                        backgroundColor: "rgba(245, 158, 11, 0.15)",
                        border: "1px solid #f59e0b",
                        color: "#fcd34d",
                        fontSize: "0.8125rem",
                      }}
                    >
                      <div><strong>Delivery Status:</strong> {recoveryDeliveryInfo.status}</div>
                      <div style={{ fontSize: "0.75rem", marginTop: "0.25rem" }}>{recoveryDeliveryInfo.detail}</div>
                      {recoveryDeliveryInfo.token && (
                        <div style={{ marginTop: "0.375rem", fontFamily: "monospace", color: "#60a5fa" }}>
                          Recovery Token: <code>{recoveryDeliveryInfo.token}</code>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: 0, minHeight: "36px", color: "#60a5fa", fontSize: "0.875rem" }}
              onClick={() => {
                setShowRecovery(!showRecovery);
                setErrorReason(null);
                setRecoverySuccessMsg(null);
              }}
            >
              {showRecovery ? t("auth.backToLogin") : t("auth.forgotPassword")}
            </button>
          </div>
        </form>

        <div style={{ marginTop: "1.5rem", paddingTop: "1rem", borderTop: "1px solid #334155" }}>
          <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: "0.5rem", fontWeight: 600, textTransform: "uppercase" }}>
            Quick Account Portal Testing
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {accounts.map((acc) => {
              const evalRes = evaluateAccountStatus(acc);
              const isCurrent = currentAccount?.userId === acc.userId;
              return (
                <button
                  key={acc.userId}
                  onClick={() => handleQuickLogin(acc)}
                  className="btn btn-secondary"
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    minHeight: "44px",
                    padding: "0.5rem 0.75rem",
                    textAlign: "left",
                    borderColor: isCurrent ? "#3b82f6" : "#334155",
                    backgroundColor: isCurrent ? "rgba(59, 130, 246, 0.1)" : undefined,
                  }}
                >
                  <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#f8fafc" }}>
                    {acc.userId} {acc.isPermanentAdmin && "👑"}
                  </span>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      padding: "0.125rem 0.5rem",
                      borderRadius: "4px",
                      fontWeight: 600,
                      backgroundColor:
                        evalRes.status === "PERMANENT_ADMIN"
                          ? "rgba(168, 85, 247, 0.2)"
                          : evalRes.status === "ACTIVE"
                          ? "rgba(34, 197, 94, 0.2)"
                          : "rgba(239, 68, 68, 0.2)",
                      color:
                        evalRes.status === "PERMANENT_ADMIN"
                          ? "#c084fc"
                          : evalRes.status === "ACTIVE"
                          ? "#4ade80"
                          : "#fca5a5",
                    }}
                  >
                    {evalRes.status}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
