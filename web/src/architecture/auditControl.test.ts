import { describe, expect, it } from 'vitest';
import {
  extractAuditControlState,
  filterAuditEvents,
  AuditEventPayload,
  AuditControlSummaryPayload,
} from './auditControl';
import { HostSnapshot } from './hostView';

describe('auditControl architecture', () => {
  const mockEvents: AuditEventPayload[] = [
    {
      event_id: '1',
      timestamp: 1000,
      user_id: 'admin_1',
      category: 'SIGNAL_INTAKE',
      event_type: 'SIGNAL_RECEIVED',
      lifecycle_state: 'VALIDATED',
      action: 'PROCESS_SIGNAL',
      outcome: 'SUCCESS',
      severity: 'INFO',
      resource_id: 'sig-1',
      correlation_id: 'corr-1',
      details: 'XAUUSD signal received',
    },
    {
      event_id: '2',
      timestamp: 2000,
      user_id: 'system',
      category: 'NOTIFICATION_DISPATCH',
      event_type: 'DISPATCH_FAILED',
      lifecycle_state: 'FAILED',
      action: 'SEND_TELEGRAM',
      outcome: 'FAILURE',
      severity: 'ERROR',
      resource_id: 'notif-1',
      correlation_id: 'corr-2',
      details: 'Telegram dispatch timeout',
    },
  ];

  const mockSummary: AuditControlSummaryPayload = {
    total_events: 2,
    events_by_category: { SIGNAL_INTAKE: 1, NOTIFICATION_DISPATCH: 1 },
    events_by_severity: { INFO: 1, ERROR: 1 },
    events_by_lifecycle: { VALIDATED: 1, FAILED: 1 },
    failed_events_count: 1,
    degraded_events_count: 0,
    last_event_timestamp: 2000,
  };

  it('extracts audit control state from snapshot correctly', () => {
    const snapshot: HostSnapshot = {
      generatedAt: '1000',
      platform: { name: 'AI Trading Lab Platform', role: 'Host', status: 'ready' },
      security: { userId: 'admin', role: 'admin', isAdmin: true, permissions: [], status: 'enforced', message: '' },
      project1: { connected: true, status: 'connected', port: 'Port', adapterName: 'Adapter', message: 'Ok' },
      market: { symbol: 'XAUUSD', timeframe: '1h', provider: null, quote: null, candles: [], status: 'unavailable', message: '', lastFetchedAt: null },
      strategy: { name: null, stability: null, status: 'unavailable', message: '' },
      signal: { action: null, timestamp: null, status: 'unavailable', message: '' },
      performance: { status: 'unavailable', message: '' },
      risk: { entry: null, stopLoss: null, takeProfits: [], status: 'unavailable', message: '' },
      monitoring: { freshness: null, health: null, status: 'unavailable', message: '' },
      providers: { marketData: 'unconnected', quote: 'unconnected', message: '' },
      activity: [],
      auditControl: {
        status: 'available',
        summary: mockSummary,
        events: mockEvents,
      },
    };

    const state = extractAuditControlState(snapshot);
    expect(state.status).toBe('available');
    expect(state.summary?.total_events).toBe(2);
    expect(state.events.length).toBe(2);
  });

  it('handles null snapshot gracefully', () => {
    const state = extractAuditControlState(null);
    expect(state.status).toBe('unavailable');
    expect(state.summary).toBeNull();
    expect(state.events).toEqual([]);
  });

  it('filters audit events by category, severity, and search term', () => {
    const filteredCat = filterAuditEvents(mockEvents, { category: 'SIGNAL_INTAKE' });
    expect(filteredCat.length).toBe(1);
    expect(filteredCat[0].event_id).toBe('1');

    const filteredSev = filterAuditEvents(mockEvents, { severity: 'ERROR' });
    expect(filteredSev.length).toBe(1);
    expect(filteredSev[0].event_id).toBe('2');

    const filteredSearch = filterAuditEvents(mockEvents, { searchTerm: 'Telegram' });
    expect(filteredSearch.length).toBe(1);
    expect(filteredSearch[0].event_id).toBe('2');
  });
});
