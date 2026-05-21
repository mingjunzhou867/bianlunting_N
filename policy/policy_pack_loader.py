"""Policy Pack loader for pluggable policy definitions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from policy.policy_models import (
    CollectorOverrides,
    EvidenceRequirement,
    PolicyConfig,
    PolicyPack,
    PolicyPackManifest,
    PolicyRule,
    PromptPack,
    ReportTemplate,
    StructuredRules,
)


DEFAULT_POLICY_PACKS_DIR = Path(__file__).resolve().parent.parent / "policy_packs"
RULE_BUCKETS = {
    "basic_conditions",
    "exclusion_conditions",
    "inference_rules",
    "calculation_rules",
}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file_obj:
        loaded = yaml.safe_load(file_obj) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return loaded


def _build_rules(raw_rules: dict[str, Any]) -> StructuredRules:
    buckets: dict[str, list[PolicyRule]] = {bucket: [] for bucket in RULE_BUCKETS}
    for bucket in RULE_BUCKETS:
        rows = raw_rules.get(bucket) or []
        if not isinstance(rows, list):
            raise ValueError(f"Rule bucket must be a list: {bucket}")
        buckets[bucket] = [PolicyRule(**row) for row in rows if isinstance(row, dict)]
    return StructuredRules(**buckets)


def load_policy_pack(pack_dir: Path) -> PolicyPack:
    """Load one policy pack directory."""
    manifest = PolicyPackManifest(**_read_yaml(pack_dir / "manifest.yaml"))
    rules = _build_rules(_read_yaml(pack_dir / "rules.yaml"))
    evidence_rows = _read_yaml(pack_dir / "evidence_requirements.yaml").get("requirements") or []
    prompt_data = _read_yaml(pack_dir / "prompts.yaml")
    report_data = _read_yaml(pack_dir / "report_template.yaml")
    overrides_data = _read_yaml(pack_dir / "collector_overrides.yaml")
    collector_overrides = CollectorOverrides(**overrides_data) if overrides_data else CollectorOverrides()
    return PolicyPack(
        manifest=manifest,
        structured_rules=rules,
        evidence_requirements=[
            EvidenceRequirement(**row)
            for row in evidence_rows
            if isinstance(row, dict)
        ],
        prompts=PromptPack(**prompt_data),
        report_template=ReportTemplate(**report_data),
        collector_overrides=collector_overrides,
        source_dir=str(pack_dir),
    )


def load_policy_packs(root_dir: Path | None = None) -> dict[str, PolicyPack]:
    """Load all policy packs, keyed by policy_id."""
    root = root_dir or DEFAULT_POLICY_PACKS_DIR
    if not root.exists():
        return {}

    packs: dict[str, PolicyPack] = {}
    for pack_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if not (pack_dir / "manifest.yaml").exists():
            continue
        try:
            pack = load_policy_pack(pack_dir)
        except Exception as exc:
            logger.error("[PolicyPackLoader] load failed {}: {}", pack_dir.name, exc)
            continue
        packs[pack.manifest.policy_id] = pack
        logger.debug(
            "[PolicyPackLoader] loaded: {} <- {}",
            pack.manifest.policy_id,
            pack_dir.name,
        )
    return packs


def load_policy_configs_from_packs(root_dir: Path | None = None) -> dict[str, PolicyConfig]:
    """Load packs and expose them through the legacy PolicyConfig contract."""
    return {
        policy_id: pack.to_policy_config()
        for policy_id, pack in load_policy_packs(root_dir).items()
    }


def list_policy_pack_summaries(root_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return lightweight metadata for UI/API discovery."""
    summaries: list[dict[str, Any]] = []
    for pack in load_policy_packs(root_dir).values():
        manifest = pack.manifest
        summaries.append(
            {
                "pack_id": manifest.pack_id,
                "policy_id": manifest.policy_id,
                "policy_name": manifest.policy_name,
                "policy_type": manifest.policy_type,
                "version": manifest.version,
                "applicant_type": manifest.applicant_type,
                "description": manifest.description,
                "default_data_source_id": manifest.default_data_source_id or "",
                "evidence_requirement_count": len(pack.evidence_requirements),
            }
        )
    return summaries


def resolve_policy_id(identifier: str | None, root_dir: Path | None = None) -> str | None:
    """Resolve a policy_id or pack_id to the runtime policy_id."""
    if not identifier:
        return None
    normalized = str(identifier).strip()
    packs = load_policy_packs(root_dir)
    if normalized in packs:
        return normalized
    for pack in packs.values():
        if pack.manifest.pack_id == normalized:
            return pack.manifest.policy_id
    return normalized
