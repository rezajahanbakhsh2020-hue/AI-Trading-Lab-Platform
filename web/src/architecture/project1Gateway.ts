export interface Project1TrailingStopConfigPayload {
  distance: number;
  activation_price?: number | null;
  is_active: boolean;
  trailing_stop_loss?: number | null;
}

export interface Project1SignalIngestPayload {
  integration_id: string;
  signal_id: string;
  symbol: string;
  signal_type: "buy" | "sell" | "hold" | "no-signal";
  timestamp: number;
  source_id?: string;
  contract_version?: string;
  command_type?: string;
  timeframe?: string | null;
  strategy_name?: string | null;
  entry_price?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  take_profit_3?: number | null;
  trailing_stop?: Project1TrailingStopConfigPayload | null;
  confidence?: number | null;
  user_id?: string | null;
  tenant_id?: string | null;
  correlation_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface Project1IntegrationRecordPayload {
  integration_id: string;
  source_id?: string;
  contract_version: string;
  command_type?: string;
  signal_id: string;
  symbol?: string;
  signal_type?: string;
  lifecycle_state?: string;
  timestamp: number;
  timeframe?: string | null;
  strategy_name?: string | null;
  entry_price?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  take_profit_3?: number | null;
  trailing_stop?: Project1TrailingStopConfigPayload | null;
  confidence?: number | null;
  user_id?: string | null;
  tenant_id?: string | null;
  correlation_id?: string | null;
  created_at?: number;
  updated_at?: number;
}

export interface Project1GatewayCapabilitiesPayload {
  gateway_name: string;
  supported_contract_versions: readonly string[];
  current_contract_version: string;
  allowed_command_types: readonly string[];
  allowed_signal_types: readonly string[];
  allowed_lifecycle_states: readonly string[];
  guarantees: {
    non_calculation: boolean;
    project1_source_of_truth: boolean;
    server_side_authorization: boolean;
    tenant_isolation: boolean;
    audit_logged: boolean;
    secret_sanitized: boolean;
  };
}

export interface Project1GatewayMonitoringSummary {
  connected: boolean;
  contractVersion: string;
  supportedVersions: readonly string[];
  ingestedRecordsCount: number;
  lastCommunicatedAt: string | null;
  capabilities: Project1GatewayCapabilitiesPayload | null;
  recentRecords: readonly Project1IntegrationRecordPayload[];
}

export async function fetchProject1Capabilities(token?: string): Promise<{
  success: boolean;
  capabilities?: Project1GatewayCapabilitiesPayload;
  message?: string;
}> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const resp = await fetch("/api/v1/integration/project1/capabilities", { headers });
    if (!resp.ok) {
      return { success: false, message: `Server error ${resp.status}` };
    }
    const data = await resp.json();
    return { success: true, capabilities: data.capabilities };
  } catch (err) {
    return { success: false, message: (err as Error).message };
  }
}

export async function ingestProject1Signal(
  token: string,
  payload: Project1SignalIngestPayload
): Promise<{
  success: boolean;
  status?: string;
  error_code?: string;
  message?: string;
  record?: Project1IntegrationRecordPayload;
  correlation_id?: string;
}> {
  try {
    const resp = await fetch("/api/v1/integration/project1/ingest", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    return data;
  } catch (err) {
    return { success: false, error_code: "NETWORK_ERROR", message: (err as Error).message };
  }
}

export async function fetchProject1Records(
  token: string,
  symbol?: string,
  lifecycleState?: string
): Promise<{
  success: boolean;
  records?: Project1IntegrationRecordPayload[];
  count?: number;
  message?: string;
}> {
  try {
    const params = new URLSearchParams();
    if (symbol) params.set("symbol", symbol);
    if (lifecycleState) params.set("lifecycle_state", lifecycleState);

    const url = `/api/v1/integration/project1/records?${params.toString()}`;
    const resp = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!resp.ok) {
      return { success: false, message: `HTTP error ${resp.status}`, records: [] };
    }
    const data = await resp.json();
    return { success: true, records: data.records, count: data.count };
  } catch (err) {
    return { success: false, message: (err as Error).message, records: [] };
  }
}

export async function updateProject1Lifecycle(
  token: string,
  signalId: string,
  lifecycleState: string,
  reason?: string
): Promise<{
  success: boolean;
  signal_id?: string;
  lifecycle_state?: string;
  message?: string;
  correlation_id?: string;
}> {
  try {
    const resp = await fetch("/api/v1/integration/project1/lifecycle", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ signal_id: signalId, lifecycle_state: lifecycleState, reason }),
    });
    const data = await resp.json();
    return data;
  } catch (err) {
    return { success: false, message: (err as Error).message };
  }
}

/**
 * Test-only fixture helper. Strictly forbidden from entering production runtime paths.
 */
export function getTestOnlySampleProject1GatewaySummary(): Project1GatewayMonitoringSummary {
  if (process.env.NODE_ENV === "production") {
    throw new Error("TEST-ONLY FIXTURE: getTestOnlySampleProject1GatewaySummary cannot be called in production.");
  }
  return {
    connected: false,
    contractVersion: "1.0",
    supportedVersions: ["1.0", "1.0.0", "v1.0"],
    ingestedRecordsCount: 0,
    lastCommunicatedAt: null,
    capabilities: {
      gateway_name: "Project1IntegrationGateway",
      supported_contract_versions: ["1.0", "1.0.0", "v1.0"],
      current_contract_version: "1.0",
      allowed_command_types: ["EMIT_SIGNAL", "UPDATE_LIFECYCLE", "UPDATE_TRAILING_STOP", "HEARTBEAT"],
      allowed_signal_types: ["buy", "sell", "hold", "no-signal"],
      allowed_lifecycle_states: ["STAGED", "ACTIVE", "UPDATED", "CANCELLED", "EXPIRED", "REJECTED", "EXECUTED"],
      guarantees: {
        non_calculation: true,
        project1_source_of_truth: true,
        server_side_authorization: true,
        tenant_isolation: true,
        audit_logged: true,
        secret_sanitized: true,
      },
    },
    recentRecords: [],
  };
}

/** @deprecated Use getTestOnlySampleProject1GatewaySummary for isolated unit tests. */
export const getSampleProject1GatewaySummary = getTestOnlySampleProject1GatewaySummary;
