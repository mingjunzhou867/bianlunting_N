"""Proof standards for argumentation framework — maps rule types to burden of proof."""
from __future__ import annotations

from enum import Enum


class ProofStandard(str, Enum):
    """证明标准（Burden of Proof）。

    对应法律/论证理论中的三级证明标准：
    - PREPONDERANCE: 优势证据，可能性大于不可能性即可
    - CLEAR_AND_CONVINCING: 清晰可信证据，高度盖然性
    - BEYOND_REASONABLE_DOUBT: 排除合理怀疑，最高标准
    """

    PREPONDERANCE = "preponderance"
    CLEAR_AND_CONVINCING = "clear_convincing"
    BEYOND_REASONABLE_DOUBT = "beyond_doubt"


# 规则类型 → 证明标准映射
# 必须满足条件：门槛低（优势证据即可通过）
# 必须排除条件：门槛高（排除合理怀疑才能否定）
# 灵活评判：中等门槛（清晰可信）
PROOF_STANDARD_BY_RULE_TYPE: dict[str, ProofStandard] = {
    "必须满足": ProofStandard.PREPONDERANCE,
    "必须排除": ProofStandard.BEYOND_REASONABLE_DOUBT,
    "灵活评判": ProofStandard.CLEAR_AND_CONVINCING,
    "灵活判断": ProofStandard.CLEAR_AND_CONVINCING,
    "额度计算": ProofStandard.PREPONDERANCE,
    "证据需求": ProofStandard.PREPONDERANCE,
}

# 证明标准 → defeat 阈值
# 用于 Grounded Semantics 的 defeat 判定：
# effective_strength >= threshold * arg.confidence → defeated
DEFEAT_THRESHOLD_BY_STANDARD: dict[ProofStandard, float] = {
    ProofStandard.PREPONDERANCE: 0.50,
    ProofStandard.CLEAR_AND_CONVINCING: 0.70,
    ProofStandard.BEYOND_REASONABLE_DOUBT: 0.90,
}


def proof_standard_for_rule_type(rule_type: str) -> ProofStandard:
    """根据规则类型返回对应的证明标准。"""
    return PROOF_STANDARD_BY_RULE_TYPE.get(rule_type, ProofStandard.PREPONDERANCE)
