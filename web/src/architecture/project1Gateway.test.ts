import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  fetchProject1Capabilities,
  ingestProject1Signal,
  fetchProject1Records,
  updateProject1Lifecycle,
  getSampleProject1GatewaySummary,
} from "./project1Gateway";

describe("Project 1 Integration Gateway Architecture Suite", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns sample Project 1 Gateway summary with non-calculation guarantees", () => {
    const summary = getSampleProject1GatewaySummary();
    expect(summary.connected).toBe(true);
    expect(summary.contractVersion).toBe("1.0");
    expect(summary.supportedVersions).toContain("1.0");
    expect(summary.capabilities?.guarantees.non_calculation).toBe(true);
    expect(summary.recentRecords.length).toBeGreaterThan(0);
  });

  it("fetches Project 1 capabilities from API endpoint", async () => {
    const mockCaps = {
      gateway_name: "Project1IntegrationGateway",
      supported_contract_versions: ["1.0"],
      current_contract_version: "1.0",
      allowed_command_types: ["EMIT_SIGNAL"],
      allowed_signal_types: ["buy", "sell"],
      allowed_lifecycle_states: ["STAGED"],
      guarantees: {
        non_calculation: true,
        project1_source_of_truth: true,
        server_side_authorization: true,
        tenant_isolation: true,
        audit_logged: true,
        secret_sanitized: true,
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, capabilities: mockCaps }),
    } as Response);

    const res = await fetchProject1Capabilities("sample_token");
    expect(res.success).toBe(true);
    expect(res.capabilities?.current_contract_version).toBe("1.0");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/v1/integration/project1/capabilities",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer sample_token",
        }),
      })
    );
  });

  it("ingests Project 1 signal via API endpoint", async () => {
    const mockPayload = {
      integration_id: "int_001",
      signal_id: "sig_001",
      symbol: "XAUUSD",
      signal_type: "buy" as const,
      timestamp: 1700000000,
      contract_version: "1.0",
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        status: "INGESTED",
        correlation_id: "p1_corr_100",
      }),
    } as Response);

    const res = await ingestProject1Signal("sample_token", mockPayload);
    expect(res.success).toBe(true);
    expect(res.status).toBe("INGESTED");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/v1/integration/project1/ingest",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(mockPayload),
      })
    );
  });

  it("fetches user-isolated integration records from API endpoint", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        records: [
          {
            integration_id: "int_001",
            signal_id: "sig_001",
            symbol: "XAUUSD",
            timestamp: 1700000000,
            contract_version: "1.0",
          },
        ],
        count: 1,
      }),
    } as Response);

    const res = await fetchProject1Records("sample_token", "XAUUSD");
    expect(res.success).toBe(true);
    expect(res.records?.length).toBe(1);
    expect(res.records?.[0].signal_id).toBe("sig_001");
  });

  it("updates signal lifecycle state via API endpoint", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        signal_id: "sig_001",
        lifecycle_state: "CANCELLED",
      }),
    } as Response);

    const res = await updateProject1Lifecycle("sample_token", "sig_001", "CANCELLED", "User cancelled");
    expect(res.success).toBe(true);
    expect(res.lifecycle_state).toBe("CANCELLED");
  });
});
