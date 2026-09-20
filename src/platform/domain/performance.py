"""Domain models for Strategy Performance Analytics and Risk Intelligence.

Immutable domain dataclasses representing strategy performance summary, drawdown profiles,
and risk analytics profiles.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class DrawdownProfile:
    """Drawdown profile for strategy risk assessment."""

    max_drawdown_pct: float = 0.0
    recovery_factor: float = 0.0
    risk_classification: str = "LOW"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_drawdown_pct": self.max_drawdown_pct,
            "recovery_factor": self.recovery_factor,
            "risk_classification": self.risk_classification,
        }


@dataclass(frozen=True)
class RiskAnalyticsProfile:
    """Risk analytics profile evaluating trade setup compliance and limits."""

    reward_to_risk_expectancy: float = 0.0
    max_drawdown: float = 0.0
    win_loss_ratio: float = 0.0
    risk_level: str = "medium"
    position_risk_pass: bool = True
    drawdown_limit_pass: bool = True
    risk_assessment_status: str = "compliant"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reward_to_risk_expectancy": self.reward_to_risk_expectancy,
            "max_drawdown": self.max_drawdown,
            "win_loss_ratio": self.win_loss_ratio,
            "risk_level": self.risk_level,
            "position_risk_pass": self.position_risk_pass,
            "drawdown_limit_pass": self.drawdown_limit_pass,
            "risk_assessment_status": self.risk_assessment_status,
        }


@dataclass(frozen=True)
class StrategyPerformanceSummary:
    """Aggregated strategy performance summary domain model."""

    strategy_name: str
    symbol: str = "XAUUSD"
    timeframe: str = "1h"
    status: str = "active"
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    net_profit: float = 0.0
    sharpe_ratio_estimate: Optional[float] = None
    drawdown_profile: Optional[DrawdownProfile] = None
    risk_profile: Optional[RiskAnalyticsProfile] = None
    walk_forward_efficiency: Optional[float] = None
    walk_forward_consistency: Optional[float] = None
    detail: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "status": self.status,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "net_profit": self.net_profit,
            "sharpe_ratio_estimate": self.sharpe_ratio_estimate,
            "drawdown_profile": self.drawdown_profile.to_dict() if self.drawdown_profile else None,
            "risk_profile": self.risk_profile.to_dict() if self.risk_profile else None,
            "walk_forward_efficiency": self.walk_forward_efficiency,
            "walk_forward_consistency": self.walk_forward_consistency,
            "detail": self.detail,
            "metadata": dict(self.metadata) if self.metadata else {},
        }
