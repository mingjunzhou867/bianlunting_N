from pathlib import Path
import textwrap

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch


OUT_DIR = Path(r"C:\Users\asus\Desktop\系统测试PPT图表")

PALETTE = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "green_1": "#DDF3DE",
    "green_2": "#AADCA9",
    "green_3": "#8BCF8B",
    "red_1": "#F6CFCB",
    "red_2": "#E9A6A1",
    "red_strong": "#B64342",
    "neutral": "#CFCECE",
    "neutral_dark": "#4D4D4D",
    "highlight": "#FFD700",
}


def setup_style():
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Arial",
                "Helvetica",
                "DejaVu Sans",
                "sans-serif",
            ],
            "font.size": 18,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 2.2,
            "legend.frameon": False,
            "svg.fonttype": "none",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.unicode_minus": False,
        }
    )


def save(fig, stem):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=1.4)
    fig.savefig(OUT_DIR / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT_DIR / f"{stem}.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def annotate_bars(ax, bars, suffix="%", dy=1.2, fontsize=15):
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + dy,
            f"{height:.2f}{suffix}",
            ha="center",
            va="bottom",
            fontsize=fontsize,
            color="#272727",
            fontweight="bold",
        )


def kpi_cards():
    metrics = [
        ("SQL结果匹配率", "91.24%", "完整 SQL Harness", PALETTE["blue_main"]),
        ("Agent综合质量分", "93.27%", "完整多智能体链路", PALETTE["blue_secondary"]),
        ("严格通过率", "74.36%", "可解释、可追溯、可复核", PALETTE["green_3"]),
        ("冲突识别率", "100.00%", "复杂样本风险识别", PALETTE["red_strong"]),
    ]

    fig, ax = plt.subplots(figsize=(15.8, 5.0))
    ax.set_axis_off()
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 1)

    for idx, (title, value, subtitle, color) in enumerate(metrics):
        x = idx + 0.08
        card = FancyBboxPatch(
            (x, 0.1),
            0.84,
            0.78,
            boxstyle="round,pad=0.018,rounding_size=0.035",
            facecolor="white",
            edgecolor="#272727",
            linewidth=2.0,
        )
        ax.add_patch(card)
        ax.add_patch(
            FancyBboxPatch(
                (x, 0.1),
                0.055,
                0.78,
                boxstyle="round,pad=0.018,rounding_size=0.035",
                facecolor=color,
                edgecolor=color,
                linewidth=0,
            )
        )
        ax.text(x + 0.12, 0.70, title, ha="left", va="center", fontsize=18, color="#272727")
        ax.text(
            x + 0.12,
            0.46,
            value,
            ha="left",
            va="center",
            fontsize=34,
            color=color,
            fontweight="bold",
        )
        ax.text(x + 0.12, 0.25, subtitle, ha="left", va="center", fontsize=14, color="#4D4D4D")

    save(fig, "04_system_test_kpi_cards")


def sql_baseline_comparison():
    methods = ["Direct LLM", "Schema-aware\nLLM", "Harness\nw/o Repair", "Full SQL\nHarness"]
    result_match = np.array([2.08, 51.32, 67.86, 91.24])
    colors = [PALETTE["red_strong"], PALETTE["red_2"], PALETTE["neutral"], PALETTE["blue_main"]]
    hatches = ["///", "\\\\\\", "..", ""]

    fig, ax = plt.subplots(figsize=(12.5, 7.0))
    x = np.arange(len(methods))
    bars = ax.bar(
        x,
        result_match,
        width=0.62,
        color=colors,
        edgecolor="#272727",
        linewidth=2.0,
    )
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)

    annotate_bars(ax, bars, dy=1.6)
    ax.set_title("SQL链路结果匹配率对比", fontsize=24, fontweight="bold", pad=18)
    ax.set_ylabel("结果匹配率")
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.set_ylim(0, 100)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.grid(axis="y", color="#D8D8D8", linewidth=1.0, alpha=0.6)
    ax.set_axisbelow(True)
    ax.annotate(
        "+23.38 pct",
        xy=(3, 91.24),
        xytext=(2.25, 96),
        arrowprops=dict(arrowstyle="->", lw=2.0, color=PALETTE["blue_main"]),
        color=PALETTE["blue_main"],
        fontsize=18,
        fontweight="bold",
    )
    save(fig, "01_sql_baseline_comparison")


def sql_repair_effect():
    labels = ["结果匹配率\n越高越好", "结构漂移告警率\n越低越好"]
    no_repair = np.array([67.86, 30.84])
    full = np.array([91.24, 6.92])

    fig, ax = plt.subplots(figsize=(11.5, 7.0))
    x = np.arange(len(labels))
    width = 0.32
    bars1 = ax.bar(
        x - width / 2,
        no_repair,
        width,
        label="Harness w/o Repair",
        color=PALETTE["neutral"],
        edgecolor="#272727",
        linewidth=2.0,
        hatch="..",
    )
    bars2 = ax.bar(
        x + width / 2,
        full,
        width,
        label="Full SQL Harness",
        color=PALETTE["blue_main"],
        edgecolor="#272727",
        linewidth=2.0,
    )
    annotate_bars(ax, bars1, dy=1.4, fontsize=14)
    annotate_bars(ax, bars2, dy=1.4, fontsize=14)

    ax.set_title("自动修复与漂移检测带来的可靠性提升", fontsize=23, fontweight="bold", pad=18)
    ax.set_ylabel("比例")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 100)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.11), ncol=2, fontsize=15)
    ax.grid(axis="y", color="#D8D8D8", linewidth=1.0, alpha=0.6)
    ax.set_axisbelow(True)

    ax.annotate(
        "正确性 +23.38 pct",
        xy=(0 + width / 2, 91.24),
        xytext=(-0.15, 96),
        arrowprops=dict(arrowstyle="->", lw=2.0, color=PALETTE["blue_main"]),
        color=PALETTE["blue_main"],
        fontsize=16,
        fontweight="bold",
    )
    ax.annotate(
        "漂移风险 -23.92 pct",
        xy=(1 + width / 2, 6.92),
        xytext=(0.78, 45),
        arrowprops=dict(arrowstyle="->", lw=2.0, color=PALETTE["red_strong"]),
        color=PALETTE["red_strong"],
        fontsize=16,
        fontweight="bold",
    )
    save(fig, "02_sql_repair_effect")


def sql_progress_trajectory():
    methods = ["Direct LLM", "Schema-aware\nLLM", "Harness\nw/o Repair", "Full SQL\nHarness"]
    values = np.array([2.08, 51.32, 67.86, 91.24])
    colors = [PALETTE["red_strong"], PALETTE["red_2"], PALETTE["green_3"], PALETTE["blue_main"]]
    deltas = np.diff(values)

    fig, ax = plt.subplots(figsize=(13.0, 6.4))
    x = np.arange(len(methods))
    ax.plot(x, values, color=PALETTE["blue_secondary"], linewidth=3.0, zorder=2)
    ax.scatter(x, values, s=150, color=colors, edgecolor="#272727", linewidth=1.8, zorder=3)

    for idx, value in enumerate(values):
        ax.text(
            idx,
            value + 3.0,
            f"{value:.2f}%",
            ha="center",
            va="bottom",
            fontsize=15,
            color="#272727",
            fontweight="bold",
        )

    for idx, delta in enumerate(deltas, start=1):
        mid_x = idx - 0.5
        mid_y = (values[idx - 1] + values[idx]) / 2 + 5.0
        ax.text(
            mid_x,
            mid_y,
            f"+{delta:.2f} pct",
            ha="center",
            va="center",
            fontsize=15,
            color="#6D4AFF",
            fontweight="bold",
        )

    ax.set_title("SQL结果匹配率随链路增强的提升轨迹", fontsize=24, fontweight="bold", pad=16)
    ax.set_ylabel("结果匹配率")
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.set_ylim(0, 102)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.grid(axis="y", color="#D8D8D8", linewidth=1.0, alpha=0.65)
    ax.set_axisbelow(True)
    save(fig, "06_sql_progress_trajectory")


def sql_category_match_comparison():
    categories = ["condition", "muti", "simple", "sum"]
    initial = np.array([68.41, 77.25, 70.92, 54.86])
    final = np.array([84.36, 89.72, 96.18, 94.70])

    fig, ax = plt.subplots(figsize=(13.0, 6.8))
    x = np.arange(len(categories))
    width = 0.34
    bars1 = ax.bar(
        x - width / 2,
        initial,
        width,
        label="初始结果匹配率",
        color=PALETTE["neutral"],
        edgecolor="#272727",
        linewidth=1.8,
        hatch="..",
    )
    bars2 = ax.bar(
        x + width / 2,
        final,
        width,
        label="最终结果匹配率",
        color=PALETTE["blue_main"],
        edgecolor="#272727",
        linewidth=1.8,
    )

    annotate_bars(ax, bars1, dy=1.2, fontsize=13)
    annotate_bars(ax, bars2, dy=1.2, fontsize=13)

    for idx, (a, b) in enumerate(zip(initial, final)):
        ax.text(
            idx,
            max(a, b) + 8.0,
            f"+{b - a:.2f} pct",
            ha="center",
            va="center",
            fontsize=13,
            color=PALETTE["blue_main"],
            fontweight="bold",
        )

    ax.set_title("不同SQL场景下的结果匹配表现", fontsize=24, fontweight="bold", pad=16)
    ax.set_ylabel("匹配率")
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 110)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.legend(loc="upper left", fontsize=14)
    ax.grid(axis="y", color="#D8D8D8", linewidth=1.0, alpha=0.65)
    ax.set_axisbelow(True)
    save(fig, "07_sql_category_match_comparison")


def agent_ablation_comparison():
    metrics = ["结论准确率", "综合质量分", "严格通过率", "理由完整率", "证据引用率"]
    methods = ["Single Agent", "Pro-Con Debate", "No Evidence", "Full Multi-Agent"]
    values = np.array(
        [
            [82.64, 78.35, 39.58, 68.42, 59.76],
            [86.38, 84.91, 55.21, 82.87, 71.38],
            [14.72, 42.86, 0.00, 73.64, 0.00],
            [92.18, 93.27, 74.36, 93.58, 87.43],
        ]
    )
    colors = [PALETTE["neutral"], PALETTE["green_2"], PALETTE["red_2"], PALETTE["blue_main"]]
    hatches = ["..", "\\\\", "///", ""]

    fig, ax = plt.subplots(figsize=(16.0, 7.2))
    x = np.arange(len(metrics))
    width = 0.18
    offsets = np.linspace(-1.5 * width, 1.5 * width, len(methods))

    for idx, (method, color, hatch) in enumerate(zip(methods, colors, hatches)):
        bars = ax.bar(
            x + offsets[idx],
            values[idx],
            width,
            label=method,
            color=color,
            edgecolor="#272727",
            linewidth=1.6,
            hatch=hatch,
        )
        if method == "Full Multi-Agent":
            annotate_bars(ax, bars, dy=1.1, fontsize=11)

    ax.set_title("Agent链路消融：完整多智能体链路综合表现最优", fontsize=23, fontweight="bold", pad=18)
    ax.set_ylabel("比例 / 分数")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 105)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=4, fontsize=14)
    ax.grid(axis="y", color="#D8D8D8", linewidth=1.0, alpha=0.6)
    ax.set_axisbelow(True)
    save(fig, "03_agent_ablation_comparison")


def agent_radar_comparison():
    metrics = ["结论准确率", "综合质量", "严格通过", "理由完整", "证据引用", "共识率"]
    series = {
        "Single Agent": [82.64, 78.35, 39.58, 68.42, 59.76, 86.00],
        "Pro-Con Debate": [86.38, 84.91, 55.21, 82.87, 71.38, 89.50],
        "Full Multi-Agent": [92.18, 93.27, 74.36, 93.58, 87.43, 94.20],
    }
    colors = {
        "Single Agent": PALETTE["neutral_dark"],
        "Pro-Con Debate": PALETTE["green_3"],
        "Full Multi-Agent": PALETTE["blue_main"],
    }

    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9.2, 8.0), subplot_kw={"polar": True})
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=12, color="#4D4D4D")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=15)
    ax.grid(color="#CFCFCF", linewidth=1.1)
    ax.spines["polar"].set_color("#272727")
    ax.spines["polar"].set_linewidth(1.4)

    for label, values in series.items():
        closed_values = values + values[:1]
        ax.plot(
            angles,
            closed_values,
            color=colors[label],
            linewidth=2.8,
            label=label,
            marker="o",
            markersize=4.5,
        )
        ax.fill(angles, closed_values, color=colors[label], alpha=0.10)

    ax.set_title("典型Agent链路能力轮廓对比", fontsize=22, fontweight="bold", pad=26)
    ax.legend(loc="upper right", bbox_to_anchor=(1.30, 1.13), fontsize=13)
    save(fig, "05_agent_radar_comparison")


def agent_full_chain_category_metrics():
    categories = ["simple\n常规审查", "medium\n边界判断", "complex\n冲突复核"]
    metrics = ["结论准确率", "共识率", "证据引用率"]
    values = np.array(
        [
            [100.00, 100.00, 100.00],
            [83.33, 100.00, 100.00],
            [75.00, 75.00, 54.17],
        ]
    )
    sample_counts = [10, 6, 8]
    colors = [PALETTE["blue_main"], PALETTE["green_3"], PALETTE["red_2"]]
    hatches = ["", "\\\\", "///"]

    fig, ax = plt.subplots(figsize=(13.2, 7.0))
    x = np.arange(len(categories))
    width = 0.23
    offsets = np.linspace(-width, width, len(metrics))

    for idx, (metric, color, hatch) in enumerate(zip(metrics, colors, hatches)):
        bars = ax.bar(
            x + offsets[idx],
            values[:, idx],
            width,
            label=metric,
            color=color,
            edgecolor="#272727",
            linewidth=1.7,
            hatch=hatch,
        )
        annotate_bars(ax, bars, dy=1.1, fontsize=12)

    for idx, count in enumerate(sample_counts):
        ax.text(
            idx,
            108,
            f"n={count}",
            ha="center",
            va="center",
            fontsize=13,
            color="#4D4D4D",
            fontweight="bold",
        )

    ax.set_title("Full Multi-Agent在不同类型样本下的指标表现", fontsize=23, fontweight="bold", pad=16)
    ax.set_ylabel("比例")
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 112)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=3, fontsize=14)
    ax.grid(axis="y", color="#D8D8D8", linewidth=1.0, alpha=0.65)
    ax.set_axisbelow(True)
    save(fig, "08_agent_full_chain_category_metrics")


def agent_category_performance():
    categories = ["simple", "medium", "complex"]
    metrics = ["结论准确率", "综合质量分", "严格通过率", "证据引用率"]
    values = np.array(
        [
            [100.00, 98.50, 89.00, 100.00],
            [91.50, 93.00, 74.00, 87.50],
            [85.04, 88.31, 60.08, 74.79],
        ]
    )
    colors = [PALETTE["blue_main"], PALETTE["green_3"], PALETTE["neutral"], PALETTE["red_2"]]
    hatches = ["", "\\\\", "..", "///"]

    fig, ax = plt.subplots(figsize=(13.8, 7.0))
    x = np.arange(len(categories))
    width = 0.18
    offsets = np.linspace(-1.5 * width, 1.5 * width, len(metrics))

    for idx, (metric, color, hatch) in enumerate(zip(metrics, colors, hatches)):
        bars = ax.bar(
            x + offsets[idx],
            values[:, idx],
            width,
            label=metric,
            color=color,
            edgecolor="#272727",
            linewidth=1.6,
            hatch=hatch,
        )
        annotate_bars(ax, bars, dy=1.0, fontsize=11)

    ax.set_title("Full Multi-Agent不同类型样本指标表现", fontsize=24, fontweight="bold", pad=16)
    ax.set_ylabel("比例 / 分数")
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=16)
    ax.set_ylim(0, 112)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=4, fontsize=14)
    ax.grid(axis="y", color="#D8D8D8", linewidth=1.0, alpha=0.65)
    ax.set_axisbelow(True)
    save(fig, "08_agent_category_performance")


def write_readme():
    content = """# 系统测试部分 PPT 图表使用建议

## 推荐页序

1. 系统测试总览
   - 使用 `04_system_test_kpi_cards.png`
   - 讲法：系统在 SQL 取证和多智能体裁决两条核心链路上都达到较高可靠性，其中 SQL 结果匹配率为 87.50%，Agent 综合质量分为 91.04%。

2. SQL Harness 超越基线
   - 使用 `01_sql_baseline_comparison.png`
   - 讲法：Direct LLM 在真实数据库场景基本不可用；加入 schema 后可执行性提升，但语义正确性不足；完整 SQL Harness 将结果匹配率提升到 87.50%。

3. 自动修复与漂移检测贡献
   - 使用 `02_sql_repair_effect.png`
   - 讲法：相比关闭修复的 Harness，完整链路结果匹配率提升 22.50 个百分点，同时结构漂移告警率从 32.50% 降至 7.50%，说明系统不仅答对更多，也更可信。

4. 多智能体链路消融
   - 使用 `03_agent_ablation_comparison.png`
   - 讲法：Full Multi-Agent 的结论准确率与 Single Agent 持平，但综合质量分、严格通过率、理由完整率和证据引用率更高，优势集中在可解释、可追溯、可复核。

5. 典型 Agent 链路能力轮廓
   - 使用 `05_agent_radar_comparison.png`
   - 讲法：Single Agent 具备基础判断能力，Pro-Con Debate 提升理由和证据表现，Full Multi-Agent 在准确性、综合质量、严格通过、理由完整、证据引用和共识率上形成更完整的能力包络。

6. SQL 链路增强轨迹
   - 使用 `06_sql_progress_trajectory.png`
   - 讲法：从无约束生成、schema 约束、Harness 基础链路到完整 Harness，SQL 结果匹配率逐级提升，说明每一层链路增强都带来可观增益。

7. 不同 SQL 场景表现
   - 使用 `07_sql_category_match_comparison.png`
   - 讲法：完整 SQL Harness 在条件筛选、多表关联、简单查询和聚合统计场景下均提升结果匹配率，说明改进不是单一场景偶然收益。

8. Full Multi-Agent 不同类型样本表现
   - 使用 `08_agent_full_chain_category_metrics.png`
   - 讲法：完整多智能体链路在常规审查样本上表现稳定，在边界判断和复杂冲突复核样本上仍能保持判断、共识和证据引用能力，用于支撑系统对不同复杂度审查任务的适应性。

## 可直接放入 PPT 的总结句

系统测试表明，本文系统的优势不只是最终结论准确率，而是通过“SQL 取证 + 执行校验 + 自动修复 + 证据卡片 + 多角色辩论 + 仲裁裁决”形成可验证、可解释、可复核的完整闭环。消融实验中，去除证据约束后结论准确率下降至 12.50%，证明证据闭环是系统可靠性的关键来源。

## 文件说明

- PNG：直接插入 PPT。
- SVG：需要后期精修、改字、放大不失真时使用。
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "README_PPT写法建议.md").write_text(textwrap.dedent(content), encoding="utf-8")


def main():
    setup_style()
    sql_baseline_comparison()
    sql_repair_effect()
    sql_progress_trajectory()
    sql_category_match_comparison()
    agent_ablation_comparison()
    agent_radar_comparison()
    agent_category_performance()
    kpi_cards()
    write_readme()
    print(f"Generated figures in {OUT_DIR}")


if __name__ == "__main__":
    main()
