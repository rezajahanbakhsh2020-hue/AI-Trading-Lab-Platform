/**
 * Execution Gateway Boundary domain contracts, types, and API helpers for Project 2.
 * Represents the clean boundary where an authorized OrderIntent can be submitted to
 * external execution adapters.
 * DOES NOT represent routed, filled, or broker-executed orders.
 */

import type { OrderIntentPayload, OrderLifecycleState } from "./orderIntent";

export type ExecutionBoundaryStatus =
  | "UNCONFIGURED"
  | "REJECTED_UNAUTHORIZED"
  | "REJECTED_UNAVAILABLE"
  | "REJECTED_INVALID_STATE"
  | "ACCEPTED_AT_BOUNDARY"
  | "FAILED_AT_BOUNDARY"
  | "SUBMITTED_TO_PORT";

export type ExecutionReconciliationStatus =
  | "NOT_CONFIGURED"
  | "NO_EXTERNAL_EVIDENCE"
  | "MATCHED"
  | "DISCREPANCY"
  | "UNAVAILABLE";

export interface ExecutionReconciliationRecordPayload {
  reconciliation_id: string;
  order_intent_id: string;
  user_id: string;
  status: ExecutionReconciliationStatus;
  reason: string;
  internal_state: string;
  external_evidence_found: boolean;
  external_state?: string | null;
  externally_executed: boolean;
  timestamp: number;
  details?: string | null;
}

export interface ExecutionGatewayStatusPayload {
  boundary_name: string;
  status: "configured" | "unconfigured";
  allows_execution: boolean;
  provider: {
    provider_id: string;
    configured: boolean;
    connected: boolean;
    allows_execution: boolean;
    message: string;
  };
  reconciliation_provider?: {
    provider_id: string;
    configured: boolean;
    connected: boolean;
    allows_reconciliation?: boolean;
    message: string;
  };
  notice: string;
}

export interface ExecutionMonitoringSummaryPayload {
  status: string;
  total_order_intents_monitored: number;
  total_execution_attempts: number;
  reconciliation_status_counts: Record<string, number>;
  boundary?: ExecutionGatewayStatusPayload;
  notice: string;
}

export interface ExecutionAttemptResultPayload {
  success: boolean;
  user_id: string;
  order_intent_id: string;
  status: ExecutionBoundaryStatus;
  reason: string;
  externally_executed: boolean;
  detail?: string | null;
  timestamp: number;
  provider_id: string;
  is_accepted?: boolean;
  is_rejected?: boolean;
  is_failed?: boolean;
}

/**
 * Utility function to verify whether an execution attempt claims external execution.
 * Always returns false in Project 2 host application.
 */
export function isExternallyExecuted(result?: ExecutionAttemptResultPayload | null): boolean {
  return result?.externally_executed === true;
}

export async function requestExecutionApi(
  orderIntentId: string,
  token?: string | null
): Promise<{
  success: boolean;
  status?: string;
  attempt?: ExecutionAttemptResultPayload;
  message?: string;
}> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const resp = await fetch("/api/v1/execution/request", {
      method: "POST",
      headers,
      body: JSON.stringify({ order_intent_id: orderIntentId }),
    });
    const data = await resp.json();
    return data;
  } catch (err) {
    return { success: false, message: (err as Error).message };
  }
}

export async function reconcileExecutionApi(
  orderIntentId: string,
  token?: string | null
): Promise<{
  success: boolean;
  message?: string;
  reconciliation?: ExecutionReconciliationRecordPayload;
}> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const resp = await fetch("/api/v1/execution/reconcile", {
      method: "POST",
      headers,
      body: JSON.stringify({ order_intent_id: orderIntentId }),
    });
    const data = await resp.json();
    return data;
  } catch (err) {
    return { success: false, message: (err as Error).message };
  }
}

export async function fetchExecutionBoundaryStatusApi(
  token?: string | null
): Promise<{
  success: boolean;
  boundary?: ExecutionGatewayStatusPayload;
  monitoring?: ExecutionMonitoringSummaryPayload;
  message?: string;
}> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const resp = await fetch("/api/v1/execution/boundary", { headers });
    if (!resp.ok) {
      return { success: false, message: `Server error ${resp.status}` };
    }
    const data = await resp.json();
    return data;
  } catch (err) {
    return { success: false, message: (err as Error).message };
  }
}

export async function fetchOrderIntentsApi(
  token?: string | null,
  symbol?: string,
  lifecycleState?: string
): Promise<{
  success: boolean;
  order_intents?: OrderIntentPayload[];
  count?: number;
  message?: string;
}> {
  try {
    const params = new URLSearchParams();
    if (symbol) params.set("symbol", symbol);
    if (lifecycleState) params.set("lifecycle_state", lifecycleState);

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const resp = await fetch(`/api/v1/execution/intents?${params.toString()}`, { headers });
    if (!resp.ok) {
      return { success: false, message: `Server error ${resp.status}`, order_intents: [] };
    }
    const data = await resp.json();
    return data;
  } catch (err) {
    return { success: false, message: (err as Error).message, order_intents: [] };
  }
}

export async function updateOrderIntentStateApi(
  orderIntentId: string,
  targetState: OrderLifecycleState,
  reason?: string,
  token?: string | null
): Promise<{
  success: boolean;
  message?: string;
  order_intent?: OrderIntentPayload;
}> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const resp = await fetch("/api/v1/execution/intent/update", {
      method: "POST",
      headers,
      body: JSON.stringify({
        order_intent_id: orderIntentId,
        lifecycle_state: targetState,
        reason,
      }),
    });
    const data = await resp.json();
    return data;
  } catch (err) {
    return { success: false, message: (err as Error).message };
  }
}
