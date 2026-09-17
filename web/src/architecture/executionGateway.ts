/**
 * Execution Gateway Boundary domain contracts and types for Project 2.
 * Represents the clean boundary where an authorized OrderIntent can be submitted to
 * external execution adapters.
 * DOES NOT represent routed, filled, or broker-executed orders.
 */

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
