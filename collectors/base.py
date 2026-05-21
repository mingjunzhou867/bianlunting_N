"""Collector protocol for pluggable evidence collection."""
from __future__ import annotations

from typing import Protocol

from evidence.evidence_model import EvidenceBundle, EvidenceItem
from runtime.trace import TraceContext


class EvidenceCollectorProtocol(Protocol):
    """Runtime contract shared by collector implementations."""

    def collect_all(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        collection_context: dict | None = None,
        trace: TraceContext | None = None,
    ) -> EvidenceBundle:
        ...

    def collect_stream(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        collection_context: dict | None = None,
        trace: TraceContext | None = None,
    ):
        ...


class UnsupportedCollector:
    """Explicit collector placeholder for data sources without execution support."""

    def __init__(self, message: str):
        self.message = message

    def collect_all(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        collection_context: dict | None = None,
        trace: TraceContext | None = None,
    ) -> EvidenceBundle:
        raise RuntimeError(self.message)

    def collect_stream(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        collection_context: dict | None = None,
        trace: TraceContext | None = None,
    ):
        raise RuntimeError(self.message)
