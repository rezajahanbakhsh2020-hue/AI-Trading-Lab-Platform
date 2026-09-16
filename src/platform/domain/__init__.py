"""Platform domain package for market models.

This package contains simple, dependency-light domain models used across the
platform. Presentation/UI code must not live here.
"""

from .alert import MarketAlert
from .autonomous_authorization import (
    AUTHORIZATION_STATUS_AUTHORIZED,
    AUTHORIZATION_STATUS_REJECTED,
    VALID_AUTHORIZATION_STATUSES,
    AutonomousAuthorization,
)
from .availability import Availability
from .backtest import BacktestResult
from .freshness import DataFreshness
from .instrument import Instrument
from .market import Candle
from .market_overview import MarketOverview
from .presented_signal import PresentedSignal
from .provider_readiness import (
    PROVIDER_STATUS_NOT_READY,
    PROVIDER_STATUS_READY,
    VALID_PROVIDER_READINESS_STATUSES,
    ProviderReadiness,
)
from .provider_selection import (
    SELECTION_STATUS_NOT_AVAILABLE,
    SELECTION_STATUS_SELECTED,
    VALID_SELECTION_STATUSES,
    ProviderSelection,
)
from .quote import Quote
from .readiness import Readiness
from .security import (
    ADMIN_ONLY_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    Permission,
    SecurityEvent,
    UserRole,
)
from .signal import Signal
from .notification_delivery import (
    NOTIFICATION_DELIVERY_DELIVERED,
    NOTIFICATION_DELIVERY_DENIED,
    NOTIFICATION_DELIVERY_FAILED,
    VALID_NOTIFICATION_DELIVERY_STATUSES,
    NotificationDelivery,
)
from .signal_delivery import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_NOT_DELIVERED,
    VALID_DELIVERY_STATUSES,
    SignalDelivery,
)
from .stability import Stability
from .strategy_result import StrategyResult
from .trade_readiness import TradeReadiness
from .trade_setup import TradeSetup
from .trade_signal import TradeSignal
from .trading_workflow import (
    VALID_WORKFLOW_STATUSES,
    WORKFLOW_STATUS_DENIED,
    WORKFLOW_STATUS_EXECUTED,
    WORKFLOW_STATUS_NOT_READY,
    TradingWorkflowResult,
)
from .user_authorization import UserAuthorization
from .validated_strategy import (
    STRATEGY_STATUS_REJECTED,
    STRATEGY_STATUS_UNVALIDATED,
    STRATEGY_STATUS_VALIDATED,
    VALID_STRATEGY_STATUSES,
    ValidatedStrategyState,
)

__all__ = [
    "AUTHORIZATION_STATUS_AUTHORIZED",
    "AUTHORIZATION_STATUS_REJECTED",
    "VALID_AUTHORIZATION_STATUSES",
    "AutonomousAuthorization",
    "Availability",
    "BacktestResult",
    "MarketAlert",
    "Candle",
    "DataFreshness",
    "Instrument",
    "MarketOverview",
    "PresentedSignal",
    "PROVIDER_STATUS_NOT_READY",
    "PROVIDER_STATUS_READY",
    "VALID_PROVIDER_READINESS_STATUSES",
    "ProviderReadiness",
    "SELECTION_STATUS_NOT_AVAILABLE",
    "SELECTION_STATUS_SELECTED",
    "VALID_SELECTION_STATUSES",
    "ProviderSelection",
    "Quote",
    "Readiness",
    "SecurityEvent",
    "UserRole",
    "Permission",
    "DEFAULT_ROLE_PERMISSIONS",
    "ADMIN_ONLY_PERMISSIONS",
    "Signal",
    "NOTIFICATION_DELIVERY_DELIVERED",
    "NOTIFICATION_DELIVERY_DENIED",
    "NOTIFICATION_DELIVERY_FAILED",
    "VALID_NOTIFICATION_DELIVERY_STATUSES",
    "NotificationDelivery",
    "DELIVERY_STATUS_DELIVERED",
    "DELIVERY_STATUS_NOT_DELIVERED",
    "VALID_DELIVERY_STATUSES",
    "SignalDelivery",
    "Stability",
    "StrategyResult",
    "TradeReadiness",
    "TradeSetup",
    "TradeSignal",
    "VALID_WORKFLOW_STATUSES",
    "WORKFLOW_STATUS_DENIED",
    "WORKFLOW_STATUS_EXECUTED",
    "WORKFLOW_STATUS_NOT_READY",
    "TradingWorkflowResult",
    "UserAuthorization",
    "STRATEGY_STATUS_REJECTED",
    "STRATEGY_STATUS_UNVALIDATED",
    "STRATEGY_STATUS_VALIDATED",
    "VALID_STRATEGY_STATUSES",
    "ValidatedStrategyState",
]
