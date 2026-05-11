"""Agent-facing evidence projection models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceSummaryCard(BaseModel):
    """A compact, traceable evidence card for debate agents."""

    card_id: str = Field(description="Card identifier, usually card_{rule_id}")
    question: str = Field(description="Question answered by this card")
    finding: str = Field(description="Natural-language evidence finding")
    status: Literal["supports", "contradicts", "unresolved", "missing"] = Field(
        description="High-level evidence status"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Card confidence")
    artifact_refs: list[str] = Field(
        default_factory=list,
        description="Traceable evidence artifact references",
    )
    evidence_score: float = Field(default=0.0, description="Evidence quality score 0-100")
    evidence_score_percent: str = Field(default="0.0%", description="Score as percentage string")
    score_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Score breakdown by dimension",
    )
    rank_reason: str = Field(default="", description="Human-readable score ranking reason")


class EvidenceProjection(BaseModel):
    """Summary-first debate input derived from retrieved evidence."""

    task_header: str = Field(description="Task title")
    target_person: str = Field(description="Target person id")
    policy_scope: str = Field(description="Policy scope")
    cards: list[EvidenceSummaryCard] = Field(default_factory=list)
    uncertainty_markers: list[str] = Field(default_factory=list)
    total_cards: int = Field(default=0)
    resolved_count: int = Field(default=0)
    unresolved_count: int = Field(default=0)
