"""Application-layer provider registry and resolution.

This module is the controlled way for application services to obtain
provider instances. It sits above concrete providers and below API/UI.

It does not:
- perform network I/O
- call connect(), fetch_*, or close()
- invent a fallback provider
- use a process-wide singleton
- contain market-data, chart, strategy, or Lab logic

Provider lifecycle remains the caller's responsibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple, Type

from src.platform.providers.market_data import MarketDataProvider
from src.platform.providers.quote import QuoteProvider

CATEGORY_MARKET_DATA = "market_data"
CATEGORY_QUOTE = "quote"

DEFAULT_PROVIDER_CATEGORIES: Mapping[str, Type[Any]] = MappingProxyType(
    {
        CATEGORY_MARKET_DATA: MarketDataProvider,
        CATEGORY_QUOTE: QuoteProvider,
    }
)

_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ProviderRegistryError(Exception):
    """Application-level registry/resolution failure."""


class InvalidProviderRegistrationError(ProviderRegistryError):
    """Registration input is invalid."""


class DuplicateProviderError(ProviderRegistryError):
    """The same category/id pair is already registered."""


class UnknownProviderCategoryError(ProviderRegistryError):
    """Category is not supported by this registry instance."""


class UnknownProviderError(ProviderRegistryError):
    """No provider is registered for the requested category/id."""


@dataclass(frozen=True)
class ProviderRecord:
    """Immutable registry record. Does not activate the provider."""

    provider_id: str
    category: str
    provider: Any
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "category": self.category,
            "metadata": dict(self.metadata),
        }


def _normalize_token(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise InvalidProviderRegistrationError(f"{field_name} must be a string")
    normalized = value.strip().lower()
    if normalized == "":
        raise InvalidProviderRegistrationError(
            f"{field_name} must not be empty or whitespace"
        )
    if not _TOKEN_PATTERN.fullmatch(normalized):
        raise InvalidProviderRegistrationError(
            f"{field_name} must match {_TOKEN_PATTERN.pattern}"
        )
    return normalized


def _copy_metadata(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        raise InvalidProviderRegistrationError("metadata must be a dict")
    return dict(metadata)


class ProviderRegistry:
    """Explicit, injectable catalog of provider instances.

    Starts empty. Callers register providers. Duplicate registrations fail.
    Listing and lookup never connect, fetch, or close providers.
    """

    def __init__(
        self,
        extra_categories: Optional[Mapping[str, Type[Any]]] = None,
    ) -> None:
        categories: Dict[str, Type[Any]] = dict(DEFAULT_PROVIDER_CATEGORIES)
        if extra_categories is not None:
            if not isinstance(extra_categories, Mapping):
                raise InvalidProviderRegistrationError(
                    "extra_categories must be a mapping of category to type"
                )
            for raw_category, port_type in extra_categories.items():
                category = _normalize_token(raw_category, "category")
                if category in categories:
                    raise InvalidProviderRegistrationError(
                        f"cannot replace existing category {category!r}"
                    )
                if not isinstance(port_type, type):
                    raise InvalidProviderRegistrationError(
                        f"category {category!r} must map to a type"
                    )
                categories[category] = port_type
        self._categories = categories
        self._entries: Dict[Tuple[str, str], ProviderRecord] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def supported_categories(self) -> Tuple[str, ...]:
        return tuple(sorted(self._categories))

    def register(
        self,
        provider_id: str,
        category: str,
        provider: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderRecord:
        normalized_id = _normalize_token(provider_id, "provider_id")
        normalized_category = _normalize_token(category, "category")
        port_type = self._categories.get(normalized_category)
        if port_type is None:
            raise UnknownProviderCategoryError(
                f"unsupported provider category {normalized_category!r}"
            )
        if provider is None:
            raise InvalidProviderRegistrationError("provider is required")
        if not isinstance(provider, port_type):
            raise InvalidProviderRegistrationError(
                f"provider for category {normalized_category!r} must be "
                f"{port_type.__name__}"
            )

        key = (normalized_category, normalized_id)
        if key in self._entries:
            raise DuplicateProviderError(
                f"provider {normalized_id!r} is already registered in "
                f"category {normalized_category!r}"
            )

        snapshot = self._snapshot_metadata(provider, metadata)
        record = ProviderRecord(
            provider_id=normalized_id,
            category=normalized_category,
            provider=provider,
            metadata=snapshot,
        )
        self._entries[key] = record
        return record

    def get(self, category: str, provider_id: str) -> ProviderRecord:
        normalized_id = _normalize_token(provider_id, "provider_id")
        normalized_category = _normalize_token(category, "category")
        if normalized_category not in self._categories:
            raise UnknownProviderCategoryError(
                f"unsupported provider category {normalized_category!r}"
            )
        record = self._entries.get((normalized_category, normalized_id))
        if record is None:
            raise UnknownProviderError(
                f"unknown provider {normalized_id!r} in category "
                f"{normalized_category!r}"
            )
        return self._copy_record(record)

    def contains(self, category: str, provider_id: str) -> bool:
        """Return whether category/id is registered. Never falls back."""
        normalized_id = _normalize_token(provider_id, "provider_id")
        normalized_category = _normalize_token(category, "category")
        if normalized_category not in self._categories:
            raise UnknownProviderCategoryError(
                f"unsupported provider category {normalized_category!r}"
            )
        return (normalized_category, normalized_id) in self._entries

    def list_providers(self, category: Optional[str] = None) -> Tuple[ProviderRecord, ...]:
        if category is None:
            records = list(self._entries.values())
        else:
            normalized_category = _normalize_token(category, "category")
            if normalized_category not in self._categories:
                raise UnknownProviderCategoryError(
                    f"unsupported provider category {normalized_category!r}"
                )
            records = [
                record
                for record in self._entries.values()
                if record.category == normalized_category
            ]
        records.sort(key=lambda item: (item.category, item.provider_id))
        return tuple(self._copy_record(record) for record in records)

    def _copy_record(self, record: ProviderRecord) -> ProviderRecord:
        return ProviderRecord(
            provider_id=record.provider_id,
            category=record.category,
            provider=record.provider,
            metadata=dict(record.metadata),
        )

    def _snapshot_metadata(
        self,
        provider: Any,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if metadata is not None:
            return _copy_metadata(metadata)
        describe = getattr(provider, "describe", None)
        if not callable(describe):
            return {}
        try:
            snapshot = describe()
        except Exception as exc:
            raise InvalidProviderRegistrationError(
                f"provider describe() failed: {exc}"
            ) from exc
        return _copy_metadata(snapshot)


class ProviderResolver:
    """Read-side lookup over an injected ProviderRegistry.

    Resolution never registers, connects, fetches, or closes providers.
    Unknown ids/categories fail; there is no fallback.
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        if registry is None:
            raise InvalidProviderRegistrationError("registry is required")
        if not isinstance(registry, ProviderRegistry):
            raise InvalidProviderRegistrationError(
                "registry must be a ProviderRegistry"
            )
        self._registry = registry

    def get_record(self, category: str, provider_id: str) -> ProviderRecord:
        """Resolve the explicit registry record. Never falls back or activates."""
        return self._registry.get(category, provider_id)

    def resolve(self, category: str, provider_id: str) -> Any:
        return self.get_record(category, provider_id).provider

    def resolve_market_data(self, provider_id: str) -> MarketDataProvider:
        provider = self.resolve(CATEGORY_MARKET_DATA, provider_id)
        if not isinstance(provider, MarketDataProvider):
            raise InvalidProviderRegistrationError(
                "resolved market-data provider must be MarketDataProvider"
            )
        return provider

    def resolve_quote(self, provider_id: str) -> QuoteProvider:
        provider = self.resolve(CATEGORY_QUOTE, provider_id)
        if not isinstance(provider, QuoteProvider):
            raise InvalidProviderRegistrationError(
                "resolved quote provider must be QuoteProvider"
            )
        return provider

    def contains(self, category: str, provider_id: str) -> bool:
        return self._registry.contains(category, provider_id)

    def list_records(
        self, category: Optional[str] = None
    ) -> Tuple[ProviderRecord, ...]:
        return self._registry.list_providers(category=category)
