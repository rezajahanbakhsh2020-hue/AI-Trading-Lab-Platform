import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OperationalControlCenter } from './OperationalControlCenter';
import { createDisconnectedHostSnapshot } from '../../architecture/hostView';
import { I18nProvider } from '../../i18n';

describe('OperationalControlCenter', () => {
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
});
