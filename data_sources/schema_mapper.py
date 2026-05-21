"""Helpers for resolving logical entities in data source packs."""
from __future__ import annotations

from data_sources.loader import get_data_source_pack


class SchemaMappingError(LookupError):
    """Raised when a data source entity mapping cannot be resolved."""


def resolve_entity_table(data_source_id: str, entity: str) -> str:
    pack = get_data_source_pack(data_source_id)
    if pack is None:
        raise SchemaMappingError(f"Data source pack not found: {data_source_id}")
    mapping = pack.entities.get(entity)
    if mapping is None:
        raise SchemaMappingError(f"Entity mapping not found: {data_source_id}.{entity}")
    return mapping.table


def resolve_field(data_source_id: str, entity: str, logical_field: str) -> str:
    pack = get_data_source_pack(data_source_id)
    if pack is None:
        raise SchemaMappingError(f"Data source pack not found: {data_source_id}")
    mapping = pack.entities.get(entity)
    if mapping is None:
        raise SchemaMappingError(f"Entity mapping not found: {data_source_id}.{entity}")
    return mapping.fields.get(logical_field, logical_field)
