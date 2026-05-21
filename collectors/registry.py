"""Registry for data-source-specific evidence collectors."""
from __future__ import annotations

from collections.abc import Callable

from collectors.base import EvidenceCollectorProtocol
from collectors.table_payload_collector import TablePayloadCollector
from data_sources.loader import get_data_source_pack, resolve_data_source_id
from text2sql.dynamic.dynamic_collector import DynamicEvidenceCollector


CollectorFactory = Callable[[], EvidenceCollectorProtocol]


class CollectorResolutionError(RuntimeError):
    """Raised when no collector can serve a data source pack."""


class CollectorRegistry:
    """Resolve data source packs to collector implementations."""

    def __init__(self):
        self._by_type: dict[str, CollectorFactory] = {}
        self._by_collector_id: dict[str, CollectorFactory] = {}

    def register_type(self, source_type: str, factory: CollectorFactory) -> None:
        self._by_type[source_type.lower()] = factory

    def register_collector_id(self, collector_id: str, factory: CollectorFactory) -> None:
        self._by_collector_id[collector_id] = factory

    def create_for_data_source(self, data_source_id: str | None) -> EvidenceCollectorProtocol:
        resolved_id = resolve_data_source_id(data_source_id)
        pack = get_data_source_pack(resolved_id)
        if pack is None:
            raise CollectorResolutionError(f"Data source pack not found: {resolved_id}")

        for capability in pack.collectors:
            factory = self._by_collector_id.get(capability.collector_id)
            if factory is not None:
                return factory()

        source_type = pack.manifest.type.lower()
        factory = self._by_type.get(source_type)
        if factory is not None:
            return factory()

        raise CollectorResolutionError(
            f"No evidence collector registered for data source {resolved_id} ({source_type})"
        )


def build_default_collector_registry() -> CollectorRegistry:
    registry = CollectorRegistry()
    registry.register_type("mysql", DynamicEvidenceCollector)
    registry.register_type("table_payload", TablePayloadCollector)
    registry.register_collector_id("dynamic_mysql_text2sql", DynamicEvidenceCollector)
    registry.register_collector_id("table_payload", TablePayloadCollector)
    return registry
