export type UserRole = "admin" | "user" | "guest";

export interface UserAccount {
  userId: string;
  role: UserRole;
  isActive: boolean;
  isPermanentAdmin: boolean;
  activationTimestamp: number | null;
  expirationTimestamp: number | null;
  allowedSymbols: readonly string[];
  allowedStrategies: readonly string[];
  detail?: string;
  permissions?: readonly string[];
}

export interface AuthSession {
  token: string;
  user: UserAccount;
  loginTime: number;
}

export interface StoredAuthState {
  isLoggedIn: boolean;
  sessionToken: string | null;
  userAccount: UserAccount | null;
}

export type AccountStatus = "ACTIVE" | "EXPIRED" | "INACTIVE" | "NOT_ACTIVE_YET" | "PERMANENT_ADMIN";

export interface AccountStatusEvaluation {
  isValid: boolean;
  status: AccountStatus;
  message: string;
}

export const PERMANENT_ADMIN_ACCOUNT: UserAccount = {
  userId: "admin",
  role: "admin",
  isActive: true,
  isPermanentAdmin: true,
  activationTimestamp: null,
  expirationTimestamp: null,
  allowedSymbols: ["XAUUSD", "EURUSD", "BTCUSD", "AAPL", "ETHUSD"],
  allowedStrategies: [],
  detail: "Protected Permanent Platform Owner/Admin",
  permissions: ["admin:all", "read:signals", "read:secrets", "read:lab_research"],
};

export function evaluateAccountStatus(
  account: UserAccount,
  nowSeconds: number = Math.floor(Date.now() / 1000)
): AccountStatusEvaluation {
  // Owner/Admin is permanently protected from expiration rules
  if (account.isPermanentAdmin || account.role === "admin") {
    return {
      isValid: true,
      status: "PERMANENT_ADMIN",
      message: "Protected permanent Owner/Admin account. Expiration rules do not apply.",
    };
  }

  if (!account.isActive) {
    return {
      isValid: false,
      status: "INACTIVE",
      message: "Account has been deactivated by system administration.",
    };
  }

  if (account.activationTimestamp !== null && nowSeconds < account.activationTimestamp) {
    return {
      isValid: false,
      status: "NOT_ACTIVE_YET",
      message: "Account activation date is in the future.",
    };
  }

  if (account.expirationTimestamp !== null && nowSeconds >= account.expirationTimestamp) {
    return {
      isValid: false,
      status: "EXPIRED",
      message: "Account subscription or time-limited access has expired.",
    };
  }

  return {
    isValid: true,
    status: "ACTIVE",
    message: "Account active and fully authorized.",
  };
}

const STORAGE_KEY_SESSION = "ai_trading_lab_session";
const STORAGE_KEY_ACCOUNTS = "ai_trading_lab_managed_accounts";

const now = Math.floor(Date.now() / 1000);
const dayInSeconds = 86400;

export const INITIAL_MANAGED_ACCOUNTS: UserAccount[] = [
  PERMANENT_ADMIN_ACCOUNT,
  {
    userId: "trader_active",
    role: "user",
    isActive: true,
    isPermanentAdmin: false,
    activationTimestamp: now - dayInSeconds * 5,
    expirationTimestamp: now + dayInSeconds * 30,
    allowedSymbols: ["XAUUSD", "EURUSD"],
    allowedStrategies: ["GoldTrendv1"],
    detail: "Standard Active Customer (Expires in 30 days)",
    permissions: ["read:signals", "read:trade_setups"],
  },
  {
    userId: "trader_expired",
    role: "user",
    isActive: true,
    isPermanentAdmin: false,
    activationTimestamp: now - dayInSeconds * 40,
    expirationTimestamp: now - dayInSeconds * 2,
    allowedSymbols: ["XAUUSD"],
    allowedStrategies: [],
    detail: "Expired Customer Account (Expired 2 days ago)",
    permissions: ["read:signals"],
  },
  {
    userId: "trader_inactive",
    role: "user",
    isActive: false,
    isPermanentAdmin: false,
    activationTimestamp: now - dayInSeconds * 10,
    expirationTimestamp: now + dayInSeconds * 20,
    allowedSymbols: ["XAUUSD"],
    allowedStrategies: [],
    detail: "Deactivated Customer Account",
    permissions: ["read:signals"],
  },
  {
    userId: "trader_future",
    role: "user",
    isActive: true,
    isPermanentAdmin: false,
    activationTimestamp: now + dayInSeconds * 7,
    expirationTimestamp: now + dayInSeconds * 37,
    allowedSymbols: ["XAUUSD"],
    allowedStrategies: [],
    detail: "Future Starting Account (Starts in 7 days)",
    permissions: ["read:signals"],
  },
];

export function getStoredAuthState(): StoredAuthState {
  const session = loadSession();
  if (session && session.user) {
    return {
      isLoggedIn: true,
      sessionToken: session.token,
      userAccount: session.user,
    };
  }
  return {
    isLoggedIn: false,
    sessionToken: null,
    userAccount: null,
  };
}

export function loadManagedAccounts(): UserAccount[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_ACCOUNTS);
    if (!raw) return INITIAL_MANAGED_ACCOUNTS;
    const parsed = JSON.parse(raw) as UserAccount[];
    if (Array.isArray(parsed) && parsed.length > 0) {
      const hasAdmin = parsed.some((u) => u.userId === "admin");
      return hasAdmin ? parsed : [PERMANENT_ADMIN_ACCOUNT, ...parsed];
    }
  } catch {
    // Fallback
  }
  return INITIAL_MANAGED_ACCOUNTS;
}

export function saveManagedAccounts(accounts: UserAccount[]): void {
  try {
    localStorage.setItem(STORAGE_KEY_ACCOUNTS, JSON.stringify(accounts));
  } catch {
    // Memory fallback
  }
}

export function loadSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_SESSION);
    if (!raw) return null;
    const session = JSON.parse(raw) as AuthSession;
    if (session && session.user) {
      const evalRes = evaluateAccountStatus(session.user);
      if (!evalRes.isValid) {
        clearSession();
        return null;
      }
      return session;
    }
  } catch {
    // Fallback
  }
  return null;
}

export function saveSession(session: AuthSession): void {
  try {
    localStorage.setItem(STORAGE_KEY_SESSION, JSON.stringify(session));
  } catch {
    // Memory fallback
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(STORAGE_KEY_SESSION);
  } catch {
    // Memory fallback
  }
}

export function createCustomerAccount(
  adminRequester: UserAccount,
  username: string,
  startDaysFromNow: number = 0,
  durationDays: number = 30,
  allowedSymbols: string[] = ["XAUUSD", "EURUSD"],
  existingAccounts: UserAccount[] = loadManagedAccounts()
): { success: boolean; accounts: UserAccount[]; message: string; newAccount?: UserAccount } {
  if (!adminRequester || (adminRequester.role !== "admin" && !adminRequester.isPermanentAdmin)) {
    return { success: false, accounts: existingAccounts, message: "Access denied: Admin privileges required." };
  }

  const cleanUser = username.trim().toLowerCase();
  if (!cleanUser) {
    return { success: false, accounts: existingAccounts, message: "Username cannot be empty." };
  }

  if (existingAccounts.some((u) => u.userId.toLowerCase() === cleanUser)) {
    return { success: false, accounts: existingAccounts, message: `User '${cleanUser}' already exists.` };
  }

  const currentTime = Math.floor(Date.now() / 1000);
  const activationTs = currentTime + startDaysFromNow * dayInSeconds;
  const expirationTs = activationTs + durationDays * dayInSeconds;

  const newAccount: UserAccount = {
    userId: cleanUser,
    role: "user",
    isActive: true,
    isPermanentAdmin: false,
    activationTimestamp: activationTs,
    expirationTimestamp: expirationTs,
    allowedSymbols,
    allowedStrategies: [],
    detail: `Customer Account created by admin ${adminRequester.userId}`,
    permissions: ["read:signals", "read:trade_setups"],
  };

  const updatedAccounts = [...existingAccounts, newAccount];
  saveManagedAccounts(updatedAccounts);
  return {
    success: true,
    accounts: updatedAccounts,
    message: `Account '${cleanUser}' successfully created. Expiration: ${new Date(expirationTs * 1000).toLocaleDateString()}`,
    newAccount,
  };
}

export function renewCustomerAccount(
  adminRequester: UserAccount,
  targetUserId: string,
  extendDays: number = 30,
  existingAccounts: UserAccount[] = loadManagedAccounts()
): { success: boolean; accounts: UserAccount[]; message: string } {
  if (!adminRequester || (adminRequester.role !== "admin" && !adminRequester.isPermanentAdmin)) {
    return { success: false, accounts: existingAccounts, message: "Access denied: Admin privileges required." };
  }

  const cleanTarget = targetUserId.trim().toLowerCase();
  const targetIndex = existingAccounts.findIndex((u) => u.userId.toLowerCase() === cleanTarget);
  if (targetIndex === -1) {
    return { success: false, accounts: existingAccounts, message: `User '${cleanTarget}' not found.` };
  }

  const target = existingAccounts[targetIndex];
  if (target.isPermanentAdmin || target.role === "admin") {
    return { success: true, accounts: existingAccounts, message: "Owner/Admin account is permanent and does not need renewal." };
  }

  const currentTime = Math.floor(Date.now() / 1000);
  const baseTs = (target.expirationTimestamp && target.expirationTimestamp > currentTime)
    ? target.expirationTimestamp
    : currentTime;
  const newExpirationTs = baseTs + extendDays * dayInSeconds;

  const updatedTarget: UserAccount = {
    ...target,
    isActive: true,
    expirationTimestamp: newExpirationTs,
    detail: `Renewed for ${extendDays} days by admin ${adminRequester.userId}`,
  };

  const updatedAccounts = [...existingAccounts];
  updatedAccounts[targetIndex] = updatedTarget;
  saveManagedAccounts(updatedAccounts);

  return {
    success: true,
    accounts: updatedAccounts,
    message: `Account '${target.userId}' renewed until ${new Date(newExpirationTs * 1000).toLocaleDateString()}.`,
  };
}

export function toggleAccountActiveStatus(
  adminRequester: UserAccount,
  targetUserId: string,
  existingAccounts: UserAccount[] = loadManagedAccounts()
): { success: boolean; accounts: UserAccount[]; message: string } {
  if (!adminRequester || (adminRequester.role !== "admin" && !adminRequester.isPermanentAdmin)) {
    return { success: false, accounts: existingAccounts, message: "Access denied: Admin privileges required." };
  }

  const cleanTarget = targetUserId.trim().toLowerCase();
  const targetIndex = existingAccounts.findIndex((u) => u.userId.toLowerCase() === cleanTarget);
  if (targetIndex === -1) {
    return { success: false, accounts: existingAccounts, message: `User '${cleanTarget}' not found.` };
  }

  const target = existingAccounts[targetIndex];
  if (target.isPermanentAdmin || target.role === "admin") {
    return { success: false, accounts: existingAccounts, message: "Permanent Owner/Admin account cannot be deactivated." };
  }

  const newStatus = !target.isActive;
  const updatedTarget: UserAccount = {
    ...target,
    isActive: newStatus,
    detail: `Active status updated to ${newStatus} by admin ${adminRequester.userId}`,
  };

  const updatedAccounts = [...existingAccounts];
  updatedAccounts[targetIndex] = updatedTarget;
  saveManagedAccounts(updatedAccounts);

  return {
    success: true,
    accounts: updatedAccounts,
    message: `Account '${target.userId}' active status set to ${newStatus}.`,
  };
}
