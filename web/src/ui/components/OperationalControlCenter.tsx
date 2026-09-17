import { useState } from 'react';
import type { HostSnapshot } from '../../architecture/hostView';
import {
  extractAuditControlState,
  filterAuditEvents,
  AuditCategory,
  AuditEventSeverity,
  OperationalLifecycleState,
} from '../../architecture/auditControl';
import { useI18n } from '../../i18n';

type OperationalControlCenterProps = {
  snapshot: HostSnapshot;
};

export function OperationalControlCenter({ snapshot }: OperationalControlCenterProps) {
  const { t } = useI18n();
  const auditState = extractAuditControlState(snapshot);
  const { summary, events, status } = auditState;
  const execMon = snapshot.executionMonitoring;

  const [categoryFilter, setCategoryFilter] = useState<AuditCategory | 'ALL'>('ALL');
  const [severityFilter, setSeverityFilter] = useState<AuditEventSeverity | 'ALL'>('ALL');
  const [lifecycleFilter, setLifecycleFilter] = useState<OperationalLifecycleState | 'ALL'>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const filteredEvents = filterAuditEvents(events, {
    category: categoryFilter,
    severity: severityFilter,
    lifecycleState: lifecycleFilter,
    searchTerm,
  });

  if (status === 'unavailable') {
    return (
      <div className="card text-center" style={{ padding: 32 }}>
        <h3>{t('auditControl.title')}</h3>
        <p className="hint mb-4">{t('status.unavailable')}</p>
        <p className="muted">{t('empty.noLogsMessage')}</p>
      </div>
    );
  }

  return (
    <div className="operational-control-center space-y-6">
      {/* Header Banner */}
      <div className="card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-xl font-bold">{t('auditControl.title')}</h2>
            <p className="hint" style={{ marginTop: 4 }}>
              {t('auditControl.subtitle')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`status ${status === 'available' ? 'ready' : 'warn'}`}>
              {status.toUpperCase()}
            </span>
            <span className="chip text-xs">Security Boundary Active</span>
          </div>
        </div>
      </div>

      {/* Execution Gateway & Reconciliation Summary Card */}
      {execMon && (
        <div className="card" style={{ padding: 16 }}>
          <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
            <h4 className="font-bold text-sm text-amber-300">
              ⚡ {t("orderIntent.reconciliationTitle")}
            </h4>
            <span className="chip text-xs bg-amber-900/30 text-amber-300 border border-amber-500/30">
              {t("orderIntent.monitoredIntents")}: {execMon.total_order_intents_monitored}
            </span>
          </div>
          <div className="grid cols-3 gap-3 text-xs">
            <div>
              <span className="hint block mb-1">{t("orderIntent.executionAttemptsTitle")}:</span>
              <strong className="text-base font-mono">{execMon.total_execution_attempts}</strong>
            </div>
            <div>
              <span className="hint block mb-1">{t("orderIntent.reconciliationStatus")}:</span>
              <strong className="text-base font-mono text-amber-400">
                {execMon.reconciliation_status_counts?.NOT_CONFIGURED || 0} {t("orderIntent.notConfiguredRec")}
              </strong>
            </div>
            <div>
              <span className="hint block mb-1">{t("orderIntent.allowsExecution")}:</span>
              <strong className="text-base font-mono text-rose-400">
                {execMon.boundary?.allows_execution ? "TRUE" : t("orderIntent.disabledExecution")}
              </strong>
            </div>
          </div>
          <p className="hint text-xs mt-2 italic text-amber-200/70">
            {t("orderIntent.reconciliationNotice")}
          </p>
        </div>
      )}

      {/* Operational Summary Grid */}
      {summary && (
        <div className="grid cols-4 gap-4">
          <div className="card flex flex-col justify-between" style={{ padding: 16, minHeight: 90 }}>
            <span className="hint block text-xs mb-2" style={{ display: "block" }}>{t('auditControl.totalEvents')}</span>
            <span className="text-2xl font-bold" style={{ fontSize: 22, fontWeight: 700 }}>{summary.total_events}</span>
          </div>
          <div className="card flex flex-col justify-between" style={{ padding: 16, minHeight: 90 }}>
            <span className="hint block text-xs mb-2" style={{ display: "block" }}>{t('auditControl.failedEvents')}</span>
            <span className={`text-2xl font-bold ${summary.failed_events_count > 0 ? 'text-danger' : ''}`} style={{ fontSize: 22, fontWeight: 700 }}>
              {summary.failed_events_count}
            </span>
          </div>
          <div className="card flex flex-col justify-between" style={{ padding: 16, minHeight: 90 }}>
            <span className="hint block text-xs mb-2" style={{ display: "block" }}>{t('auditControl.degradedEvents')}</span>
            <span className={`text-2xl font-bold ${summary.degraded_events_count > 0 ? 'text-warn' : ''}`} style={{ fontSize: 22, fontWeight: 700 }}>
              {summary.degraded_events_count}
            </span>
          </div>
          <div className="card flex flex-col justify-between" style={{ padding: 16, minHeight: 90 }}>
            <span className="hint block text-xs mb-2" style={{ display: "block" }}>{t('auditControl.lastEventTime')}</span>
            <span className="text-sm font-semibold" style={{ fontSize: 14, fontWeight: 600 }}>
              {summary.last_event_timestamp
                ? new Date(summary.last_event_timestamp * 1000).toLocaleTimeString()
                : 'N/A'}
            </span>
          </div>
        </div>
      )}

      {/* Filtering Toolbar */}
      <div className="card" style={{ padding: 16 }}>
        <h4 className="font-semibold text-sm mb-3">{t('auditControl.filterTitle')}</h4>
        <div className="grid cols-4 gap-3">
          <div>
            <label className="hint block text-xs mb-1">{t('auditControl.category')}</label>
            <select
              className="select"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value as any)}
              style={{ width: '100%', padding: '6px 8px' }}
            >
              <option value="ALL">{t('auditControl.allCategories')}</option>
              <option value="SIGNAL_INTAKE">SIGNAL_INTAKE</option>
              <option value="BACKTEST_ASSESSMENT">BACKTEST_ASSESSMENT</option>
              <option value="STRATEGY_VALIDATION">STRATEGY_VALIDATION</option>
              <option value="AUTONOMOUS_AUTHORIZATION">AUTONOMOUS_AUTHORIZATION</option>
              <option value="NOTIFICATION_DISPATCH">NOTIFICATION_DISPATCH</option>
              <option value="PROVIDER_HEALTH">PROVIDER_HEALTH</option>
              <option value="SECURITY_AUTHORIZATION">SECURITY_AUTHORIZATION</option>
              <option value="OPERATIONAL_SYSTEM">OPERATIONAL_SYSTEM</option>
            </select>
          </div>

          <div>
            <label className="hint block text-xs mb-1">{t('auditControl.severity')}</label>
            <select
              className="select"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as any)}
              style={{ width: '100%', padding: '6px 8px' }}
            >
              <option value="ALL">{t('auditControl.allSeverities')}</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>

          <div>
            <label className="hint block text-xs mb-1">{t('auditControl.lifecycleState')}</label>
            <select
              className="select"
              value={lifecycleFilter}
              onChange={(e) => setLifecycleFilter(e.target.value as any)}
              style={{ width: '100%', padding: '6px 8px' }}
            >
              <option value="ALL">{t('auditControl.allStates')}</option>
              <option value="INITIATED">INITIATED</option>
              <option value="PROCESSING">PROCESSING</option>
              <option value="VALIDATED">VALIDATED</option>
              <option value="AUTHORIZED">AUTHORIZED</option>
              <option value="DISPATCHED">DISPATCHED</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="DEGRADED">DEGRADED</option>
              <option value="FAILED">FAILED</option>
              <option value="REJECTED">REJECTED</option>
            </select>
          </div>

          <div>
            <label className="hint block text-xs mb-1">Search</label>
            <input
              type="text"
              placeholder={t('auditControl.searchPlaceholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: '100%', padding: '6px 8px' }}
            />
          </div>
        </div>
      </div>

      {/* Audit Log Events List */}
      <div className="card" style={{ padding: 16 }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-base">{t('auditControl.eventsListTitle')}</h3>
          <span className="hint text-xs">{filteredEvents.length} events displayed</span>
        </div>

        {filteredEvents.length === 0 ? (
          <p className="hint text-center py-6">{t('auditControl.noEvents')}</p>
        ) : (
          <div className="space-y-3">
            {filteredEvents.map((event) => {
              const sevClass =
                event.severity === 'CRITICAL' || event.severity === 'ERROR'
                  ? 'unavailable'
                  : event.severity === 'WARNING'
                  ? 'warn'
                  : 'ready';

              return (
                <div key={event.event_id} className="card" style={{ padding: 12, background: 'rgba(255,255,255,0.01)' }}>
                  <div className="card-head mb-2 flex items-center justify-between flex-wrap gap-2" style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <div className="flex items-center gap-2" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span className={`status ${sevClass}`} style={{ marginRight: 6 }}>{event.severity}</span>
                      <strong className="text-sm" style={{ marginLeft: 4 }}>{event.event_type}</strong>
                      <span className="chip text-xs">{event.category}</span>
                      <span className="chip text-xs" style={{ background: 'rgba(255,255,255,0.06)' }}>
                        {event.lifecycle_state}
                      </span>
                    </div>
                    <span className="hint text-xs">
                      {new Date(event.timestamp * 1000).toLocaleString()}
                    </span>
                  </div>

                  <div className="text-xs space-y-1 mb-2">
                    <p>
                      <strong>Action:</strong> {event.action} | <strong>Outcome:</strong>{' '}
                      <span className={event.outcome === 'SUCCESS' ? 'text-success' : 'text-danger'}>
                        {event.outcome}
                      </span>
                    </p>
                    <p className="muted">
                      <strong>User:</strong> {event.user_id}{' '}
                      {event.correlation_id ? `| Corr ID: ${event.correlation_id}` : ''}
                    </p>
                    {event.details && <p className="text-sm mt-1">{event.details}</p>}
                  </div>

                  {event.metadata && Object.keys(event.metadata).length > 0 && (
                    <div className="text-xs muted card" style={{ padding: 8, background: 'rgba(0,0,0,0.2)' }}>
                      <strong>Metadata:</strong> {JSON.stringify(event.metadata)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <p className="hint text-xs mt-4 italic text-center">{t('auditControl.sanitizedNotice')}</p>
      </div>
    </div>
  );
}
