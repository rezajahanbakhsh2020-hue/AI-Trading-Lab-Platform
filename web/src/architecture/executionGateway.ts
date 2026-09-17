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
