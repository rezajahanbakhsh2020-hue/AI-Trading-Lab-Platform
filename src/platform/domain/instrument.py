"""Instrument domain model.

Immutable identity for a tradable market instrument. Catalog/search layers
may use this later; presentation must not live here.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


VALID_ASSET_CLASSES = (
    "forex",
    "crypto",
    "commodity",
    "metal",
    "index",
    "stock",
    "unknown",
)


@dataclass(frozen=True)
class Instrument:
    """Immutable instrument identity."""

    symbol: str
    display_name: Optional[str] = None
    asset_class: str = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            raise ValueError("symbol must be a string")
        symbol_normalized = self.symbol.strip()
        if symbol_normalized == "":
            raise ValueError("symbol must not be empty or whitespace")
        object.__setattr__(self, "symbol", symbol_normalized)

        if self.display_name is not None:
            if not isinstance(self.display_name, str):
                raise ValueError("display_name must be a string if provided")
            display = self.display_name.strip()
            if display == "":
                raise ValueError("display_name must not be empty or whitespace")
            object.__setattr__(self, "display_name", display)

        if not isinstance(self.asset_class, str):
            raise ValueError("asset_class must be a string")
        asset_normalized = self.asset_class.strip().lower()
        if asset_normalized not in VALID_ASSET_CLASSES:
            raise ValueError(
                "asset_class must be one of: " + ", ".join(VALID_ASSET_CLASSES)
            )
        object.__setattr__(self, "asset_class", asset_normalized)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "display_name": self.display_name,
            "asset_class": self.asset_class,
        }
