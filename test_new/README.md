# test_new 数据与图表口径说明

本目录只保留当前作品报告采用的测试数据、实际运行结果和同口径图表。旧 `tests/` 目录、旧测试输出、临时调试结果和口径不一致的历史图片不纳入本目录。

## 目录结构

| 目录 | 内容 |
| --- | --- |
| `source_cases/` | 130 条政策审查多 Agent 链路样本定义，以及 50 条样本分析说明 |
| `datasets/sql_1000_cases/` | SQL 评测使用的 1000 条数据集、四类各 250 条样本、桌面导入的 SQL 与 Excel 数据基础 |
| `final_results/multi_agent_130/` | 130 条多 Agent 链路实际运行结果和最终统计表 |
| `final_results/sql_four_chain_500/` | 500 条 SQL 四链路实际运行结果和统计表 |
| `final_figures/multi_agent_130/` | 与 130 条多 Agent 结果一致的报告图表 |
| `final_figures/sql_four_chain_500/` | 与 500 条 SQL 四链路结果一致的报告图表 |

## 数据基础

SQL 数据集口径如下：

| 文件 | 说明 | 样本数 |
| --- | --- | ---: |
| `datasets/sql_1000_cases/sql_test_1000_full_20260522_170343.json` | SQL 评测完整样本 | 1000 |
| `datasets/sql_1000_cases/sql_test_1000_full_20260522_170343.csv` | SQL 评测完整样本表格版 | 1000 |
| `datasets/sql_1000_cases/sql1000_condition_20260522_170850.*` | 条件查询样本 | 250 |
| `datasets/sql_1000_cases/sql1000_muti_20260522_170857.*` | 多表查询样本 | 250 |
| `datasets/sql_1000_cases/sql1000_simple_20260522_170904.*` | 简单查询样本 | 250 |
| `datasets/sql_1000_cases/sql1000_sum_20260522_170910.*` | 聚合查询样本 | 250 |
| `datasets/sql_1000_cases/personas_simulated_1000.sql` | 人员与业务模拟数据 SQL 导入文件 | 实际导出文件 |
| `datasets/sql_1000_cases/demo.xlsx` | 人员与业务模拟数据 Excel 文件 | 实际导出文件 |

多 Agent 样本口径如下：

| 文件 | 说明 | 样本数 |
| --- | --- | ---: |
| `source_cases/agent_chain_policy_cases_130.json` | 多 Agent 政策链路样本 | 130 |
| `final_results/multi_agent_130/latest_results.json` | 多 Agent 链路运行结果 | 130 |

## 最终报告指标

以下指标均来自本目录中保留的实际运行结果或统计输出文件，不使用旧 `tests/` 图片，不使用反向比例推算。

SQL 四链路结果来自 `final_results/sql_four_chain_500/processed_experiment_results.csv`，每条链路实际评测 500 条样本：

| 方法 | 结果匹配率 | 执行成功率 |
| --- | ---: | ---: |
| Direct LLM | 0.30% | 0.40% |
| Schema-aware LLM | 19.70% | 94.90% |
| Harness w/o Repair | 49.60% | 99.60% |
| Full SQL Harness | 90.20% | 99.90% |

多 Agent 链路结果来自 `final_results/multi_agent_130/paper_metrics_table.md` 和 `final_results/multi_agent_130/latest_results.json`：

| 方法 | 结论准确率 | 决策质量 | 严格通过率 | 理由完整率 | 证据引用率 | 冲突识别率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Single Agent | 84.62% | 85.95% | 54.31% | 77.27% | 72.17% | 78.95% |
| Pro-Con Debate | 88.46% | 91.05% | 70.60% | 90.90% | 79.39% | 85.96% |
| No Evidence Constraint | 19.23% | 45.85% | 0.00% | 81.82% | 0.00% | 31.58% |
| Full Multi-Agent Chain | 94.62% | 96.80% | 92.31% | 100.00% | 97.83% | 91.23% |

## 图表纳入规则

`final_figures/` 只纳入与上述最终结果同口径的图表：

- SQL 图表来自 `final_results/sql_four_chain_500/processed_experiment_results.csv`、`processed_category_results.csv` 和 `failure_breakdown.csv`。
- 多 Agent 图表来自 `final_results/multi_agent_130/latest_results.json` 与 `paper_metrics_table.md`。
- 旧 `tests/sql_test/reports/visuals/` 中的图片未纳入，因为它们对应旧测试口径。
- 临时调试、日志、缓存和历史输出未纳入。
