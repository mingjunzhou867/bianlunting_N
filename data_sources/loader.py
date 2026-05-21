"""Data Source Pack loader."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from data_sources.models import CollectorCapability, DataSourceManifest, DataSourcePack, EntityMapping


DEFAULT_DATA_SOURCE_PACKS_DIR = Path(__file__).resolve().parent.parent / "data_source_packs"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file_obj:
        loaded = yaml.safe_load(file_obj) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return loaded


def load_data_source_pack(pack_dir: Path) -> DataSourcePack:
    manifest = DataSourceManifest(**_read_yaml(pack_dir / "manifest.yaml"))
    raw_schema = _read_yaml(pack_dir / "schema_map.yaml")
    raw_collectors = _read_yaml(pack_dir / "collectors.yaml")

    entities: dict[str, EntityMapping] = {}
    for entity_name, row in (raw_schema.get("entities") or {}).items():
        if not isinstance(row, dict):
            continue
        payload = {"entity": entity_name, **row}
        entities[entity_name] = EntityMapping(**payload)

    collectors = [
        CollectorCapability(**row)
        for row in (raw_collectors.get("collectors") or [])
        if isinstance(row, dict)
    ]
    return DataSourcePack(
        manifest=manifest,
        entities=entities,
        collectors=collectors,
        source_dir=str(pack_dir),
    )


def load_data_source_packs(root_dir: Path | None = None) -> dict[str, DataSourcePack]:
    root = root_dir or DEFAULT_DATA_SOURCE_PACKS_DIR
    if not root.exists():
        return {}

    packs: dict[str, DataSourcePack] = {}
    for pack_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if not (pack_dir / "manifest.yaml").exists():
            continue
        try:
            pack = load_data_source_pack(pack_dir)
        except Exception as exc:
            logger.error("[DataSourceLoader] load failed {}: {}", pack_dir.name, exc)
            continue
        packs[pack.manifest.data_source_id] = pack
        logger.debug(
            "[DataSourceLoader] loaded: {} <- {}",
            pack.manifest.data_source_id,
            pack_dir.name,
        )
    return packs


def get_data_source_pack(data_source_id: str, root_dir: Path | None = None) -> DataSourcePack | None:
    return load_data_source_packs(root_dir).get(data_source_id)


def list_data_source_summaries(root_dir: Path | None = None) -> list[dict[str, Any]]:
    return [pack.to_summary() for pack in load_data_source_packs(root_dir).values()]


def resolve_data_source_id(data_source_id: str | None, default: str = "local_mysql_demo") -> str:
    normalized = str(data_source_id or "").strip()
    return normalized or default
