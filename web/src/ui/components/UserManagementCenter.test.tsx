import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { UserManagementCenter } from "./UserManagementCenter";
import { I18nProvider } from "../../i18n";
import { PERMANENT_ADMIN_ACCOUNT, type UserAccount } from "../../architecture/userAuth";

describe("UserManagementCenter UI Component", () => {
  const adminAccount: UserAccount = PERMANENT_ADMIN_ACCOUNT;
  const customerAccount: UserAccount = {
    userId: "cust_test",
    role: "customer",
    isActive: true,
    isPermanentAdmin: false,
    activationTimestamp: 1000,
    expirationTimestamp: 2000000000,
    allowedSymbols: ["XAUUSD"],
    allowedStrategies: [],
  };

  it("renders access denied message for non-admin user", () => {
    render(
      <I18nProvider>
        <UserManagementCenter currentAccount={customerAccount} />
      </I18nProvider>
    );

    expect(screen.getByText(/Access Denied/i)).toBeDefined();
  });

  it("renders admin management table and controls for admin account", () => {
    render(
      <I18nProvider>
        <UserManagementCenter currentAccount={adminAccount} />
      </I18nProvider>
    );

    expect(screen.getByText(/User & Access Management Center/i)).toBeDefined();
    expect(screen.getByPlaceholderText(/Filter users by username/i)).toBeDefined();
  });

  it("opens create account modal and filters users", () => {
    render(
      <I18nProvider>
        <UserManagementCenter currentAccount={adminAccount} />
      </I18nProvider>
    );

    const createBtns = screen.getAllByText(/\+ Create Customer Account/i);
    expect(createBtns.length).toBeGreaterThan(0);
    fireEvent.click(createBtns[0]);

    expect(screen.getByText(/Create New Customer Account/i)).toBeDefined();
  });
});
