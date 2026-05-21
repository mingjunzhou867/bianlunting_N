"""Agent factory helpers."""

from agents.agent_auditor import AuditChallengeAgent
from agents.agent_empirical import EmpiricalReasoningAgent
from agents.agent_explorer import ExploratoryAgent
from agents.agent_lenient import LenientBusinessAgent
from agents.agent_strict import StrictComplianceAgent
from agents.base_agent import AgentJudgment, BaseAgent, format_evidence_bundle


def create_all_agents(policy_name: str = "政策资格认定") -> list[BaseAgent]:
    """Return the default five debate agents in a stable order."""

    return [
        StrictComplianceAgent(policy_name=policy_name),
        LenientBusinessAgent(policy_name=policy_name),
        ExploratoryAgent(policy_name=policy_name),
        EmpiricalReasoningAgent(policy_name=policy_name),
        AuditChallengeAgent(policy_name=policy_name),
    ]


__all__ = [
    "BaseAgent",
    "AgentJudgment",
    "format_evidence_bundle",
    "StrictComplianceAgent",
    "LenientBusinessAgent",
    "ExploratoryAgent",
    "EmpiricalReasoningAgent",
    "AuditChallengeAgent",
    "create_all_agents",
]
