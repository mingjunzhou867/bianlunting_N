# 工程化开发说明

本文档描述项目的本地开发、配置、启动、测试和产物管理约定。业务设计说明仍以根目录 `README.md` 为主。

## 环境要求

- Python 3.11+，建议使用根目录 `.venv`
- Node.js 20+ 与 `npm.cmd`
- MySQL 8.0+
- 可用的 LLM API Key

## 配置文件

后端配置模板位于 `config/.env.example`。首次启动前复制为 `config/.env`，并填写真实数据库和模型配置：

```powershell
Copy-Item config\.env.example config\.env
```

`config/.env` 已被 `.gitignore` 忽略，不能提交。前端配置模板位于 `frontend/.env.example`，如需覆盖 API 地址，可复制为 `frontend/.env`：

```powershell
Copy-Item frontend\.env.example frontend\.env
```

## 安装依赖

后端：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

前端：

```powershell
npm.cmd --prefix frontend install
```

## 启动服务

后端：

```powershell
.\scripts\start-backend.ps1
```

前端：

```powershell
.\scripts\start-frontend.ps1
```

同时启动后端和前端：

```powershell
.\scripts\start-all.ps1
```

默认后端地址为 `http://localhost:8000`，健康检查接口为 `GET /api/health`。默认前端地址由 Vite 输出，通常是 `http://localhost:5173`。

## 测试入口

后端纯单元测试，不要求真实数据库和 LLM：

```powershell
.\scripts\test-backend.ps1 -Mode unit
```

后端 API 路由测试：

```powershell
.\scripts\test-backend.ps1 -Mode api
```

后端数据库烟测，会读取 `config/.env` 并连接 MySQL：

```powershell
.\scripts\test-backend.ps1 -Mode db
```

前端状态机 smoke 测试和生产构建：

```powershell
.\scripts\test-frontend.ps1 -Mode all
```

## 测试分层

- `unit`：纯 Python 逻辑、证据投影、Agent JSON 解析、语义包、状态机和持久化契约等，适合作为每次提交前的基础门禁。
- `api`：FastAPI 路由注册与 mock 返回测试。当前 `api.main` 初始化会构造编排器，若本地配置缺失可能暴露环境问题。
- `db`：依赖 MySQL 样本库，验证取证链路和数据库连通性。
- `eval`：`tests/sql_test`、`tests/agents_test`、`tests/agents_disappear` 等实验评测，通常会调用 LLM 和数据库，结果受模型与数据版本影响。

## 产物管理

默认不提交以下内容：

- `config/.env`
- `frontend/.env`
- `.venv/`、`frontend/node_modules/`、`frontend/dist/`
- `.agents/`、`.codex/`、`.claude/`
- 临时日志、缓存和草稿报告

论文图、答辩图、固定示例报告如果需要进入仓库，应按文档或演示用途显式提交；评测批量输出优先保存在测试报告目录，并在提交前确认体积和敏感性。

## 工程化边界

当前系统的稳定边界是：

- FastAPI 负责请求入口、流式事件、历史会话和报告下载。
- `policy_packs/` 负责保存可插拔政策定义，`policy_router` 只负责把政策包或数据库配置暴露成运行时 `PolicyConfig`。
- `data_source_packs/` 负责保存可插拔数据源定义，声明连接引用、实体到真实表的映射和采集器能力。
- `DynamicEvidenceCollector` 负责取证规划、SQL 执行/修复和证据装配。
- `EvidenceItem` / `EvidenceBundle` 是 Agent 判断的事实输入边界。
- 多 Agent 只应基于证据、政策和受控工具输出判断。
- 人工复核结果应作为高优先级证据进入后续裁决，而不是普通备注。

后续 Agent Runtime、Memory 分层、Tool 审计和 Trace Replay 的升级，应优先保持这些边界稳定。

## Policy Pack

项目当前支持可插拔政策包，入口位于 `policy_packs/`，加载器位于 `policy/policy_pack_loader.py`。政策包优先于数据库政策配置；如果数据库中存在同名 `policy_id`，运行时以政策包为准，数据库只补充未迁移的旧政策。

一个政策包建议包含：

- `manifest.yaml`：政策 ID、政策包 ID、政策名称、版本、适用主体、裁决标签和默认数据源。
- `rules.yaml`：结构化规则，按 `basic_conditions`、`exclusion_conditions`、`inference_rules`、`calculation_rules` 分组。
- `evidence_requirements.yaml`：该政策需要哪些证据、实体、字段和兜底方式。
- `prompts.yaml`：Agent 审核口径和人工复核项。
- `report_template.yaml`：报告标题和章节声明。

当前已迁移的首个政策包为 `policy_packs/flexible_employment_subsidy/`，兼容运行时 `policy_id=POLICY_001`。后端提供只读发现接口：

```text
GET /api/policy-packs
```

兼容规则：

- 旧接口继续接收 `confirmed_policy_id`。
- 新请求可传 `policy_pack_id`，系统会解析为对应 `policy_id`。
- 取证规划优先使用政策包：`rules.yaml` 提供规则和 SQL 参考，`evidence_requirements.yaml` 提供实体、字段、期望信号和缺失证据兜底策略。
- 如果找不到政策包，系统会回退到旧数据库规则和问题模板规划器。

## Evidence Planning

运行时取证计划位于 `cognition/evidence_planner.py`。当前规划链路的责任边界是：

- `policy_packs/*/rules.yaml`：定义政策条款、规则类型和 SQL 模板参考。
- `policy_packs/*/evidence_requirements.yaml`：定义每条规则需要哪些业务实体和字段，不直接绑定某个客户数据库表。
- `data_source_packs/*/schema_map.yaml`：把政策层的逻辑实体和字段映射到真实表、资源和字段。
- `collectors/registry.py`：按 `data_source_id` 解析实际取证 collector。

因此新增政策时，应优先补政策包；新增客户数据库或表结构时，应优先补数据源包；只有新增取证方式时，才需要新增 collector。提交前可运行：

```powershell
.\scripts\validate-packs.ps1
```

该脚本会检查政策包、数据源包、collector 注册关系，以及政策证据需求是否能被默认数据源包支撑。

## Data Source Pack

项目当前支持可插拔数据源包，入口位于 `data_source_packs/`，加载器位于 `data_sources/loader.py`。数据源包不保存真实密码，只声明连接配置引用和业务实体映射。

一个数据源包建议包含：

- `manifest.yaml`：数据源 ID、展示名称、类型、版本、连接配置引用和字符集。
- `schema_map.yaml`：逻辑实体到真实表、主键字段和字段名的映射。
- `collectors.yaml`：该数据源支持的采集器能力。
- `connection.example.yaml`：连接配置示例，真实值仍写入 `config/.env` 或客户环境变量。

当前内置两个示例数据源包：

- `data_source_packs/local_mysql_demo/`：默认 MySQL 示例库，继续服务现有 Text-to-SQL 取证链路。
- `data_source_packs/table_payload_demo/`：无数据库表格材料入口，适合客户系统先把 Excel/API/表单结果整理成结构化行，再交给审查链路。

后端提供只读发现接口：

```text
GET /api/data-sources
```

兼容规则：

- 旧请求不传 `data_source_id` 时，默认使用 `local_mysql_demo`。
- 新请求可传 `data_source_id`，系统会把该 ID 写入 Trace、运行结果和持久化快照。
- SQL 执行入口位于 `data_sources/session.py`，当前支持 `mysql + config/.env` 类型的数据源包。
- `DynamicEvidenceCollector`、`AutoDebugger` 和取证回退查询会按 `data_source_id` 获取 Session；未实现的非 MySQL 数据源会明确报错。
- Collector 注册入口位于 `collectors/registry.py`。默认注册 `mysql`、`dynamic_mysql_text2sql` 和 `table_payload`。
- `table_payload` 请求通过 `POST /api/debate` 或 `POST /api/debate_stream` 传入 `data_source_id=table_payload_demo` 和 `table_payload`。`table_payload` 支持 `records` 或 `tables` 两种结构，collector 会统一转换为 `EvidenceItem`。
- 后续 Excel/API 数据源应实现对应 collector，或先转换为 `table_payload`，而不是复用 SQLAlchemy MySQL Session。

`table_payload` 最小请求示例：

```json
{
  "id_card": "42090219760310000D",
  "confirmed_policy_id": "POLICY_001",
  "data_source_id": "table_payload_demo",
  "table_payload": {
    "records": [
      {
        "rule_id": "RULE_001",
        "target": "employment",
        "result_summary": "employment status exists",
        "supports_conclusion": true,
        "confidence": 0.9
      }
    ]
  }
}
```

## Trace 事件

项目当前提供轻量运行时 Trace，入口位于 `runtime/trace.py`。Trace 不要求数据库 schema 变更，会随 API 结果和 `snapshot_payload` 一起保存。

每条事件至少包含：

- `event_id`：会话内递增事件 ID
- `timestamp`：UTC 时间
- `session_id`：审查会话 ID
- `policy_id`：当前政策 ID
- `stage`：阶段，如 `session`、`planning`、`evidence`、`tool`、`debate`、`arbitration`
- `action`：阶段内动作
- `status`：`info`、`success`、`warning`、`danger`
- `log`：前端可直接展示的摘要
- `payload`：可选结构化上下文

Trace 当前覆盖：

- 会话启动和完成
- 取证计划和动态取证
- Agent 初判与多轮回应
- Agent Tool 调用开始、完成和失败
- 仲裁与条款级报告生成

Trace 的设计原则是记录“系统做了什么”，而不是记录模型隐式思维链。后续做 Tool 审计、Memory 分层、Replay 回放时，应继续复用该结构。

## Memory 分层

项目当前提供会话级 Memory 快照，入口位于 `runtime/memory.py`。Memory 不直接改变 Agent 判断，而是在会话完成后把关键材料整理为可检索、可审计的分层记录，并随 `snapshot_payload` 一起保存。

信任层级：

- `P0_DATA`：数据库事实和系统可观测事实，例如 `EvidenceItem`
- `P1_MANUAL`：人工复核和人工补证
- `P2_DECISION`：已经完成的裁决结论
- `P3_AGENT`：Agent 判断、观点和论据
- `P4_INFERRED`：低信任的推断型运维经验，例如工具失败或取证异常摘要

Memory 的工程边界：

- 高信任层级可以作为后续审查的事实参考。
- `P3_AGENT` 和 `P4_INFERRED` 只能辅助解释、检索和诊断，不能覆盖政策规则、数据库事实或人工复核。
- 后端提供只读检索入口 `GET /api/memory/search`，支持 `q`、`policy_id`、`trust_level`、`source_type`、`limit` 参数。
- Memory 检索返回历史会话中的结构化记录，并对身份证号做脱敏处理；检索结果不直接改变当前会话结论。
- 后续可在此基础上增加相似案例召回、Replay 对比和人工复核后的 Memory 提升机制。
