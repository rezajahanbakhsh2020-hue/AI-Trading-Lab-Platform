"""Live monitoring / data-freshness application service.

Composes the explicit provider operation layer (ProviderOperations) with
an optional LabArtifactService and reports how current the selected market
context realmente is, measured against a single injected reference instant.

No wall-clock is used inside the service: the reference instant is injected so
monitoring stays deterministic and testable,and no timestamp is ever guessed
or fabricated..

Rules:
- construction and validation perform no I/O and no connect
- nothing is fetched unless an explicit method is called
- provider/source errors propagate unchanged to the caller
- ``None`` from any contract means genuinely unavailable, never fabricated
- ages are computed only from real timestamps the provider reported; if a
  timestamp cannot be interpreted (bad string, non-numeric,, mixed semantics,
  the age stays ``None`` (unknown age,, not zero, not invented)
- freshness statuses use only the ages the service actually computed::
  "fresh"/"stale" when at least one age is known (oldest age wins),
  "unknown" when no age could be computed,, and "unavailable" only when
  the quote explicitly reports an ``Availability(status="unavailable")``
- reference instant follows the existing domain ``Availability.age_seconds``
  convention (float seconds since epoch,, non-negative-age-able
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union
import time
from datetime import datetime, timezone
import numbers
import math

from src.platform.domain.freshness import DataFreshness
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.services.provider_operations import ProviderOperations

FRESH = "fresh"
STALE = "stale"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

_MAX_AGE_DEFAULT = 60.0


@dataclass(frozen=True)
class DataFreshnessSnapshot:
    """Combined market+quote freshness snapshot carrying both provider ids."""

    symbol: str
    timeframe: str
    market_data_provider_id: str
    quote_provider_id: Optional[str] = None
    freshness: Optional[DataFreshness] = None
    candle_count: int = 0
    quote_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "market_data_provider_id": self.market_data_provider_id,
            "quote_provider_id": self.quote_provider_id,
            "freshness": None if self.freshness is None else self.freshness.to_dict(),
            "candle_count": self.candle_count,
            "quote_status": self.quote_status,
        }


class ProviderMonitor:
    """Application service computing market-data freshness for one context.



    The caller owns provider/source lifecycle:this service never connects,
    closes,, retries,, falls back,, or polls. Every fetch is explicit through
    the injected operation layers. The reference instant (``reference``) is
    injected per call so tests and callers can fix ``now`` deterministically; whend
    omitted, each call samples a single clock promptly (``time.time()``) and
    uses that same instant for the whole snapshot, so no age can go negative..
    """

    def __init__(
        self,
        operations: ProviderOperations,
        lab: Optional[LabArtifactService] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if operations is None or not isinstance(operations, ProviderOperations):
            raise ValueError("operations must be a ProviderOperations")
        if lab is not None and not isinstance(lab, LabArtifactService):
            raise ValueError("lab must be a LabArtifactService when provided")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable when provided")
        self._operations = operations
        self._lab = lab
        self._clock = clock if clock is not None else time.time

    def monitor(
        self,
        symbol: str,
        timeframe: str,
        market_data_provider_id: str,
        candles_limit: int = 100,
        quote_provider_id: Optional[str] = None,
        max_age_seconds: float = _MAX_AGE_DEFAULT,
    reference: Optional[Union[int, float, str]] = None
    ) -> DataFreshnessSnapshot:
        """Compute a freshness snapshot for one explicitly requested context.


        Parameters:
        - symbol: instrument identifier (non-empty string)
        - timeframe: timeframe string (non-empty string)
        - market_data_provider_id: explicit market-data provider id (required)
        - candles_limit: maximum candles to fetch (default 100)
        - quote_provider_id: optional explicit quote provider id; when omitted,
          the snapshot has no quote and no quote age (None)
        - max_age_seconds: threshold separating "fresh" from"stale"
          (positive finite number, seconds; default 60.0)
        - reference: optional reference instant used for all ages (float seconds
          since epoch, or int, or ISO string); when omitted, a single sample
          of the injected clock is used for the whole snapshot

        Raises: validation errors, provider failures,, and lab source failures
          propagate unchanged..
        """
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)
        _validate_limit(candles_limit)
        _validate_positive_number(max_age_seconds, "max_age_seconds")

        ref = reference if reference is not None else self._clock()

        candles_result = self._operations.fetch_candles(
            provider_id=market_data_provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=candles_limit,
        )

        quote = None
        quote_status = None
        if quote_provider_id is not None:
            quote_result = self._operations.fetch_quote(
                provider_id=quote_provider_id,
                symbol=symbol,
            )
            quote = quote_result.quote
            if quote.availability is not None:
                quote_status = quote.availability.status

        freshness = self._build_freshness(
            symbol=symbol,
            timeframe=timeframe,
            ref=ref,
            candles=candles_result.candles,
            quote=quote,
            max_age_seconds=max_age_seconds,
        )

        return DataFreshnessSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            market_data_provider_id=candles_result.provider_id,
            quote_provider_id=quote_provider_id,
            freshness=freshness,
            candle_count=len(candles_result.candles),
            quote_status=quote_status,
        )

    def _build_freshness(
        self,
        symbol: str,
        timeframe: str,
        ref: Union[int, float, str],
        candles: tuple,
        quote: Optional[Quote],
        max_age_seconds: float,
    ) -> DataFreshness:
        candle_timestamp = None
        candle_age = None
        if candles:
            candle = _latest_candle(candles)
            candle_timestamp = candle.timestamp
            candle_age = _age_seconds(candle_timestamp, ref)

        quote_timestamp = None
        quote_age = None
        unavailable = False
        if quote is not None:
            quote_timestamp = quote.timestamp
            quote_age = _age_seconds(quote_timestamp, ref)
            if (
                quote.availability is not None
                and quote.availability.status == UNAVAILABLE
            ):
                unavailable = True

        if unavailable:
            return DataFreshness(
                symbol=symbol,
                timeframe=timeframe,
                status=UNAVAILABLE,
                reference_timestamp=ref,
                candle_timestamp=candle_timestamp,
                quote_timestamp=quote_timestamp,
                candle_age_seconds=candle_age,
                quote_age_seconds=quote_age,
                reason="quote provider explicitly reports the market unavailable",
            )

        if candle_age is None and quote_age is None:
            return DataFreshness(
                symbol=symbol,
                timeframe=timeframe,
                status=UNKNOWN,
                reference_timestamp=ref,
                candle_timestamp=candle_timestamp,
                quote_timestamp=quote_timestamp,
                candle_age_seconds=candle_age,
                quote_age_seconds=quote_age,
            )

        oldest_age = None
        if candle_age is not None and (oldest_age is None or candle_age > oldest_age):
            oldest_age = candle_age
        if quote_age is not None and (oldest_age is None or quote_age > oldest_age):
            oldest_age = quote_age

        status = FRESH if oldest_age <= max_age_seconds else STALE

        return DataFreshness(
            symbol=symbol,
            timeframe=timeframe,
            status=status,
            reference_timestamp=ref,
            candle_timestamp=candle_timestamp,
            quote_timestamp=quote_timestamp,
            candle_age_seconds=candle_age,
            quote_age_seconds=quote_age,
        )


def _latest_candle(candles: tuple) -> Candle:
    """Return the candle with the newest timestamp, preserving reported order
    on ties.. Works on numeric and ISO-string timestamps alike; when timestamps
    are incomparable, the first candle in the list is used (no fabrication..
    """
    latest = candles[0]
    for candidate in candles[1:]:
        if _is_newer(candidate.timestamp, latest.timestamp):
            latest = candidate
    return latest


def _is_newer(candidate: Any, current: Any) -> bool:
    """True when ``candidate`` is strictly newer than ``current`` (mixed
    timestamp types counts as incomparable, not fakeable.."""
    if isinstance(candidate, (int, float)) and isinstance(current, (int, float)):
        return candidate > current
    if isinstance(candidate, str) and isinstance(current, str):
        try:
            return _parse_iso(candidate) > _parse_iso(current)
        except ValueError:
            return False
    return False


def _age_seconds(timestamp: Any, reference: Any) -> Optional[float]:
    """Compute age of ``timestamp`` against ``reference``;; ``None`` when either
    cannot be interpreted (unknown age, not invented.."""
    try:
        ts = _to_seconds(timestamp)
        ref = _to_seconds(reference)
    except (TypeError, ValueError, OverflowError):
        return None
    age = ref - ts
    if not math.isfinite(age) or age < 0:
        return None
    return float(age)


def _to_seconds(value: Any) -> Union[int, float]:
    """Normalize a timestamp to seconds since epoch (numeric passthrough,
    ISO string parsed; anything else raises.."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError("unsupported timestamp")
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("non-finite numeric timestamp")
        return value
    stripped = value.strip()
    if not stripped:
        raise ValueError("empty timestamp string")
    parsed = _parse_iso(stripped)
    return parsed.timestamp()


def _parse_iso(value: str) -> datetime:
    normalized = value
    if normalized.endswith("Z") or normalized.endswith("z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit <= 0:
        raise ValueError("limit must be greater than zero")


def _validate_positive_number(value: Any, field_name: str) -> None:
    if (
        not isinstance(value, numbers.Real)
        or isinstance(value, bool)
    ):
        raise ValueError(f"{field_name} must be a numeric real value")
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")