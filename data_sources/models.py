"""Models for pluggable data source packs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DataSourceManifest(BaseModel):
    """Data source pack metadata."""

    data_source_id: str = Field(..., description="数据源包ID")
    display_name: str = Field(..., description="展示名称")
    type: str = Field(..., description="数据源类型，如 mysql、postgresql、excel、api")
    version: str = Field("1.0.0", description="数据源包版本")
    description: str = Field("", description="说明")
    connection_ref: str = Field("config.env", description="连接配置引用")
    charset: str = Field("utf8mb4", description="字符集")
    ddl_file: str = Field("", description="Pack 内 DDL 文件名（相对于 pack 目录）")


class EntityMapping(BaseModel):
    """Logical entity to physical table/API mapping."""

    entity: str = Field(..., description="逻辑实体")
    table: str = Field(..., description="物理表名或资源名")
    id_field: str = Field("id_card", description="主体标识字段")
    fields: dict[str, str] = Field(default_factory=dict, description="逻辑字段到物理字段映射")
    description: str = Field("", description="实体说明")


class CollectorCapability(BaseModel):
    """Collector capability declared by a data source pack."""

    collector_id: str = Field(..., description="采集器ID")
    type: str = Field(..., description="采集器类型")
    entities: list[str] = Field(default_factory=list, description="支持实体")
    supports_stream: bool = Field(True, description="是否支持流式取证")
    description: str = Field("", description="说明")


class DataSourcePack(BaseModel):
    """Complete data source pack."""

    manifest: DataSourceManifest
    entities: dict[str, EntityMapping] = Field(default_factory=dict, description="实体映射")
    collectors: list[CollectorCapability] = Field(default_factory=list, description="采集能力")
    source_dir: str = Field("", description="数据源包目录")

    def to_summary(self) -> dict[str, Any]:
        return {
            "data_source_id": self.manifest.data_source_id,
            "display_name": self.manifest.display_name,
            "type": self.manifest.type,
            "version": self.manifest.version,
            "description": self.manifest.description,
            "connection_ref": self.manifest.connection_ref,
            "entity_count": len(self.entities),
            "collector_count": len(self.collectors),
        }

