import { describe, it, expect } from "vitest";
import {
  buildAllowedContextSummary,
  processAIGatewayRequest,
} from "./aiGateway";
import { createDisconnectedHostSnapshot } from "./hostView";

describe("AI Gateway Architecture Tests", () => {
  it("builds allowed context summary from snapshot", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const summary = buildAllowedContextSummary(snapshot, "explain_signal", "XAUUSD");

    expect(summary.contextId).toMatch(/^ctx_fe_/);
    expect(summary.userId).toBe("guest_user");
    expect(summary.capability).toBe("explain_signal");
    expect(summary.permittedSymbol).toBe("XAUUSD");
    expect(summary.isSanitized).toBe(true);
  });

  it("returns honest unavailable state when no provider is connected", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const response = processAIGatewayRequest(snapshot, {
      requestId: "req_001",
      userId: "guest_user",
      capability: "summarize_market",
      targetSymbol: "XAUUSD",
    });

    expect(response.status).toBe("UNAVAILABLE");
    expect(response.content).toBe("AI unavailable / provider not configured");
    expect(response.providerName).toBe("UnavailableAIProviderAdapter");
  });

  it("returns permission denied state when user lacks signal permissions", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h", {
      userId: "restricted_user",
      role: "guest",
      permissions: [],
      isAdmin: false,
    });

    const response = processAIGatewayRequest(snapshot, {
      requestId: "req_002",
      userId: "restricted_user",
      capability: "explain_signal",
      targetSymbol: "XAUUSD",
    });

    expect(response.status).toBe("PERMISSION_DENIED");
    expect(response.content).toContain("Access denied");
  });

  it("returns success response when provider is available", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const response = processAIGatewayRequest(
      snapshot,
      {
        requestId: "req_003",
        userId: "guest_user",
        capability: "explain_health",
      },
      {
        status: "available",
        name: "HttpAIProviderAdapter",
        responseText: "System health analysis complete.",
      }
    );

    expect(response.status).toBe("SUCCESS");
    expect(response.providerName).toBe("HttpAIProviderAdapter");
    expect(response.content).toBe("System health analysis complete.");
    expect(response.contextSummary?.hasPermittedHealth).toBe(true);
  });

  it("handles provider timeout or error states gracefully", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const response = processAIGatewayRequest(
      snapshot,
      {
        requestId: "req_004",
        userId: "guest_user",
        capability: "explain_signal",
      },
      {
        status: "error",
        name: "HttpAIProviderAdapter",
        simulatedErrorType: "timeout",
      }
    );

    expect(response.status).toBe("ERROR");
    expect(response.content).toBe("AI provider request timed out.");
    expect(response.errorMessage).toBe("Request timed out");
  });
});
