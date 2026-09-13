"""Autonomous authorization application service (Part 15: Full Autonomous Authorization).

Evaluates whether a trade signal, provider selection, and trade readiness
satisfy all criteria for full autonomous execution authorization.

Rules:
- Strictly deterministic, pure application boundary (no I/O, no network calls).
- Performs no price, signal, confidence, or risk data fabrication.
- Validates trade signal tradability and readiness/stability gates.
- Optionally validates operational provider selection readiness.
- Optionally validates trade setup level sanity and minimum risk/reward ratio.
"""

import numbers
from typing import Optional, Union

from src.platform.domain.autonomous_authorization import (
    AUTHORIZATION_STATUS_AUTHORIZED,
    AUTHORIZATION_STATUS_REJECTED,
    AutonomousAuthorization,
)
from src.platform.domain.provider_selection import ProviderSelection
from src.platform.domain.trade_readiness import TradeReadiness
from src.platform.domain.trade_signal import TradeSignal

REASON_AUTHORIZED = "autonomous execution authorized"
REASON_SIGNAL_NOT_TRADABLE = "trade signal is not tradable"
REASON_PROVIDER_REQUIRED = "provider selection is required"
REASON_PROVIDER_NOT_SELECTED = "provider selection status is not SELECTED"
REASON_LEVELS_INSANE = "trade readiness levels are insane"
REASON_INSUFFICIENT_RR = "risk reward ratio is below required minimum"


class AutonomousAuthorizationService:
    """Application service for full autonomous execution authorization."""

    def authorize(
        self,
        trade_signal: TradeSignal,
        provider_selection: Optional[ProviderSelection] = None,
        trade_readiness: Optional[TradeReadiness] = None,
        timestamp: Optional[Union[int, float]] = None,
        min_risk_reward_to_tp1: Optional[float] = None,
        require_selected_provider: bool = False,
    ) -> AutonomousAuthorization:
        """Deterministically evaluate criteria for full autonomous execution authorization."""

        if not isinstance(trade_signal, TradeSignal):
            raise ValueError("trade_signal must be a TradeSignal instance")

        if provider_selection is not None and not isinstance(
            provider_selection, ProviderSelection
        ):
            raise ValueError("provider_selection must be a ProviderSelection instance if provided")

        if trade_readiness is not None and not isinstance(
            trade_readiness, TradeReadiness
        ):
            raise ValueError("trade_readiness must be a TradeReadiness instance if provided")

        if not isinstance(require_selected_provider, bool):
            raise ValueError("require_selected_provider must be a boolean")

        if timestamp is not None:
            if isinstance(timestamp, bool) or not isinstance(timestamp, numbers.Real):
                raise ValueError("timestamp must be a numeric real value if provided")
            eval_ts = float(timestamp)
            if eval_ts < 0:
                raise ValueError("timestamp must be non-negative")
        else:
            eval_ts = float(trade_signal.signal.timestamp)

        if min_risk_reward_to_tp1 is not None:
            if isinstance(min_risk_reward_to_tp1, bool) or not isinstance(
                min_risk_reward_to_tp1, numbers.Real
            ):
                raise ValueError("min_risk_reward_to_tp1 must be a numeric real value if provided")
            min_rr = float(min_risk_reward_to_tp1)
            if min_rr <= 0:
                raise ValueError("min_risk_reward_to_tp1 must be greater than zero")
        else:
            min_rr = None

        # 1. Trade signal tradability check
        if not trade_signal.tradable or trade_signal.signal.action not in ("buy", "sell"):
            reason = f"{REASON_SIGNAL_NOT_TRADABLE}: {trade_signal.reason}"
            return AutonomousAuthorization(
                status=AUTHORIZATION_STATUS_REJECTED,
                reason=reason,
                timestamp=eval_ts,
                trade_signal=trade_signal,
                provider_selection=provider_selection,
                trade_readiness=trade_readiness,
            )

        # 2. Provider selection check
        if require_selected_provider and provider_selection is None:
            return AutonomousAuthorization(
                status=AUTHORIZATION_STATUS_REJECTED,
                reason=REASON_PROVIDER_REQUIRED,
                timestamp=eval_ts,
                trade_signal=trade_signal,
                provider_selection=None,
                trade_readiness=trade_readiness,
            )

        if provider_selection is not None and not provider_selection.is_selected:
            reason = f"{REASON_PROVIDER_NOT_SELECTED}: {provider_selection.reason}"
            return AutonomousAuthorization(
                status=AUTHORIZATION_STATUS_REJECTED,
                reason=reason,
                timestamp=eval_ts,
                trade_signal=trade_signal,
                provider_selection=provider_selection,
                trade_readiness=trade_readiness,
            )

        # 3. Trade readiness level sanity check
        if trade_readiness is not None:
            if not trade_readiness.levels_are_sane:
                return AutonomousAuthorization(
                    status=AUTHORIZATION_STATUS_REJECTED,
                    reason=REASON_LEVELS_INSANE,
                    timestamp=eval_ts,
                    trade_signal=trade_signal,
                    provider_selection=provider_selection,
                    trade_readiness=trade_readiness,
                )

            if min_rr is not None:
                rr = trade_readiness.risk_reward_to_tp1
                if rr is None or rr < min_rr:
                    reason = (
                        f"{REASON_INSUFFICIENT_RR} ({rr} < {min_rr})"
                    )
                    return AutonomousAuthorization(
                        status=AUTHORIZATION_STATUS_REJECTED,
                        reason=reason,
                        timestamp=eval_ts,
                        trade_signal=trade_signal,
                        provider_selection=provider_selection,
                        trade_readiness=trade_readiness,
                    )

        # All gates passed -> AUTHORIZED
        return AutonomousAuthorization(
            status=AUTHORIZATION_STATUS_AUTHORIZED,
            reason=REASON_AUTHORIZED,
            timestamp=eval_ts,
            trade_signal=trade_signal,
            provider_selection=provider_selection,
            trade_readiness=trade_readiness,
        )
