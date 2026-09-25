import React, { useState } from "react";
import { useI18n } from "../../i18n";
import { OperationalErrorBanner } from "./OperationalErrorBanner";
import {
  loginWithPasswordApi,
  requestPasswordRecoveryApi,
  resetPasswordWithTokenApi,
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
}: LoginModalProps) {
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorReason, setErrorReason] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Recovery flow state
  const [showRecovery, setShowRecovery] = useState(false);
  const [recoveryEmail, setRecoveryEmail] = useState("");
  const [recoveryUserId, setRecoveryUserId] = useState("");
  const [recoveryToken, setRecoveryToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [recoveryStep, setRecoveryStep] = useState<"REQUEST" | "RESET" | "SUCCESS">("REQUEST");
  const [recoverySuccessMsg, setRecoverySuccessMsg] = useState<string | null>(null);
  const [recoveryDeliveryInfo, setRecoveryDeliveryInfo] = useState<{ status: string; detail: string; token?: string | null } | null>(null);

  if (!isOpen) return null;

  const resetAllStates = () => {
    setErrorReason(null);
    setIsSubmitting(false);
    setShowRecovery(false);
    setRecoveryStep("REQUEST");
    setRecoveryEmail("");
    setRecoveryUserId("");
    setRecoveryToken("");
    setNewPassword("");
    setRecoverySuccessMsg(null);
    setRecoveryDeliveryInfo(null);
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorReason(null);
    setIsSubmitting(true);

    const cleanUser = username.trim();
    const cleanPwd = password.trim();

    if (!cleanUser || !cleanPwd) {
      setErrorReason(t("auth.invalidCredentials"));
      setIsSubmitting(false);
      return;
    }

    const result = await loginWithPasswordApi(cleanUser, cleanPwd);
    setIsSubmitting(false);

    if (result.success && result.session) {
      onLoginSuccess(result.session);
      resetAllStates();
      onClose();
    } else {
      setErrorReason(result.message || t("auth.invalidCredentials"));
    }
  };

  const handleRecoveryRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorReason(null);
    setRecoverySuccessMsg(null);
    setRecoveryDeliveryInfo(null);
    setIsSubmitting(true);

    const cleanEmail = recoveryEmail.trim();
    const cleanUid = recoveryUserId.trim();

    if (!cleanEmail && !cleanUid) {
      setErrorReason("Provide an email address or User ID to request recovery.");
      setIsSubmitting(false);
      return;
    }

    const res = await requestPasswordRecoveryApi(cleanUid || cleanEmail, cleanEmail);
    setIsSubmitting(false);

    setRecoveryDeliveryInfo({
      status: res.deliveryStatus,
      detail: res.deliveryDetail || "",
      token: res.recoveryToken,
    });
    setRecoverySuccessMsg(res.message);

    // If token is directly returned or user is ready, move to RESET step
    if (res.recoveryToken) {
      setRecoveryToken(res.recoveryToken);
    }
    setRecoveryStep("RESET");
  };

  const handlePasswordResetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorReason(null);
    setIsSubmitting(true);

    const cleanUid = recoveryUserId.trim() || recoveryEmail.trim();
    const cleanToken = recoveryToken.trim();
    const cleanNewPwd = newPassword.trim();

    if (!cleanUid || !cleanToken || !cleanNewPwd) {
      setErrorReason("All recovery reset fields (User ID/Email, Token, New Password) are required.");
      setIsSubmitting(false);
      return;
    }

    const res = await resetPasswordWithTokenApi(cleanUid, cleanToken, cleanNewPwd);
    setIsSubmitting(false);

    if (res.success) {
      setRecoveryStep("SUCCESS");
      setRecoverySuccessMsg(res.message || "Password reset successfully. You can now log in with your new password.");
    } else {
      setErrorReason(res.message || "Password reset failed.");
    }
  };

  return (
    <div className="command-palette-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="command-palette-modal"
        style={{ maxWidth: "480px", width: "92%" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, fontSize: "1.25rem", color: "#f8fafc" }}>
            {showRecovery ? t("auth.forgotPassword") : t("auth.loginTitle")}
          </h3>
          <button
            onClick={() => {
              resetAllStates();
              onClose();
            }}
            className="btn btn-ghost"
            style={{ minHeight: "44px", minWidth: "44px", color: "#94a3b8" }}
            aria-label={t("commandCenter.close")}
          >
            ✕
          </button>
        </div>

        <p style={{ color: "#94a3b8", fontSize: "0.875rem", marginBottom: "1.25rem" }}>
          {showRecovery
            ? "Enter your account email to receive a secure password recovery token."
            : t("auth.loginSub")}
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

        {!showRecovery ? (
          <form onSubmit={handleLoginSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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
                placeholder="e.g. admin_owner or trader_active"
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

            <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", marginTop: "0.25rem" }}>
              <button
                type="button"
                className="btn btn-ghost"
                style={{ padding: 0, minHeight: "36px", color: "#60a5fa", fontSize: "0.875rem" }}
                onClick={() => {
                  setShowRecovery(true);
                  setErrorReason(null);
                }}
              >
                {t("auth.forgotPassword")}
              </button>
            </div>
          </form>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {recoveryStep === "REQUEST" && (
              <form onSubmit={handleRecoveryRequest} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div>
                  <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                    Account User ID (Optional)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                    value={recoveryUserId}
                    onChange={(e) => setRecoveryUserId(e.target.value)}
                    placeholder="e.g. admin_owner or trader_active"
                  />
                </div>

                <div>
                  <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
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
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: "100%", minHeight: "44px", fontWeight: 600 }}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Generating Token..." : t("auth.requestRecoveryToken")}
                </button>
              </form>
            )}

            {recoveryStep === "RESET" && (
              <form onSubmit={handlePasswordResetSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {recoverySuccessMsg && (
                  <div style={{ color: "#4ade80", fontSize: "0.875rem" }}>
                    ✓ {recoverySuccessMsg}
                  </div>
                )}

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
                  </div>
                )}

                <div>
                  <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                    Account User ID / Email
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                    value={recoveryUserId || recoveryEmail}
                    onChange={(e) => setRecoveryUserId(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                    Recovery Token
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem", fontFamily: "monospace" }}
                    value={recoveryToken}
                    onChange={(e) => setRecoveryToken(e.target.value)}
                    placeholder="rec_..."
                    required
                  />
                </div>

                <div>
                  <label style={{ display: "block", color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                    New Password
                  </label>
                  <input
                    type="password"
                    className="search-input"
                    style={{ width: "100%", minHeight: "44px", padding: "0.5rem 0.75rem" }}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: "100%", minHeight: "44px", fontWeight: 600 }}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Resetting Password..." : "Reset Password & Login"}
                </button>
              </form>
            )}

            {recoveryStep === "SUCCESS" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div style={{ color: "#4ade80", fontSize: "0.9375rem", fontWeight: 600, padding: "0.75rem", backgroundColor: "rgba(34, 197, 94, 0.15)", borderRadius: "4px" }}>
                  ✓ {recoverySuccessMsg}
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: "100%", minHeight: "44px" }}
                  onClick={() => {
                    resetAllStates();
                  }}
                >
                  Return to Login
                </button>
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-start", alignItems: "center" }}>
              <button
                type="button"
                className="btn btn-ghost"
                style={{ padding: 0, minHeight: "36px", color: "#60a5fa", fontSize: "0.875rem" }}
                onClick={() => {
                  resetAllStates();
                }}
              >
                ← {t("auth.backToLogin")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
