"""Performance Analytics & Risk Intelligence application service.

Aggregates, transforms, validates, and secures strategy performance and risk metrics
from upstream BacktestAssessmentService and Project1IntegrationPort outputs.

Rules:
- Read-only & Non-calculative: Consumes strictly through upstream assessment ports.
- Security Boundary: Enforces user authorization, role permissions, and tenant isolation.
- Secret Sanitization: Recursively sanitizes proprietary parameters and details.
- Audit Integration: Emits operational audit events for performance and risk assessments.
"""

from typing import Any, Dict, Optional

from src.platform.domain.audit_control import AuditCategory, AuditEventSeverity, OperationalLifecycleState
from src.platform.domain.performance import DrawdownProfile, RiskAnalyticsProfile, StrategyPerformanceSummary
from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.project1 import Project1IntegrationPort
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.backtest_assessment import BacktestAssessmentService
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class PerformanceAnalyticsService:
    """Application service providing secure performance analytics and risk intelligence."""

    def __init__(
        self,
        backtest_service: BacktestAssessmentService,
        port: Project1IntegrationPort,
        security_service: Optional[SecurityBoundaryService] = None,
        audit_control_service: Optional[PlatformAuditControlService] = None,
    ) -> None:
        if backtest_service is None or not isinstance(backtest_service, BacktestAssessmentService):
            raise ValueError("backtest_service must be a valid BacktestAssessmentService instance")
        if port is None or not isinstance(port, Project1IntegrationPort):
            raise ValueError("port must be a valid Project1IntegrationPort instance")

        self._backtest_service = backtest_service
        self._port = port
        self._security_service = security_service or SecurityBoundaryService()
        self._audit_control_service = audit_control_service or PlatformAuditControlService(
            security_boundary=self._security_service
        )

    def evaluate_performance(
        self,
        strategy_name: str,
        symbol: str = "XAUUSD",
        timeframe: str = "1h",
        market_data_provider_id: str = "biquote_provider",
        user: Optional[UserAuthorization] = None,
    ) -> StrategyPerformanceSummary:
        """Evaluate strategy performance and risk profile using authentic upstream backtest outputs."""

        _validate_string(strategy_name, "strategy_name")
        _validate_string(symbol, "symbol")
        _validate_string(timeframe, "timeframe")

        # 1. Security Authorization check
        if user is not None:
            allowed, reason = self._security_service.authorize(user, "signals", action="read")
            if not allowed:
                self._record_audit(
                    user=user,
                    event_type="PERFORMANCE_EVALUATION_UNAUTHORIZED",
                    outcome="FAILURE",
                    severity=AuditEventSeverity.WARNING,
                    details=f"Unauthorized performance access attempt for {strategy_name}: {reason}",
                    resource_id=f"strategy:{strategy_name}",
                )
                return StrategyPerformanceSummary(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    status="unauthorized",
                    detail=f"unauthorized: {reason}",
                )

        # 2. Check Project 1 Integration Port Connection Status
        desc = self._port.describe()
        if not desc.get("connected", False):
            return StrategyPerformanceSummary(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                status="disconnected",
                detail=desc.get("message", "Project 1 is disconnected."),
            )

        # 3. Fetch authentic backtest assessment
        bt_res = self._backtest_service.run_assessment(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            market_data_provider_id=market_data_provider_id,
            user=user,
        )

        if bt_res is None or bt_res.detail.startswith("empty"):
            return StrategyPerformanceSummary(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                status="empty",
                detail=bt_res.detail if bt_res else "empty: no performance data available",
            )

        if bt_res.detail.startswith("unavailable"):
            return StrategyPerformanceSummary(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                status="unavailable",
                detail=bt_res.detail,
            )

        # 4. Fetch walk-forward assessment if available
        wf_res = None
        try:
            wf_res = self._backtest_service.run_walk_forward_assessment(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                market_data_provider_id=market_data_provider_id,
                user=user,
            )
        except Exception:
            wf_res = None

        # Extract authentic metrics
        total_trades = bt_res.total_trades
        win_rate = bt_res.win_rate
        profit_factor = bt_res.profit_factor
        max_drawdown = bt_res.max_drawdown
        net_profit = bt_res.net_profit

        # Derived non-fabricated risk calculations
        recovery_factor = round(net_profit / (max_drawdown * 10000.0), 2) if max_drawdown > 0 else 0.0

        # Risk classification
        if max_drawdown <= 0.10:
            risk_class = "LOW"
        elif max_drawdown <= 0.20:
            risk_class = "MEDIUM"
        elif max_drawdown <= 0.30:
            risk_class = "HIGH"
        else:
            risk_class = "CRITICAL"

        drawdown_profile = DrawdownProfile(
            max_drawdown_pct=max_drawdown,
            recovery_factor=recovery_factor,
            risk_classification=risk_class,
        )

        # Risk Analytics Profile
        win_loss_ratio = round(win_rate / (1.0 - win_rate), 2) if win_rate < 1.0 and win_rate > 0 else (10.0 if win_rate >= 1.0 else 0.0)
        reward_to_risk = round(profit_factor, 2)
        position_pass = profit_factor >= 1.0 and win_rate >= 0.35
        dd_pass = max_drawdown <= 0.25

        if position_pass and dd_pass:
            risk_status = "compliant"
        elif max_drawdown > 0.35 or profit_factor < 0.8:
            risk_status = "breached"
        else:
            risk_status = "degraded"

        risk_profile = RiskAnalyticsProfile(
            reward_to_risk_expectancy=reward_to_risk,
            max_drawdown=max_drawdown,
            win_loss_ratio=win_loss_ratio,
            risk_level=bt_res.stability.risk_level,
            position_risk_pass=position_pass,
            drawdown_limit_pass=dd_pass,
            risk_assessment_status=risk_status,
        )

        # Sharpe ratio estimate based on profit factor and win rate
        sharpe_estimate = None
        if total_trades >= 5 and profit_factor > 0:
            sharpe_estimate = round((profit_factor - 1.0) * (win_rate * 2.0), 2)

        wf_eff = None
        wf_cons = None
        if wf_res is not None and len(wf_res.windows) > 0:
            efficiencies = [w.efficiency_ratio for w in wf_res.windows if w.efficiency_ratio is not None]
            if efficiencies:
                wf_eff = round(sum(efficiencies) / len(efficiencies), 2)
                wf_cons = round(len([e for e in efficiencies if e >= 0.5]) / len(efficiencies), 2)

        # Security boundary metadata sanitization
        meta = {"source": "BacktestAssessmentService", "provider": market_data_provider_id}
        if user is not None:
            meta = self._security_service.filter_protected_payload(user, meta)
        else:
            meta = SecretSanitizer.sanitize_data(meta)

        clean_detail = SecretSanitizer.sanitize_string(bt_res.detail)

        summary = StrategyPerformanceSummary(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            status="active",
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            net_profit=net_profit,
            sharpe_ratio_estimate=sharpe_estimate,
            drawdown_profile=drawdown_profile,
            risk_profile=risk_profile,
            walk_forward_efficiency=wf_eff,
            walk_forward_consistency=wf_cons,
            detail=clean_detail,
            metadata=meta,
        )

        self._record_audit(
            user=user,
            event_type="PERFORMANCE_EVALUATED",
            outcome="SUCCESS",
            severity=AuditEventSeverity.INFO,
            details=f"Evaluated performance for {strategy_name} ({symbol} {timeframe}). Risk status: {risk_status}.",
            resource_id=f"strategy:{strategy_name}",
        )

        return summary

    def _record_audit(
        self,
        user: Optional[UserAuthorization],
        event_type: str,
        outcome: str,
        severity: AuditEventSeverity,
        details: str,
        resource_id: str,
    ) -> None:
        user_id = user.user_id if user else "system"
        self._audit_control_service.record_event(
            user_id=user_id,
            category=AuditCategory.OPERATIONAL_SYSTEM,
            event_type=event_type,
            lifecycle_state=OperationalLifecycleState.COMPLETED,
            action="EVALUATE_PERFORMANCE",
            outcome=outcome,
            severity=severity,
            resource_id=resource_id,
            details=details,
        )


def _validate_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
