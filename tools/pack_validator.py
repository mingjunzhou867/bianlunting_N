"""Contract validation for pluggable policy and data source packs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from collectors.registry import build_default_collector_registry
from data_sources.loader import DEFAULT_DATA_SOURCE_PACKS_DIR, load_data_source_pack, load_data_source_packs
from policy.policy_pack_loader import DEFAULT_POLICY_PACKS_DIR, load_policy_pack


REQUIRED_POLICY_FILES = {
    "manifest.yaml",
    "rules.yaml",
    "evidence_requirements.yaml",
    "prompts.yaml",
    "report_template.yaml",
}
REQUIRED_DATA_SOURCE_FILES = {"manifest.yaml", "schema_map.yaml", "collectors.yaml"}
RESERVED_COLLECTOR_IDS = {"manual_supplement"}
RESERVED_COLLECTOR_TYPES = {"manual"}


@dataclass(frozen=True)
class PackValidationIssue:
    """One pack validation finding."""

    level: str
    scope: str
    path: str
    message: str


def _iter_pack_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "manifest.yaml").exists())


def _required_file_issues(pack_dir: Path, required_files: set[str], scope: str) -> list[PackValidationIssue]:
    issues: list[PackValidationIssue] = []
    for filename in sorted(required_files):
        path = pack_dir / filename
        if not path.exists():
            issues.append(PackValidationIssue("error", scope, str(path), f"required file missing: {filename}"))
    return issues


def validate_data_source_packs(root_dir: Path | None = None) -> list[PackValidationIssue]:
    """Validate data source pack manifests, schema maps and collector bindings."""
    root = root_dir or DEFAULT_DATA_SOURCE_PACKS_DIR
    issues: list[PackValidationIssue] = []
    seen_ids: set[str] = set()
    registry = build_default_collector_registry()
    known_collector_ids = set(registry._by_collector_id)
    known_types = set(registry._by_type)

    for pack_dir in _iter_pack_dirs(root):
        scope = f"data_source:{pack_dir.name}"
        issues.extend(_required_file_issues(pack_dir, REQUIRED_DATA_SOURCE_FILES, scope))
        try:
            pack = load_data_source_pack(pack_dir)
        except Exception as exc:
            issues.append(PackValidationIssue("error", scope, str(pack_dir), f"load failed: {exc}"))
            continue

        data_source_id = pack.manifest.data_source_id
        if data_source_id in seen_ids:
            issues.append(PackValidationIssue("error", scope, str(pack_dir), f"duplicate data_source_id: {data_source_id}"))
        seen_ids.add(data_source_id)

        if not pack.collectors:
            issues.append(PackValidationIssue("error", scope, str(pack_dir / "collectors.yaml"), "no collectors declared"))

        entity_names = set(pack.entities)
        for capability in pack.collectors:
            is_registered = capability.collector_id in known_collector_ids or capability.type.lower() in known_types
            is_reserved = (
                capability.collector_id in RESERVED_COLLECTOR_IDS
                or capability.type.lower() in RESERVED_COLLECTOR_TYPES
            )
            if not is_registered and not is_reserved:
                issues.append(
                    PackValidationIssue(
                        "error",
                        scope,
                        str(pack_dir / "collectors.yaml"),
                        f"collector is not registered: {capability.collector_id}/{capability.type}",
                    )
                )
            missing_entities = [entity for entity in capability.entities if entity not in entity_names]
            if missing_entities:
                issues.append(
                    PackValidationIssue(
                        "error",
                        scope,
                        str(pack_dir / "collectors.yaml"),
                        f"collector references unknown entities: {', '.join(missing_entities)}",
                    )
                )

    return issues


def validate_policy_packs(
    policy_root_dir: Path | None = None,
    data_source_root_dir: Path | None = None,
) -> list[PackValidationIssue]:
    """Validate policy pack files and their references to data source packs."""
    policy_root = policy_root_dir or DEFAULT_POLICY_PACKS_DIR
    data_source_root = data_source_root_dir or DEFAULT_DATA_SOURCE_PACKS_DIR
    issues: list[PackValidationIssue] = []
    data_sources = load_data_source_packs(data_source_root)
    data_source_ids = set(data_sources)
    for data_source_dir in _iter_pack_dirs(data_source_root):
        try:
            load_data_source_pack(data_source_dir)
        except Exception as exc:
            issues.append(
                PackValidationIssue(
                    "error",
                    f"data_source:{data_source_dir.name}",
                    str(data_source_dir),
                    f"load failed while resolving policy references: {exc}",
                )
            )
    seen_policy_ids: set[str] = set()
    seen_pack_ids: set[str] = set()

    for pack_dir in _iter_pack_dirs(policy_root):
        scope = f"policy:{pack_dir.name}"
        issues.extend(_required_file_issues(pack_dir, REQUIRED_POLICY_FILES, scope))
        try:
            pack = load_policy_pack(pack_dir)
        except Exception as exc:
            issues.append(PackValidationIssue("error", scope, str(pack_dir), f"load failed: {exc}"))
            continue

        manifest = pack.manifest
        if manifest.policy_id in seen_policy_ids:
            issues.append(PackValidationIssue("error", scope, str(pack_dir), f"duplicate policy_id: {manifest.policy_id}"))
        if manifest.pack_id in seen_pack_ids:
            issues.append(PackValidationIssue("error", scope, str(pack_dir), f"duplicate pack_id: {manifest.pack_id}"))
        seen_policy_ids.add(manifest.policy_id)
        seen_pack_ids.add(manifest.pack_id)

        if manifest.default_data_source_id and manifest.default_data_source_id not in data_source_ids:
            issues.append(
                PackValidationIssue(
                    "error",
                    scope,
                    str(pack_dir / "manifest.yaml"),
                    f"default data source pack not found: {manifest.default_data_source_id}",
                )
            )

        default_data_source = (
            data_sources.get(manifest.default_data_source_id)
            if manifest.default_data_source_id
            else None
        )
        rule_ids = {
            rule.rule_id
            for bucket in (
                pack.structured_rules.basic_conditions,
                pack.structured_rules.exclusion_conditions,
                pack.structured_rules.inference_rules,
                pack.structured_rules.calculation_rules,
            )
            for rule in bucket
        }
        seen_requirement_ids: set[str] = set()
        for requirement in pack.evidence_requirements:
            if requirement.requirement_id in seen_requirement_ids:
                issues.append(
                    PackValidationIssue(
                        "error",
                        scope,
                        str(pack_dir / "evidence_requirements.yaml"),
                        f"duplicate requirement_id: {requirement.requirement_id}",
                    )
                )
            seen_requirement_ids.add(requirement.requirement_id)
            if requirement.rule_id not in rule_ids:
                issues.append(
                    PackValidationIssue(
                        "error",
                        scope,
                        str(pack_dir / "evidence_requirements.yaml"),
                        f"requirement references unknown rule_id: {requirement.rule_id}",
                    )
                )
            if default_data_source is not None:
                entity_mapping = default_data_source.entities.get(requirement.entity)
                if entity_mapping is None:
                    issues.append(
                        PackValidationIssue(
                            "error",
                            scope,
                            str(pack_dir / "evidence_requirements.yaml"),
                            f"requirement entity not mapped by default data source: {requirement.entity}",
                        )
                    )
                    continue
                available_fields = set(entity_mapping.fields)
                available_fields.update(entity_mapping.fields.values())
                available_fields.add(entity_mapping.id_field)
                missing_fields = [
                    field
                    for field in requirement.required_fields
                    if "." not in field and field not in available_fields
                ]
                if missing_fields:
                    issues.append(
                        PackValidationIssue(
                            "error",
                            scope,
                            str(pack_dir / "evidence_requirements.yaml"),
                            f"requirement fields not mapped by default data source: {', '.join(missing_fields)}",
                        )
                    )

    return issues


def validate_all_packs(
    policy_root_dir: Path | None = None,
    data_source_root_dir: Path | None = None,
) -> list[PackValidationIssue]:
    """Validate every pluggable pack in the repository."""
    return [
        *validate_data_source_packs(data_source_root_dir),
        *validate_policy_packs(policy_root_dir, data_source_root_dir),
    ]


def main() -> int:
    issues = validate_all_packs()
    if not issues:
        print("PACK_VALIDATION_OK")
        return 0
    for issue in issues:
        print(f"{issue.level.upper()} [{issue.scope}] {issue.path}: {issue.message}")
    return 1 if any(issue.level == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
