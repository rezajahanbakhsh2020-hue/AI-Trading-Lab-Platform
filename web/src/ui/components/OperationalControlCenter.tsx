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
      <div className="card empty-card-view">
        <div className="card-body empty-state">
          <div className="empty-icon-ring" aria-hidden="true">🛡️</div>
          <h3>{t('auditControl.title')}</h3>
          <p className="hint mb-4">{t('status.unavailable')}</p>
          <p className="hint">{t('empty.noLogsMessage')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="operational-control-center space-v-6">
      {/* Header Banner */}
      <div className="card header-banner-card">
        <div className="card-body flex-header-row">
          <div>
            <h2 className="header-title">{t('auditControl.title')}</h2>
            <p className="hint header-subtitle">
              {t('auditControl.subtitle')}
            </p>
          </div>
          <div className="status-badge-group">
            <span className={`status ${status === 'available' ? 'ready' : 'warn'}`}>
              {status.toUpperCase()}
            </span>
            <span className="chip ready-chip">Security Boundary Active</span>
          </div>
        </div>
      </div>

      {/* Project 1 Integration Gateway Summary Card */}
      <div className="card project1-gateway-card">
        <div className="card-head flex-header-row">
          <div>
            <h4 className="header-title" style={{ margin: 0, fontSize: 16 }}>
              🔌 {t('project1Gateway.title')}
            </h4>
            <span className="hint" style={{ fontSize: 12 }}>
              {t('project1Gateway.subtitle')}
            </span>
          </div>
          <span className={`status ${snapshot.project1.connected ? 'ready' : 'disconnected'}`}>
            {snapshot.project1.connected ? t('project1Gateway.connected') : t('project1Gateway.disconnected')}
          </span>
        </div>
        <div className="card-body space-v-3">
          <div className="grid cols-4" style={{ gap: 12 }}>
            <div>
              <span className="hint block-label">{t('project1Gateway.contractVersion')}</span>
              <strong className="mono-val metric-md">1.0</strong>
            </div>
            <div>
              <span className="hint block-label">{t('signal.port')} / {t('signal.adapter')}</span>
              <span className="mono-val" style={{ fontSize: 12 }}>
                {snapshot.project1.port} ({snapshot.project1.adapterName})
              </span>
            </div>
            <div>
              <span className="hint block-label">{t('project1Gateway.supportedVersions')}</span>
              <span className="chip muted-chip">1.0, 1.0.0, v1.0</span>
            </div>
            <div>
              <span className="hint block-label">{t('status.ready')}</span>
              <span className="chip ready-chip">Audit & Auth Active</span>
            </div>
          </div>

          <div className="capabilities-badges flex-row" style={{ gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <span className="chip ready-chip">✓ {t('project1Gateway.guarantees.nonCalculation')}</span>
            <span className="chip ready-chip">✓ {t('project1Gateway.guarantees.sourceOfTruth')}</span>
            <span className="chip ready-chip">✓ {t('project1Gateway.guarantees.tenantIsolation')}</span>
            <span className="chip ready-chip">✓ {t('project1Gateway.guarantees.auditLogged')}</span>
          </div>

          <p className="hint notice-footer" style={{ margin: 0, marginTop: 8, fontStyle: 'italic' }}>
            {t('project1Gateway.nonCalculationNotice')}
          </p>
        </div>
      </div>

      {/* Execution Gateway & Reconciliation Summary Card */}
      {execMon && (
        <div className="card execution-reconciliation-card">
          <div className="card-head reconciliation-head">
            <h4 className="reconciliation-title text-amber">
              ⚡ {t("orderIntent.reconciliationTitle")}
            </h4>
            <span className="chip warn-chip">
              {t("orderIntent.monitoredIntents")}: {execMon.total_order_intents_monitored}
            </span>
          </div>
          <div className="card-body">
            <div className="grid cols-3 reconciliation-grid">
              <div>
                <span className="hint block-label">{t("orderIntent.executionAttemptsTitle")}:</span>
                <strong className="mono-val metric-md">{execMon.total_execution_attempts}</strong>
              </div>
              <div>
                <span className="hint block-label">{t("orderIntent.reconciliationStatus")}:</span>
                <strong className="mono-val metric-md text-amber">
                  {execMon.reconciliation_status_counts?.NOT_CONFIGURED || 0} {t("orderIntent.notConfiguredRec")}
                </strong>
              </div>
              <div>
                <span className="hint block-label">{t("orderIntent.allowsExecution")}:</span>
                <strong className="mono-val metric-md text-red">
                  {execMon.boundary?.allows_execution ? "TRUE" : t("orderIntent.disabledExecution")}
                </strong>
              </div>
            </div>
            <p className="hint reconciliation-notice">
              {t("orderIntent.reconciliationNotice")}
            </p>
          </div>
        </div>
      )}

      {/* Operational Incident Failures Card */}
      {snapshot.operationalFailures && (
        <div className="card operational-incidents-card">
          <div className="card-head flex-header-row">
            <h4 className="header-title" style={{ margin: 0, fontSize: 16 }}>
              🚨 {t("health.sections.operationalIncidents")}
            </h4>
            <span className="chip muted-chip">
              {snapshot.operationalFailures.length} Incidents Recorded
            </span>
          </div>
          <div className="card-body">
            {snapshot.operationalFailures.length === 0 ? (
              <p className="hint text-center py-4">{t("health.labels.noFailuresMessage")}</p>
            ) : (
              <div className="space-v-3">
                {snapshot.operationalFailures.map((fail) => (
                  <div key={fail.failure_id} className="card event-item-card">
                    <div className="card-head event-item-head">
                      <div className="event-badge-row">
                        <span className="status unavailable">{fail.severity}</span>
                        <strong className="event-type-name">{fail.error_type}</strong>
                        <span className="chip">{fail.component}</span>
                        <span className={`chip ${fail.retryable ? "ready-chip" : "muted-chip"}`}>
                          {fail.retryable ? t("health.labels.retryable") : t("health.labels.nonRetryable")}
                        </span>
                      </div>
                      <span className="hint">
                        {new Date(fail.timestamp * 1000).toLocaleString()}
                      </span>
                    </div>
                    <div className="card-body event-item-body">
                      <p className="event-action-line">
                        <strong>Message:</strong> {fail.message}
                      </p>
                      <p className="hint">
                        <strong>User:</strong> {fail.user_id} | <strong>Corr ID:</strong> <code>{fail.correlation_id}</code>
                      </p>
                      {fail.diagnostic_details && (
                        <div className="metadata-code-box">
                          <strong>Diagnostic Detail:</strong> {fail.diagnostic_details}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Operational Summary Grid */}
      {summary && (
        <div className="grid cols-4 summary-grid">
          <div className="card summary-card">
            <span className="hint block-label">{t('auditControl.totalEvents')}</span>
            <span className="metric-val">{summary.total_events}</span>
          </div>
          <div className="card summary-card">
            <span className="hint block-label">{t('auditControl.failedEvents')}</span>
            <span className={`metric-val ${summary.failed_events_count > 0 ? 'text-red' : ''}`}>
              {summary.failed_events_count}
            </span>
          </div>
          <div className="card summary-card">
            <span className="hint block-label">{t('auditControl.degradedEvents')}</span>
            <span className={`metric-val ${summary.degraded_events_count > 0 ? 'text-amber' : ''}`}>
              {summary.degraded_events_count}
            </span>
          </div>
          <div className="card summary-card">
            <span className="hint block-label">{t('auditControl.lastEventTime')}</span>
            <span className="metric-time">
              {summary.last_event_timestamp
                ? new Date(summary.last_event_timestamp * 1000).toLocaleTimeString()
                : 'N/A'}
            </span>
          </div>
        </div>
      )}

      {/* Filtering Toolbar */}
      <div className="card filter-toolbar-card">
        <div className="card-body">
          <h4 className="filter-title">{t('auditControl.filterTitle')}</h4>
          <div className="grid cols-4 filter-grid">
            <div>
              <label htmlFor="audit-cat-select" className="filter-label">{t('auditControl.category')}</label>
              <select
                id="audit-cat-select"
                className="select-filter"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value as any)}
                aria-label={t('auditControl.category')}
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
              <label htmlFor="audit-sev-select" className="filter-label">{t('auditControl.severity')}</label>
              <select
                id="audit-sev-select"
                className="select-filter"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value as any)}
                aria-label={t('auditControl.severity')}
              >
                <option value="ALL">{t('auditControl.allSeverities')}</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>

            <div>
              <label htmlFor="audit-life-select" className="filter-label">{t('auditControl.lifecycleState')}</label>
              <select
                id="audit-life-select"
                className="select-filter"
                value={lifecycleFilter}
                onChange={(e) => setLifecycleFilter(e.target.value as any)}
                aria-label={t('auditControl.lifecycleState')}
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
              <label htmlFor="audit-search-input" className="filter-label">Search</label>
              <input
                id="audit-search-input"
                type="text"
                className="input-search"
                placeholder={t('auditControl.searchPlaceholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                aria-label={t('auditControl.searchPlaceholder')}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Audit Log Events List */}
      <div className="card event-list-card">
        <div className="card-head flex-header-row">
          <h3>{t('auditControl.eventsListTitle')}</h3>
          <span className="hint">{filteredEvents.length} events displayed</span>
        </div>

        <div className="card-body">
          {filteredEvents.length === 0 ? (
            <p className="hint text-center py-6">{t('auditControl.noEvents')}</p>
          ) : (
            <div className="space-v-3">
              {filteredEvents.map((event) => {
                const sevClass =
                  event.severity === 'CRITICAL' || event.severity === 'ERROR'
                    ? 'unavailable'
                    : event.severity === 'WARNING'
                    ? 'warn'
                    : 'ready';

                return (
                  <div key={event.event_id} className="card event-item-card">
                    <div className="card-head event-item-head">
                      <div className="event-badge-row">
                        <span className={`status ${sevClass}`}>{event.severity}</span>
                        <strong className="event-type-name">{event.event_type}</strong>
                        <span className="chip">{event.category}</span>
                        <span className="chip muted-chip">
                          {event.lifecycle_state}
                        </span>
                      </div>
                      <span className="hint">
                        {new Date(event.timestamp * 1000).toLocaleString()}
                      </span>
                    </div>

                    <div className="card-body event-item-body">
                      <p className="event-action-line">
                        <strong>Action:</strong> {event.action} | <strong>Outcome:</strong>{' '}
                        <span className={event.outcome === 'SUCCESS' ? 'text-green' : 'text-red'}>
                          {event.outcome}
                        </span>
                      </p>
                      <p className="hint">
                        <strong>User:</strong> {event.user_id}{' '}
                        {event.correlation_id ? `| Corr ID: ${event.correlation_id}` : ''}
                      </p>
                      {event.details && <p className="event-details-text">{event.details}</p>}

                      {event.metadata && Object.keys(event.metadata).length > 0 && (
                        <div className="metadata-code-box">
                          <strong>Metadata:</strong> {JSON.stringify(event.metadata)}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <p className="hint notice-footer">{t('auditControl.sanitizedNotice')}</p>
        </div>
      </div>
    </div>
  );
}
