from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import patches


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "chapter6_figures"

COLORS = {
    "blue": "#0F4D92",
    "blue_2": "#3775BA",
    "green": "#8BCF8B",
    "green_light": "#DDF3DE",
    "red": "#B64342",
    "red_light": "#F6CFCB",
    "neutral": "#F4F6F8",
    "line": "#C9D3DF",
    "text": "#243447",
    "muted": "#64748B",
    "gold": "#C58B2B",
}


plt.rcParams.update(
    {
        "font.family": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans", "sans-serif"],
        "font.size": 13,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 2,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "figure.facecolor": "white",
    }
)


def rounded_box(ax, xy, width, height, text, facecolor, edgecolor, fontsize=13, weight="bold"):
    box = patches.FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.045",
        linewidth=1.4,
        edgecolor=edgecolor,
        facecolor=facecolor,
    )
    ax.add_patch(box)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        ha="center",
        va="center",
        color=COLORS["text"],
        fontsize=fontsize,
        fontweight=weight,
        linespacing=1.25,
    )
    return box


def arrow(ax, start, end, color=COLORS["line"], lw=1.5):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(
            arrowstyle="-|>",
            lw=lw,
            color=color,
            shrinkA=8,
            shrinkB=8,
            mutation_scale=12,
        ),
    )


def save_figure(fig, stem: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.svg", bbox_inches="tight", pad_inches=0.16)
    fig.savefig(OUT_DIR / f"{stem}.png", dpi=300, bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)


def figure_6_1():
    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.95,
        "图6-1 作品特色与创新点总结",
        ha="center",
        va="center",
        fontsize=19,
        fontweight="bold",
        color=COLORS["text"],
    )
    ax.text(
        0.5,
        0.90,
        "以政策规则为起点，以数据库事实为依据，形成可解释、可复核、可归档的智能评审闭环",
        ha="center",
        va="center",
        fontsize=12,
        color=COLORS["muted"],
    )

    center = rounded_box(
        ax,
        (0.36, 0.40),
        0.28,
        0.18,
        "智策通\n政策研判系统",
        "#EEF5FF",
        COLORS["blue"],
        fontsize=17,
    )

    nodes = [
        ((0.07, 0.68), "政策规则\n结构化", "#EEF5FF", COLORS["blue"]),
        ((0.37, 0.69), "T2SQL\n自动取证", "#FFF8E8", COLORS["gold"]),
        ((0.67, 0.68), "证据卡片\n可追溯", "#F2FBF2", COLORS["green"]),
        ((0.07, 0.22), "多 Agent\n辩论仲裁", "#FCEEEE", COLORS["red"]),
        ((0.37, 0.19), "人工补证\n复核确认", "#F8FAFC", COLORS["muted"]),
        ((0.67, 0.22), "公文式 PDF\n归档留痕", "#EEF5FF", COLORS["blue_2"]),
    ]

    for xy, label, face, edge in nodes:
        rounded_box(ax, xy, 0.22, 0.13, label, face, edge)

    center_points = {
        "top_left": (0.40, 0.58),
        "top": (0.50, 0.58),
        "top_right": (0.60, 0.58),
        "bottom_left": (0.40, 0.40),
        "bottom": (0.50, 0.40),
        "bottom_right": (0.60, 0.40),
    }
    node_points = [
        ((0.29, 0.745), center_points["top_left"]),
        ((0.48, 0.69), center_points["top"]),
        ((0.67, 0.745), center_points["top_right"]),
        ((0.29, 0.285), center_points["bottom_left"]),
        ((0.48, 0.32), center_points["bottom"]),
        ((0.67, 0.285), center_points["bottom_right"]),
    ]
    for start, end in node_points:
        arrow(ax, start, end)

    ax.text(
        0.5,
        0.085,
        "创新主线：规则驱动取证  →  证据约束推理  →  多视角评议  →  人工兜底归档",
        ha="center",
        va="center",
        fontsize=13,
        color=COLORS["blue"],
        fontweight="bold",
    )

    save_figure(fig, "figure_6_1_innovation_summary")


def figure_6_3():
    fig, ax = plt.subplots(figsize=(14.5, 6.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.92,
        "图6-3 后续优化与拓展路线图",
        ha="center",
        va="center",
        fontsize=19,
        fontweight="bold",
        color=COLORS["text"],
    )
    ax.text(
        0.5,
        0.865,
        "从单政策演示系统逐步扩展为可接入真实数据、支持批量审核和风险预警的可信智能审核平台",
        ha="center",
        va="center",
        fontsize=12,
        color=COLORS["muted"],
    )

    stages = [
        ("当前系统", "完成政策识别、\nT2SQL取证、\nAgent评议闭环", COLORS["blue"]),
        ("扩展政策库", "增加政策类型、\n版本管理与规则\n变更对比", COLORS["green"]),
        ("接入真实数据", "对接政务接口，\n完善权限与脱敏\n机制", COLORS["gold"]),
        ("优化智能评审", "提升复杂SQL、\n冲突检测和仲裁\n置信度", COLORS["red"]),
        ("平台化应用", "支持批量审核、\n任务流转与风险\n预警", COLORS["blue_2"]),
    ]

    x_positions = [0.08, 0.29, 0.50, 0.71, 0.92]
    y = 0.50
    ax.plot([0.08, 0.92], [y, y], color=COLORS["line"], lw=3, solid_capstyle="round")

    for idx, ((title, desc, color), x) in enumerate(zip(stages, x_positions), start=1):
        ax.scatter([x], [y], s=560, color="white", edgecolor=color, linewidth=2.5, zorder=3)
        ax.text(x, y, str(idx), ha="center", va="center", fontsize=14, color=color, fontweight="bold", zorder=4)

        box_y = 0.58 if idx % 2 else 0.18
        rounded_box(ax, (x - 0.085, box_y), 0.17, 0.20, f"{title}\n{desc}", "#FFFFFF", color, fontsize=11)
        if idx % 2:
            arrow(ax, (x, box_y), (x, y + 0.035), color=color, lw=1.2)
        else:
            arrow(ax, (x, box_y + 0.20), (x, y - 0.035), color=color, lw=1.2)

    for start, end in zip(x_positions[:-1], x_positions[1:]):
        arrow(ax, (start + 0.055, y), (end - 0.055, y), color=COLORS["muted"], lw=1.3)

    ax.text(
        0.5,
        0.07,
        "提升方向：政策覆盖更广、取证链路更稳、数据安全更强、应用形态更贴近政务审核流程",
        ha="center",
        va="center",
        fontsize=12.5,
        color=COLORS["text"],
        fontweight="bold",
    )

    save_figure(fig, "figure_6_3_future_roadmap")


def main():
    figure_6_1()
    figure_6_3()
    print(f"Saved figures to: {OUT_DIR}")


if __name__ == "__main__":
    main()
