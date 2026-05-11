from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import patches


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs"

plt.rcParams.update(
    {
        "font.family": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans", "sans-serif"],
        "font.size": 11,
        "svg.fonttype": "none",
        "figure.facecolor": "white",
    }
)

BLUE = "#0F4D92"
RED = "#B64342"
RED_LIGHT = "#FFF7F6"
GOLD = "#C58B2B"
GOLD_LIGHT = "#FFF9EA"
TEXT = "#243447"
MUTED = "#64748B"
BORDER = "#D8D1C8"


def box(ax, x, y, w, h, title, lines, edge, face):
    rect = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.014",
        linewidth=1.45,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(rect)
    ax.text(x + 0.018, y + h - 0.035, title, ha="left", va="top", fontsize=11.5, fontweight="bold", color=TEXT)
    ax.text(x + 0.018, y + h - 0.080, "\n".join(lines), ha="left", va="top", fontsize=8.4, color=MUTED, linespacing=1.6)


def main():
    fig, ax = plt.subplots(figsize=(13.5, 5.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    outer = patches.FancyBboxPatch(
        (0.03, 0.08),
        0.94,
        0.84,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.2,
        edgecolor=BORDER,
        facecolor="#FFFFFF",
    )
    ax.add_patch(outer)

    ax.text(0.05, 0.86, "工程目录与模块划分图", fontsize=17, fontweight="bold", color=TEXT, ha="left", va="center")
    ax.text(
        0.05,
        0.815,
        "按照“交互展示层—服务接口层—智能评审编排层—多智能体协同层—知识与数据支撑层—贯穿可信评审机制”组织工程模块",
        fontsize=9.5,
        color=MUTED,
        ha="left",
        va="center",
    )

    w, h = 0.25, 0.20
    xs = [0.055, 0.375, 0.695]
    y_top = 0.56
    y_bottom = 0.23

    box(
        ax,
        xs[0],
        y_top,
        w,
        h,
        "1 交互展示层  frontend/",
        [
            "App.vue",
            "components/*.vue",
            "输入、证据、画像、辩论、复核、历史、PDF下载",
        ],
        RED,
        RED_LIGHT,
    )
    box(
        ax,
        xs[1],
        y_top,
        w,
        h,
        "2 服务接口层  api/",
        [
            "api/main.py",
            "intent / debate / stream / sessions / review",
            "FastAPI接口与SSE过程事件",
        ],
        RED,
        RED_LIGHT,
    )
    box(
        ax,
        xs[2],
        y_top,
        w,
        h,
        "3 智能评审编排层",
        [
            "intent/  policy/  cognition/",
            "text2sql/  evidence/  reports/",
            "规则加载、T2SQL取证、证据标准化、仲裁报告",
        ],
        RED,
        RED_LIGHT,
    )

    box(
        ax,
        xs[0],
        y_bottom,
        w,
        h,
        "4 多智能体协同层  agents/",
        [
            "agent_*.py",
            "debate_orchestrator.py",
            "严格、宽松、探索、经验、审计、仲裁Agent",
        ],
        GOLD,
        GOLD_LIGHT,
    )
    box(
        ax,
        xs[1],
        y_bottom,
        w,
        h,
        "5 知识与数据支撑层",
        [
            "policies/  dicts/  data/",
            "schema_struct.sql  config/database.py",
            "政策规则、Schema、业务字典、业务数据、会话存储",
        ],
        GOLD,
        GOLD_LIGHT,
    )
    box(
        ax,
        xs[2],
        y_bottom,
        w,
        h,
        "6 贯穿可信评审机制",
        [
            "evidence/  text2sql/  agents/  reports/",
            "人工复核接口  generated_reports/",
            "证据约束、SQL修复、冲突检测、保守仲裁、全链路留痕",
        ],
        GOLD,
        GOLD_LIGHT,
    )

    ax.text(
        0.50,
        0.13,
        "蓝色/红色模块侧重系统主动流程，黄色模块侧重证据、数据与可信保障；各层通过会话编号、证据编号和报告路径关联。",
        ha="center",
        va="center",
        fontsize=9.5,
        color=BLUE,
        fontweight="bold",
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "engineering_module_layers.svg", bbox_inches="tight", pad_inches=0.10)
    fig.savefig(OUT_DIR / "engineering_module_layers.png", dpi=300, bbox_inches="tight", pad_inches=0.10)
    plt.close(fig)
    print(f"Saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
