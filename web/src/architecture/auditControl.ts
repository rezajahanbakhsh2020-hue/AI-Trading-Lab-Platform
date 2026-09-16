import { HostSnapshot } from './hostView';

export type AuditCategory =
  | 'SIGNAL_INTAKE'
  | 'BACKTEST_ASSESSMENT'
  | 'STRATEGY_VALIDATION'
  | 'AUTONOMOUS_AUTHORIZATION'
  | 'NOTIFICATION_DISPATCH'
  | 'PROVIDER_HEALTH'
  | 'SECURITY_AUTHORIZATION'
  | 'OPERATIONAL_SYSTEM';

export type OperationalLifecycleState =
  | 'INITIATED'
  | 'PROCESSING'
  | 'VALIDATED'
  | 'AUTHORIZED'
  | 'DISPATCHED'
  | 'COMPLETED'
  | 'DEGRADED'
  | 'FAILED'
  | 'REJECTED';

export type AuditEventSeverity = 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export interface AuditEventPayload {
  event_id: string;
  timestamp: number;
  user_id: string;
  category: AuditCategory;
  event_type: string;
  lifecycle_state: OperationalLifecycleState;
  action: string;
  outcome: string;
  severity: AuditEventSeverity;
  resource_id?: string | null;
  correlation_id?: string | null;
  details?: string | null;
  metadata?: Record<string, unknown>;
}

export interface AuditControlSummaryPayload {
  total_events: number;
  events_by_category: Record<string, number>;
  events_by_severity: Record<string, number>;
  events_by_lifecycle: Record<string, number>;
  failed_events_count: number;
  degraded_events_count: number;
  last_event_timestamp?: number | null;
}

export interface AuditControlState {
  status: 'available' | 'unavailable' | 'empty' | 'loading';
  summary: AuditControlSummaryPayload | null;
  events: AuditEventPayload[];
}

export interface AuditFilterOptions {
  category?: AuditCategory | 'ALL';
  severity?: AuditEventSeverity | 'ALL';
  lifecycleState?: OperationalLifecycleState | 'ALL';
  searchTerm?: string;
}

/**
 * Extracts Audit Control Plane state safely from HostSnapshot.
 */
export function extractAuditControlState(snapshot: HostSnapshot | null | undefined): AuditControlState {
  if (!snapshot || !snapshot.auditControl) {
    return {
      status: 'unavailable',
      summary: null,
      events: [],
    };
  }

  const raw = snapshot.auditControl as {
    status?: string;
    summary?: AuditControlSummaryPayload | null;
    events?: AuditEventPayload[];
  };

  const status = raw.status === 'available' ? 'available' : 'unavailable';
  const summary = raw.summary || null;
  const events = Array.isArray(raw.events) ? raw.events : [];

  return {
    status: events.length === 0 && status === 'available' ? 'empty' : status,
    summary,
    events,
  };
}

/**
 * Filter audit events by category, severity, lifecycle state, or search text.
 */
export function filterAuditEvents(
  events: AuditEventPayload[],
  options: AuditFilterOptions
): AuditEventPayload[] {
  return events.filter((event) => {
    if (options.category && options.category !== 'ALL' && event.category !== options.category) {
      return false;
    }
    if (options.severity && options.severity !== 'ALL' && event.severity !== options.severity) {
      return false;
    }
    if (
      options.lifecycleState &&
      options.lifecycleState !== 'ALL' &&
      event.lifecycle_state !== options.lifecycleState
    ) {
      return false;
    }
    if (options.searchTerm && options.searchTerm.trim() !== '') {
      const term = options.searchTerm.toLowerCase().trim();
      const matchAction = event.action.toLowerCase().includes(term);
      const matchType = event.event_type.toLowerCase().includes(term);
      const matchDetails = event.details ? event.details.toLowerCase().includes(term) : false;
      const matchUser = event.user_id.toLowerCase().includes(term);
      const matchCorr = event.correlation_id ? event.correlation_id.toLowerCase().includes(term) : false;
      if (!matchAction && !matchType && !matchDetails && !matchUser && !matchCorr) {
        return false;
      }
    }
    return true;
  });
}
