"""Alert application service.

Derives user-facing market alerts honestly from a real monitored snapshot.
Alerts are never fabricated: every id and message detail is built only from
fields of the injected ProviderMonitor snapshot actually observed. Absent
observations yield no alert (None), never an invented one..
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union
import math
import numbers
import time

from src.platform.domain.alert import (
    MarketAlert,
    VALID_ALERT_KINDS,
    VALID_ALERT_SEVERITIES,
)
from src.platform.services.provider_monitoring import ProviderMonitor
from src.platform.services.provider_monitoring import DataFreshnessSnapshot


def _none_if_blank(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _format_age(age: Any) -> Optional[str]:
    if age is None:
        return None
    if isinstance(age, bool) or not isinstance(age, numbers.Real):
        return None
    if not math.isfinite(float(age)):
        return None
    return f"{float(age):.1f}s"


@dataclass(frozen=True)
class AlertEvaluation:
    """Result of evaluating one monitored context for alerts.



    alert: Optional[MarketAlert] = None
    snapshot: Optional[DataFreshnessSnapshot] = None
    """

    alert: Optional[MarketAlert] = None
    snapshot: Optional[DataFreshnessSnapshot] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert": None if self.alert is None else self.alert.to_dict(),
            "snapshot": None if self.snapshot is None else self.snapshot.to_dict(),
        }


class AlertService:
    """Derive user-facing alerts honestly from a real monitored snapshot.



    alerts build only from fields of the injected ProviderMonitor actually
    observed; a fresh or missing snapshot produces no alert unless the caller
    explicitly opts in the healthy informational variant (include_healthy)..
    Snapshot data that is unavailable or unknown never gets reclassified::
    the observed freshness status is mapped 1:1 onto alert kind/severity,,
    and no price,, level,, or reason is ever invented..
    """

    def __init__(
        self,
        monitor: ProviderMonitor,
        created_at: Optional[Union[int, float, str]] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if monitor is None or not isinstance(monitor, ProviderMonitor):
            raise ValueError("monitor must be a ProviderMonitor")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable when provided")
        self._monitor = monitor
        self._created_at = created_at
        self._clock = clock if clock is not None else time.time

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        market_data_provider_id: str,
        candles_limit: int = 100,
        quote_provider_id: Optional[str] = None,
        max_age_seconds: float = 60.0,
        reference: Optional[Union[int, float, str]] = None,
        include_healthy: bool = False,
    ) -> Optional[MarketAlert]:
        """Evaluate one monitored context and return a single alert (or None.



        The monitor snapshot is computed exactly once via the injected monitor
        (which may raise provider/validation errors unchanged;; those propagate).
        Alerts:
        - stale      -> warning  (id freshness-stale)
        - unavailable -> critical  (id freshness-unavailable)
        - unknown    -> info     (id freshness-unknown)
        - fresh      -> None     unless include_healthy (then info freshness-ok)
        """
        if isinstance(include_healthy, bool) is False:
            raise ValueError("include_healthy must be a bool")

        snapshot = self._monitor.monitor(
            symbol=symbol,
            timeframe=timeframe,
            market_data_provider_id=market_data_provider_id,
            candles_limit=candles_limit,
            quote_provider_id=quote_provider_id,
            max_age_seconds=max_age_seconds,
            reference=reference,
        )

        if snapshot.freshness is None:
            return None

        status = snapshot.freshness.status
        if status == "fresh" and not include_healthy:
            return None

        created_at = self._created_at if self._created_at is not None else self._clock()
        alert = self._build_alert(snapshot, status, created_at)
        return alert

    def _build_alert(
        self,
        snapshot: DataFreshnessSnapshot,
        status: str,
        created_at: Union[int, float, str],
    ) -> MarketAlert:
        severity, alert_id, subject = self._classify(status)
        details: Dict[str, Any] = {}
        details["market_data_provider_id"] = snapshot.market_data_provider_id
        if snapshot.quote_provider_id is not None:
            details["quote_provider_id"] = snapshot.quote_provider_id
        details["candle_count"] = snapshot.candle_count
        if snapshot.quote_status is not None:
            details["quote_status"] = snapshot.quote_status
        details["freshness"] = snapshot.freshness.to_dict()

        message = self._build_message(snapshot, status, subject)
        return MarketAlert(
            id=alert_id,
            kind="freshness",
            severity=severity,
            status="active",
            message=message,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            created_at=created_at,
            details=details,
        )

    def _classify(self, status: str):
        if status == "stale":
            return "warning", "freshness-stale", "Market data is stale"
        if status == "unavailable":
            return "critical", "freshness-unavailable", "Market data is unavailable"
        if status == "unknown":
            return "info", "freshness-unknown", "Market data freshness is unknown"
        return "info", "freshness-ok", "Market data is fresh"

    def _build_message(
        self,
        snapshot: DataFreshnessSnapshot,
        status: str,
        subject: str,
    ) -> str:
        freshness = snapshot.freshness
        parts = [subject, f"{snapshot.symbol}/{snapshot.timeframe}"]
        parts.append(f"from {snapshot.market_data_provider_id}")
        reason = _none_if_blank(freshness.reason)
        if reason is not None:
            parts.append(f"reason: {reason}")
        age = _format_age(freshness.candle_age_seconds)
        if age is None:
            age = _format_age(freshness.quote_age_seconds)
        if age is not None:
            parts.append(f"observed age {age}")
        return ", ".join(parts)
