import { describe, expect, it, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { OperationalControlCenter } from './OperationalControlCenter';
import { createDisconnectedHostSnapshot } from '../../architecture/hostView';
import { I18nProvider } from '../../i18n';

describe('OperationalControlCenter', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders operational control center with audit events from snapshot', () => {
    const snapshot = createDisconnectedHostSnapshot('XAUUSD', '1h');
    snapshot.auditControl = {
      status: 'available',
      summary: {
        total_events: 1,
        events_by_category: { OPERATIONAL_SYSTEM: 1 },
        events_by_severity: { INFO: 1 },
        events_by_lifecycle: { COMPLETED: 1 },
        failed_events_count: 0,
        degraded_events_count: 0,
        last_event_timestamp: 1000,
      },
      events: [
        {
          event_id: 'evt-100',
          timestamp: 1000,
          user_id: 'system',
          category: 'OPERATIONAL_SYSTEM',
          event_type: 'SYSTEM_INITIALIZED',
          lifecycle_state: 'COMPLETED',
          action: 'INITIALIZE_PLATFORM',
          outcome: 'SUCCESS',
          severity: 'INFO',
          details: 'Platform operational control plane initialized safely.',
        },
      ],
    };

    render(
      <I18nProvider>
        <OperationalControlCenter snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByText('Operational Control Plane & Audit Log')).toBeTruthy();
    expect(screen.getByText('SYSTEM_INITIALIZED')).toBeTruthy();
    expect(screen.getByText(/INITIALIZE_PLATFORM/)).toBeTruthy();
  });

  it('filters audit events by search term', () => {
    const snapshot = createDisconnectedHostSnapshot('XAUUSD', '1h');
    snapshot.auditControl = {
      status: 'available',
      summary: {
        total_events: 2,
        events_by_category: { OPERATIONAL_SYSTEM: 1, PROVIDER_HEALTH: 1 },
        events_by_severity: { INFO: 2 },
        events_by_lifecycle: { COMPLETED: 2 },
        failed_events_count: 0,
        degraded_events_count: 0,
        last_event_timestamp: 1000,
      },
      events: [
        {
          event_id: 'evt-100',
          timestamp: 1000,
          user_id: 'system',
          category: 'OPERATIONAL_SYSTEM',
          event_type: 'SYSTEM_INITIALIZED',
          lifecycle_state: 'COMPLETED',
          action: 'INITIALIZE_PLATFORM',
          outcome: 'SUCCESS',
          severity: 'INFO',
          details: 'Platform operational control plane initialized safely.',
        },
        {
          event_id: 'evt-101',
          timestamp: 1001,
          user_id: 'system',
          category: 'PROVIDER_HEALTH',
          event_type: 'PROVIDER_CHECK',
          lifecycle_state: 'COMPLETED',
          action: 'CHECK_READINESS',
          outcome: 'SUCCESS',
          severity: 'INFO',
          details: 'Lab artifact provider adapter verified and online.',
        },
      ],
    };

    render(
      <I18nProvider>
        <OperationalControlCenter snapshot={snapshot} />
      </I18nProvider>
    );

    const searchInput = screen.getByPlaceholderText(/Search by action/i);
    fireEvent.change(searchInput, { target: { value: 'CHECK_READINESS' } });

    expect(screen.queryByText('SYSTEM_INITIALIZED')).toBeNull();
    expect(screen.getByText('PROVIDER_CHECK')).toBeTruthy();
  });
});
