# ChatGPT Image Generation Prompts - 智策通系统架构图

---

## 图3-1 系统总体架构图

```
Create a professional system architecture diagram for an academic thesis. The diagram should be clean, modern, and use a layered architecture style with a white background. Use Chinese text for all labels.

Title at the top: "图3-1 系统总体架构图"

The architecture has 6 horizontal layers stacked vertically, connected by downward arrows between layers. Each layer is a rounded rectangle with a distinct color:

Layer 1 (top, light blue #E3F2FD): "前端展示层"
- Contains: Vue 3 + Vite, Element Plus
- Show 5 small boxes inside: "用户输入视图", "取证规划中心", "多Agent辩论庭", "裁决结果视图", "历史会话面板"
- Label: "SSE 实时流式渲染"

Layer 2 (light green #E8F5E9): "API 接口层"
- Contains: FastAPI + uvicorn
- Show 4 small boxes: "意图识别接口", "政策查询接口", "辩论流式接口", "报告下载接口"
- Label: "RESTful API / SSE"

Layer 3 (light yellow #FFF8E1): "意图理解与政策路由层"
- Contains 3 boxes: "IntentUnderstandingAgent", "PolicyRouter", "PolicyParserAgent"
- Arrow from left box to right boxes

Layer 4 (light orange #FFF3E0): "政策认知与取证层"
- Left section "证据规划": "EvidencePlanner"
- Center section "动态取证": "DynamicEvidenceCollector", "AutoDebugger", "EvidenceAssembler"
- Right section "工具注册": "Text2SQL Tool", "Dict Tool"

Layer 5 (light purple #F3E5F5): "多智能体辩论与仲裁层"
- 5 agent boxes in a row: "严格合规Agent", "宽松业务Agent", "探索补充Agent", "经验案例Agent", "审计复核Agent"
- Below them: "DebateOrchestrator" (center), "ConservativeArbiter" (right)
- Below: "RuleEngine", "WeightedVote", "MajorityFallback" (three-layer decision pipeline)

Layer 6 (bottom, light red #FFEBEE): "持久化与报告层"
- Left: "MySQL 数据库" with sub-boxes: "debate_session", "agent_debate_log", "evidence_snapshot", "业务数据表"
- Right: "PDF 裁决报告生成"

Use clean connecting arrows between layers showing data flow. Style should be suitable for an academic thesis - professional, not too colorful, clear hierarchy. Use a sans-serif font. The overall size should be landscape orientation, approximately 16:9 aspect ratio.
```

---

## 图3-2 政策规则库与业务数据库关系图

```
Create a professional database relationship diagram for an academic thesis. White background, clean and modern style, Chinese labels.

Title at the top: "图3-2 政策规则库与业务数据库关系图"

The diagram should show two main sections connected by a central mapping mechanism:

LEFT SIDE - "政策规则库 (Policy Rule Base)":
A vertical stack of 4 rounded rectangles:
1. "基础条件 (basic_conditions)" - green
2. "排除条件 (exclusion_conditions)" - red
3. "合理推断 (inference_rules)" - yellow
4. "额度计算 (calculation_rules)" - blue

Each box shows internal fields: rule_id, description, pass_condition, fail_condition, check_logic

CENTER - "规则-数据映射层":
A diamond shape labeled "EvidencePlanner" with arrows pointing to it from the left and pointing to the right.
Below it, a box labeled "SQL模板 / 动态SQL生成" with fields: evidence_targets, relevant_fields, sql_template

RIGHT SIDE - "业务数据库 (MySQL bysj)":
A vertical stack of database cylinder icons with table names:
1. "person (人员信息)" - fields: id_card, name, age, gender
2. "company_info (企业信息)" - fields: company_id, business_type
3. "hardship_certification (困难认定)" - fields: cert_type, cert_date
4. "social_insurance_payment (社保缴费)" - fields: pay_month, amount
5. "subsidy_payment_history (补贴发放)" - fields: subsidy_type, payment_amount
6. "employment_record (就业记录)" - fields: job_type, start_date

Show connecting arrows from center to right tables, with labels like "rule_id → SQL查询 → 业务表"

Bottom section: "持久化存储" with 3 database tables:
- "debate_session" connected to "agent_debate_log" (1:N)
- "debate_session" connected to "evidence_snapshot" (1:N)

Use entity-relationship style with clean lines. Professional academic style, suitable for a thesis.
```

---

## 图3-3 T2SQL取证与证据卡片生成流程图

```
Create a professional flowchart diagram for an academic thesis. White background, clean modern style, Chinese labels.

Title at the top: "图3-3 T2SQL取证与证据卡片生成流程图"

The flowchart should be a top-down flow with clear stages, using different shapes for different types of steps:

STAGE 1 - Input (rounded rectangle, light blue):
"输入: person_id + policy_id"

Arrow down to:

STAGE 2 - Evidence Planning (rectangle, green border):
"证据规划 (EvidencePlanner)"
Inside: "加载政策规则 → 转换为 EvidencePlanItem 列表"
Sub-boxes: "must_satisfy 规则", "must_exclude 规则", "flexible 规则"
Output arrow labeled "EvidencePlan"

Arrow down to:

STAGE 3 - Dynamic Evidence Collection (large rectangle, orange border):
"动态取证 (DynamicEvidenceCollector)"
Show a loop/iteration box: "遍历 plan.items"
Inside the loop, 4 steps connected vertically:
Step 3a: "SQL生成/选择" (diamond: "是否有SQL模板?" → Yes: 使用模板 / No: 动态生成)
Step 3b: "执行SQL查询" → diamond: "执行成功?" → No: "AutoDebugger自动修复重试" (loop back)
Step 3c: "EvidenceAssembler 证据装配"
Step 3d: "应用硬规则语义" → "MUST规则命中=support" / "EXCLUDE规则命中=contradict"
Output: "yield EvidenceItem"

Arrow down to:

STAGE 4 - Evidence Projection (rectangle, purple border):
"证据投影 (project_evidence)"
Inside 3 steps connected:
"证据质量排序 (sort_evidence_items)"
→ "构建语义标签 (build_item_semantics)" with outputs: "supports / contradicts / missing / unresolved"
→ "计算质量分数 (score_evidence_item)"
Output: "EvidenceSummaryCard"

Arrow down to:

STAGE 5 - Output (rounded rectangle, light green):
"输出: EvidenceProjection"
Sub-items: "cards列表", "uncertainty_markers", "resolved_count", "unresolved_count"

Use clean connecting arrows with labels. Professional academic style. The flowchart should be tall/narrow portrait orientation.
```

---

## 图3-4 证据约束下的多Agent辩论仲裁流程图

```
Create a professional flowchart diagram for an academic thesis. White background, clean modern style, Chinese labels.

Title at the top: "图3-4 证据约束下的多Agent辩论仲裁流程图"

The diagram should show the multi-agent debate and arbitration process in a clear flow:

TOP SECTION - Input:
"输入: EvidenceProjection (证据投影)"
→ "构建人员画像 (PersonaBuilder)"

MIDDLE SECTION - Debate Loop (this should be the largest and most prominent part):

Show a large box labeled "辩论编排 (DebateOrchestrator)" containing:

ROUND 0 (Initial Judgment):
"第0轮: 初判轮"
5 agent boxes in a horizontal row, each with their role:
- "严格合规Agent" (icon: shield/badge)
- "宽松业务Agent" (icon: handshake)
- "探索补充Agent" (icon: magnifying glass)
- "经验案例Agent" (icon: book)
- "审计复核Agent" (icon: clipboard)

Each agent has a speech bubble showing: "judge() → AgentJudgment"
Below: "提取论点 → ArgumentGraph (论辩图谱)"

A decision diamond: "共识检测"
- Three criteria listed: "投票共识 ≥ 0.8", "加权置信度 ≥ 0.8", "论辩图谱收敛"
- If Yes → exit loop
- If No → continue to Round 1..N

ROUND 1..N (Debate Rounds):
"辩论轮: Agent.debate_respond()"
Show agents with speech bubbles showing interaction: "查看其他Agent判断 → 回应"
"AttackDetector 检测攻击关系"
"更新 ArgumentGraph"
Loop back to "共识检测" diamond

After loop exit:

BOTTOM SECTION - Arbitration (three-layer decision pipeline):
Show 3 horizontal boxes connected in sequence:
Layer 1: "规则引擎 (RuleEngine)" - "硬规则一票否决/一票通过"
Layer 2: "加权投票 (WeightedVote)" - "Agent置信度 × 证据质量"
Layer 3: "多数表决 (MajorityFallback)" - "简单多数投票兜底"

Below: "保守仲裁器 (ConservativeArbiter)" → "生成仲裁解释"

OUTPUT SECTION:
"裁决报告 (AdjudicationReport)"
Sub-items: "summary (最终结论)", "clause_results (条款级判定)", "debate_digest (辩论摘要)", "next_actions (后续建议)"

Use clean connecting arrows, show the iterative nature of the debate with a loop arrow. Professional academic style.
```

---

## 图3-5 人工复核与报告归档流程图

```
Create a professional flowchart diagram for an academic thesis. White background, clean modern style, Chinese labels.

Title at the top: "图3-5 人工复核与报告归档流程图"

The diagram should show the human review and report archival process:

START (rounded rectangle, light blue):
"辩论完成，展示裁决结果"

Arrow to decision diamond:
"是否需要人工补证?"

If No → direct arrow to "报告归档" section

If Yes → enter "人工补证流程":

STEP 1 - Manual Supplement (rectangle, light yellow):
"人工补证面板 (ManualSupplementPanel)"
Sub-steps:
- "选择具体条款 (clause_id)"
- "填写补证说明 (detail)"
- "选择立场: 支持 / 反驳"
- "状态: pending_review"

STEP 2 - Supplement Processing (rectangle, light orange):
"发起复核"
Sub-steps:
- "人工补证 → EvidenceItem (category=manual_supplement)"
- "人工证据优先级最高，覆盖系统证据"
- "_prioritize_manual_evidence()"

STEP 3 - Re-debate (rectangle, light purple):
"重新辩论 (reuse_evidence=true)"
Sub-steps:
- "合并人工证据 + 系统证据"
- "POST /api/debate_stream"
- "多Agent重新辩论"

Arrow to:

STEP 4 - Confirmation (rectangle, light green):
"复核确认"
Sub-steps:
- "POST /api/debates/{session_id}/manual_review/confirm"
- "补证状态 → adopted"

Arrow to:

ARCHIVAL SECTION (rectangle, light gray):
"报告归档"
Three parallel paths:
Path 1: "持久化存储" → "MySQL 三表写入"
  - "debate_session (会话主表)"
  - "agent_debate_log (辩论记录)"
  - "evidence_snapshot (证据快照)"

Path 2: "PDF报告生成" → "official_report_generator"
  - "政务风格裁决书"
  - "政策信息 + 人员信息 + 证据清单 + 辩论摘要"

Path 3: "历史会话" → "GET /api/debates (查询回放)"

END (rounded rectangle, light blue):
"裁决完成，可供查询与下载"

Use clean connecting arrows. Show the optional nature of the manual review with a branch. Professional academic style.
```

---

## 使用说明

1. 将每个提示词单独复制到 ChatGPT (GPT-4o with DALL-E) 中生成图片
2. 建议使用 16:9 或 4:3 的画布比例
3. 如果生成结果不理想，可以调整以下参数：
   - 增加 "minimalist style" 或 "flat design" 让图更简洁
   - 增加 "no gradients, solid colors only" 让配色更统一
   - 增加 "thick borders, high contrast" 让图更清晰
4. 生成后可能需要用图片编辑工具微调中文文字的显示
