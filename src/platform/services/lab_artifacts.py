"""Lab artifact application service.

Consumes the existing read-only LabArtifactSource port and exposes validated
domain objects for signals, trade setups, and stability assessments. It keeps
all infrastructure concerns (connect/fetch/close) behind the injected port and
never fabricates unavailable engine artifacts. Enforces security boundary checks
for protected lab resources.

Rules:
------------
- construction and validation perform no I/O and no connect
- fetching happens only when an explicit method is called
- ``None`` from the source means genuinely unavailable, never fabricated
- source dicts are validated before mapping into existing domain models
- validation failures raise ``ValueError`` deterministically
- source identity is preserved where the existing contracts support it
- no dependency on the original AI-Trading-Lab engine
"""

from typing import Optional

from src.platform.domain import Signal, Stability, TradeSetup
from src.platform.domain.security import Permission
from src.platform.domain.walk_forward import WalkForwardResult, WalkForwardWindow
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services.security import SecurityBoundaryService


class LabArtifactService:
    """Application service for reading Labrador artifacts via a LabArtifactSource.

    The caller owns the source lifecycle (connect/close). The service consumes
    the source strictly via its public port contract and never touches external
    infrastructure, concrete Lab implementations, or the engine repository.
    """

    def __init__(
        self,
        source: LabArtifactSource,
        security_service: Optional[SecurityBoundaryService] = None,
    ) -> None:
        if source is None or not isinstance(source, LabArtifactSource):
            raise ValueError("source must be a LabArtifactSource")
        if security_service is not None and not isinstance(
            security_service, SecurityBoundaryService
        ):
            raise ValueError("security_service must be a SecurityBoundaryService instance")
        self._source = source
        self._security_service = security_service or SecurityBoundaryService()

    def get_signal(
        self, symbol: str, timeframe: str, user: Optional[UserAuthorization] = None
    ) -> Optional[Signal]:
        """Return a validated Signal, or None when unavailable or unauthorized."""
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)

        if user is not None:
            allowed, _ = self._security_service.authorize(user, "signals", action="read")
            if not allowed:
                return None

        raw = self._source.fetch_signal(symbol=symbol, timeframe=timeframe)
        if raw is None:
            return None
        _require_dict(raw, "signal")
        return Signal(
            action=_require_field(raw, "action", "signal"),
            strategy_name=_require_field(raw, "strategy_name", "signal"),
            timestamp=_require_field(raw, "timestamp", "signal"),
            confidence=raw.get("confidence"),
        )

    def get_trade_setup(
        self, symbol: str, timeframe: str, user: Optional[UserAuthorization] = None
    ) -> Optional[TradeSetup]:
        """Return a validated TradeSetup, or None when unavailable or unauthorized."""
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)

        if user is not None:
            allowed, _ = self._security_service.authorize(
                user, "trade_setups", action="read"
            )
            if not allowed:
                return None

        raw = self._source.fetch_trade_setup(symbol=symbol, timeframe=timeframe)
        if raw is None:
            return None
        _require_dict(raw, "trade_setup")
        return TradeSetup(
            symbol=_require_field(raw, "symbol", "trade_setup"),
            entry_price=_require_field(raw, "entry_price", "trade_setup"),
            stop_loss=_require_field(raw, "stop_loss", "trade_setup"),
            take_profit_1=_require_field(raw, "take_profit_1", "trade_setup"),
            take_profit_2=_require_field(raw, "take_profit_2", "trade_setup"),
            take_profit_3=_require_field(raw, "take_profit_3", "trade_setup"),
            timestamp=_require_field(raw, "timestamp", "trade_setup"),
            direction=_require_field(raw, "direction", "trade_setup"),
        )

    def get_stability(
        self, strategy_name: str, user: Optional[UserAuthorization] = None
    ) -> Optional[Stability]:
        """Return a validated Stability, or None when unavailable or unauthorized."""
        _validate_strategy_name(strategy_name)

        if user is not None:
            allowed, _ = self._security_service.authorize(
                user, "best_strategies", action="read"
            )
            if not allowed:
                # Also check general signal permission for stability metrics if user is non-admin
                allowed_sig, _ = self._security_service.authorize(user, "signals", action="read")
                if not allowed_sig:
                    return None

        raw = self._source.fetch_stability(strategy_name=strategy_name)
        if raw is None:
            return None
        _require_dict(raw, "stability")

        # Sanitize metrics if present for non-admin users
        metrics = raw.get("metrics")
        if user is not None and not user.is_admin and isinstance(metrics, dict):
            metrics = self._security_service.filter_protected_payload(user, metrics)

        return Stability(
            score=_require_field(raw, "score", "stability"),
            risk_level=_require_field(raw, "risk_level", "stability"),
            metrics=metrics,
        )

    def get_walk_forward(
        self, strategy_name: str, symbol: str = "XAUUSD", timeframe: str = "1h", user: Optional[UserAuthorization] = None
    ) -> Optional[WalkForwardResult]:
        """Return a validated WalkForwardResult, or None when unavailable or unauthorized."""
        _validate_strategy_name(strategy_name)

        if user is not None:
            allowed, _ = self._security_service.authorize(user, "signals", action="read")
            if not allowed:
                return None

        raw = self._source.fetch_walk_forward(strategy_name=strategy_name)
        if raw is None:
            return None
        _require_dict(raw, "walk_forward")

        raw_windows = raw.get("windows", [])
        windows_list = []
        if isinstance(raw_windows, list):
            for rw in raw_windows:
                if isinstance(rw, dict):
                    windows_list.append(
                        WalkForwardWindow(
                            window_index=int(rw.get("window_index", 0)),
                            in_sample_trades=int(rw.get("in_sample_trades", 0)),
                            in_sample_win_rate=float(rw.get("in_sample_win_rate", 0.0)),
                            in_sample_profit_factor=float(rw.get("in_sample_profit_factor", 0.0)),
                            out_of_sample_trades=int(rw.get("out_of_sample_trades", 0)),
                            out_of_sample_win_rate=float(rw.get("out_of_sample_win_rate", 0.0)),
                            out_of_sample_profit_factor=float(rw.get("out_of_sample_profit_factor", 0.0)),
                            out_of_sample_max_drawdown=float(rw.get("out_of_sample_max_drawdown", 0.0)),
                            out_of_sample_net_profit=float(rw.get("out_of_sample_net_profit", 0.0)),
                            efficiency_ratio=float(rw.get("efficiency_ratio", 1.0)),
                        )
                    )

        stab = None
        stab_raw = raw.get("stability")
        if isinstance(stab_raw, dict):
            stab = Stability(
                score=float(stab_raw.get("score", 0.0)),
                risk_level=str(stab_raw.get("risk_level", "medium")),
                metrics=stab_raw.get("metrics"),
            )

        return WalkForwardResult(
            strategy_name=strategy_name,
            symbol=raw.get("symbol", symbol),
            timeframe=raw.get("timeframe", timeframe),
            windows=tuple(windows_list),
            overall_out_of_sample_win_rate=float(raw.get("overall_out_of_sample_win_rate", 0.0)),
            overall_out_of_sample_profit_factor=float(raw.get("overall_out_of_sample_profit_factor", 0.0)),
            overall_out_of_sample_max_drawdown=float(raw.get("overall_out_of_sample_max_drawdown", 0.0)),
            overall_out_of_sample_net_profit=float(raw.get("overall_out_of_sample_net_profit", 0.0)),
            stability=stab,
            detail=raw.get("detail"),
        )


def _validate_symbol(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise ValueError("symbol must be a string")
    if symbol.strip() == "":
        raise ValueError("symbol must not be empty or whitespace")


def _validate_timeframe(timeframe: str) -> None:
    if not isinstance(timeframe, str):
        raise ValueError("timeframe must be a string")
    if timeframe.strip() == "":
        raise ValueError("timeframe must not be empty or whitespace")


def _validate_strategy_name(strategy_name: str) -> None:
    if not isinstance(strategy_name, str):
        raise ValueError("strategy_name must be a string")
    if strategy_name.strip() == "":
        raise ValueError("strategy_name must not be empty or whitespace")


def _require_dict(raw, kind: str) -> None:
    if not isinstance(raw, dict):
        raise ValueError(f"{kind} source must return a dict, or None")


def _require_field(raw: dict, field: str, kind: str):
    if field not in raw:
        raise ValueError(f"{kind} record is missing required field '{field}'")
    return raw[field]
