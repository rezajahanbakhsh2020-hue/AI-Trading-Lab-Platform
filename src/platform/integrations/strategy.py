"""Read-only integration port for external trading-strategy engines.

The original AI-Trading-Lab repository is an external research/engine source.
Strategy engines execute outside this platform. This port lets the platform
consume an external strategy honestly: the strategy receives real observed
market data (candles and an optional quote) and returns an optional raw
signal dict. Returning ``None`` means the strategy genuinely cannot decide or
has no signal for the context; it is never invented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote


class SignalStrategy(ABC):
    """External strategy engine port that emits raw signal records.



    Implementations receive only real observed market data (the candles the
    platform actually fetched, anda quote when the caller requested one). They
    MUST NOT fabricate signals: returning ``None`` (or omitting a decision) is
    the honest way to report "no signal/undecided" for the current context.

    Contract (summary):
    - ``generate`` MUST return a plain dict with at least: ``action``,
      ``strategy_name``, ``timestamp``; ``confidence`` is optional (a float
      between 0.0 and 1.0 inclusive).
    - ``None`` returned means genuinely no signal, never an error.

    - Implementations MUST NOT perform I/O inside the platform-facing contract
      beyond what their own explicit lifecycle exposes; aby lifecycle/connect
      remains the caller's responsibility externally..
    - ``describe`` MUST be I/O-free (matching provider port convention)..
"""

    @abstractmethod
    def generate(
        self,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
        quote: Optional[Quote] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return a raw signal dict, or None when the strategy has no signal."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return a small serializable description of the strategy engine."""
        raise NotImplementedError