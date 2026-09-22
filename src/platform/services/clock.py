"""System Clock abstraction for application-wide authoritative UTC time and date evaluation."""

from datetime import datetime, timezone
import time


class SystemClock:
    """Authoritative application time and date clock."""

    def __init__(self, fixed_timestamp: float | None = None) -> None:
        self._fixed_timestamp = fixed_timestamp

    def get_current_timestamp(self) -> float:
        """Return the current authoritative Unix timestamp in seconds."""
        if self._fixed_timestamp is not None:
            return float(self._fixed_timestamp)
        return time.time()

    def get_current_datetime(self) -> datetime:
        """Return current authoritative timezone-aware UTC datetime."""
        return datetime.fromtimestamp(self.get_current_timestamp(), tz=timezone.utc)

    def get_current_date(self) -> str:
        """Return current authoritative application calendar date in YYYY-MM-DD (UTC)."""
        return self.get_current_datetime().strftime("%Y-%m-%d")

    def get_date_for_timestamp(self, ts: float) -> str:
        """Return YYYY-MM-DD (UTC) date string for a given Unix timestamp."""
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return ""


# Default singleton instance for convenience across platform services
default_clock = SystemClock()
