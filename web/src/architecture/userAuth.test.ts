import { describe, expect, it } from "vitest";
import {
  evaluateAccountStatus,
  createCustomerAccount,
  renewCustomerAccount,
  toggleAccountActiveStatus,
  PERMANENT_ADMIN_ACCOUNT,
  type UserAccount,
} from "./userAuth";

describe("User Authentication & Time-Limited Customer Security Architecture", () => {
  const baseTime = 1700000000;
  const dayInSeconds = 86400;

  it("Owner/Admin is permanently valid and never expires", () => {
    const adminAccount: UserAccount = {
      ...PERMANENT_ADMIN_ACCOUNT,
      expirationTimestamp: baseTime - 1000,
      isActive: false,
    };

    const evalRes = evaluateAccountStatus(adminAccount, baseTime);
    expect(evalRes.isValid).toBe(true);
    expect(evalRes.status).toBe("PERMANENT_ADMIN");
  });

  it("Active customer with future expiration date is valid", () => {
    const activeCustomer: UserAccount = {
      userId: "cust_1",
      role: "user",
      isActive: true,
      isPermanentAdmin: false,
      activationTimestamp: baseTime - dayInSeconds,
      expirationTimestamp: baseTime + dayInSeconds * 30,
      allowedSymbols: ["XAUUSD"],
      allowedStrategies: [],
    };

    const evalRes = evaluateAccountStatus(activeCustomer, baseTime);
    expect(evalRes.isValid).toBe(true);
    expect(evalRes.status).toBe("ACTIVE");
  });

  it("Expired customer account is invalid with EXPIRED status", () => {
    const expiredCustomer: UserAccount = {
      userId: "cust_expired",
      role: "user",
      isActive: true,
      isPermanentAdmin: false,
      activationTimestamp: baseTime - dayInSeconds * 40,
      expirationTimestamp: baseTime - dayInSeconds * 2,
      allowedSymbols: ["XAUUSD"],
      allowedStrategies: [],
    };

    const evalRes = evaluateAccountStatus(expiredCustomer, baseTime);
    expect(evalRes.isValid).toBe(false);
    expect(evalRes.status).toBe("EXPIRED");
  });

  it("Future starting customer account is invalid with NOT_ACTIVE_YET status", () => {
    const futureCustomer: UserAccount = {
      userId: "cust_future",
      role: "user",
      isActive: true,
      isPermanentAdmin: false,
      activationTimestamp: baseTime + dayInSeconds * 7,
      expirationTimestamp: baseTime + dayInSeconds * 37,
      allowedSymbols: ["XAUUSD"],
      allowedStrategies: [],
    };

    const evalRes = evaluateAccountStatus(futureCustomer, baseTime);
    expect(evalRes.isValid).toBe(false);
    expect(evalRes.status).toBe("NOT_ACTIVE_YET");
  });

  it("Deactivated customer account is invalid with INACTIVE status", () => {
    const inactiveCustomer: UserAccount = {
      userId: "cust_inactive",
      role: "user",
      isActive: false,
      isPermanentAdmin: false,
      activationTimestamp: baseTime - dayInSeconds,
      expirationTimestamp: baseTime + dayInSeconds * 30,
      allowedSymbols: ["XAUUSD"],
      allowedStrategies: [],
    };

    const evalRes = evaluateAccountStatus(inactiveCustomer, baseTime);
    expect(evalRes.isValid).toBe(false);
    expect(evalRes.status).toBe("INACTIVE");
  });

  it("Admin can create customer with activation and expiration dates", () => {
    const existing = [PERMANENT_ADMIN_ACCOUNT];
    const res = createCustomerAccount(
      PERMANENT_ADMIN_ACCOUNT,
      "new_client",
      0,
      30,
      ["XAUUSD"],
      existing
    );

    expect(res.success).toBe(true);
    expect(res.accounts.length).toBe(2);
    expect(res.newAccount?.userId).toBe("new_client");
    expect(res.newAccount?.expirationTimestamp).toBeGreaterThan(baseTime);
  });

  it("Non-admin user cannot create customer account (prevents privilege escalation)", () => {
    const normalUser: UserAccount = {
      userId: "normal_user",
      role: "user",
      isActive: true,
      isPermanentAdmin: false,
      activationTimestamp: null,
      expirationTimestamp: null,
      allowedSymbols: [],
      allowedStrategies: [],
    };

    const res = createCustomerAccount(normalUser, "hacker_client", 0, 30, ["XAUUSD"], [PERMANENT_ADMIN_ACCOUNT]);
    expect(res.success).toBe(false);
    expect(res.message).toContain("Admin privileges required");
  });

  it("Admin can renew/extend an expired customer account", () => {
    const expiredCustomer: UserAccount = {
      userId: "client_exp",
      role: "user",
      isActive: true,
      isPermanentAdmin: false,
      activationTimestamp: baseTime - dayInSeconds * 40,
      expirationTimestamp: baseTime - dayInSeconds * 2,
      allowedSymbols: ["XAUUSD"],
      allowedStrategies: [],
    };

    const accounts = [PERMANENT_ADMIN_ACCOUNT, expiredCustomer];
    const res = renewCustomerAccount(PERMANENT_ADMIN_ACCOUNT, "client_exp", 30, accounts);

    expect(res.success).toBe(true);
    const renewed = res.accounts.find((a) => a.userId === "client_exp");
    expect(renewed?.expirationTimestamp).toBeGreaterThan(baseTime);
    const status = evaluateAccountStatus(renewed!, baseTime);
    expect(status.isValid).toBe(true);
  });

  it("Admin can deactivate and reactivate customer account but cannot deactivate Owner/Admin", () => {
    const activeCust: UserAccount = {
      userId: "client_active",
      role: "user",
      isActive: true,
      isPermanentAdmin: false,
      activationTimestamp: baseTime - dayInSeconds,
      expirationTimestamp: baseTime + dayInSeconds * 30,
      allowedSymbols: [],
      allowedStrategies: [],
    };

    let accounts = [PERMANENT_ADMIN_ACCOUNT, activeCust];

    let res = toggleAccountActiveStatus(PERMANENT_ADMIN_ACCOUNT, "client_active", accounts);
    expect(res.success).toBe(true);
    expect(res.accounts.find((a) => a.userId === "client_active")?.isActive).toBe(false);

    let adminToggleRes = toggleAccountActiveStatus(PERMANENT_ADMIN_ACCOUNT, "admin", res.accounts);
    expect(adminToggleRes.success).toBe(false);
    expect(adminToggleRes.message).toContain("cannot be deactivated");
  });
});
