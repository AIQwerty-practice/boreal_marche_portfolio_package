"""Generate the presentation-ready D2 architecture PNG."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import FancyBboxPatch


def box(ax, x, y, w, h, title, subtitle="", color="#ffffff", edge="#53799e"):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.015", facecolor=color, edgecolor=edge, linewidth=1.8
        )
    )
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=10, weight="bold")
    if subtitle:
        ax.text(x + w / 2, y + h * 0.30, subtitle, ha="center", va="center", fontsize=8, color="#526579")


def arrow(ax, start, end):
    ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": "#587089", "lw": 1.8})


def main() -> int:
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.text(8, 8.55, "Boreal Marché — Three-Head Customer Intelligence Architecture", ha="center", fontsize=20, weight="bold", color="#17324d")
    ax.text(8, 8.22, "D2 verified local integration • offline preparation separated from online inference", ha="center", fontsize=10, color="#526579")

    ax.add_patch(FancyBboxPatch((0.4, 4.8), 15.2, 2.9, boxstyle="round,pad=0.02", facecolor="#f5f8fb", edgecolor="#b8c7d6"))
    ax.text(0.7, 7.35, "OFFLINE — reproducible preparation and evaluation", fontsize=12, weight="bold", color="#17324d")
    box(ax, 0.8, 5.65, 1.8, 0.8, "UCI transactions", "checksum + provenance")
    box(ax, 3.3, 5.65, 1.9, 0.8, "Bronze → Silver", "typed + audited cleaning")
    box(ax, 5.9, 5.65, 1.9, 0.8, "Gold features", "point-in-time snapshots")
    box(ax, 8.7, 6.65, 1.9, 0.55, "Head A", "retention", "#e8f4f3", "#248e89")
    box(ax, 8.7, 5.75, 1.9, 0.55, "Head B", "recommendation", "#e8f4f3", "#248e89")
    box(ax, 8.7, 4.95, 1.9, 0.50, "Head C", "corpus + index", "#e8f4f3", "#248e89")
    box(ax, 12.1, 5.65, 2.6, 0.9, "Versioned artifacts", "model • rules • corpus • MLflow", "#fff4df", "#c88417")
    arrow(ax, (2.6, 6.05), (3.3, 6.05)); arrow(ax, (5.2, 6.05), (5.9, 6.05))
    for y in (6.93, 6.03, 5.20): arrow(ax, (7.8, 6.05), (8.7, y))
    for y in (6.93, 6.03, 5.20): arrow(ax, (10.6, y), (12.1, 6.05))

    ax.add_patch(FancyBboxPatch((0.4, 0.75), 15.2, 3.5, boxstyle="round,pad=0.02", facecolor="#f5f8fb", edgecolor="#b8c7d6"))
    ax.text(0.7, 3.9, "ONLINE — typed inference and observable operations", fontsize=12, weight="bold", color="#17324d")
    box(ax, 0.9, 2.25, 2.1, 0.9, "Bilingual interface", "customer + manager flows")
    box(ax, 4.0, 1.95, 3.5, 1.5, "Typed FastAPI service", "/predict • /recommend • /chat\nhealth • ready • version • metrics", "#e8f4f3", "#248e89")
    box(ax, 8.7, 3.15, 2.2, 0.55, "Head A artifact", "41 exact features")
    box(ax, 8.7, 2.25, 2.2, 0.55, "Head B artifact", "rules + fallback")
    box(ax, 8.7, 1.35, 2.2, 0.55, "Head C tools", "retrieval + refusal")
    box(ax, 12.3, 2.65, 2.5, 0.9, "Event log + metrics", "D4 durable storage + dashboard", "#fff4df", "#c88417")
    box(ax, 12.3, 1.25, 2.5, 0.75, "Authentication + CI/CD", "D4 implementation", "#fff4df", "#c88417")
    arrow(ax, (3.0, 2.7), (4.0, 2.7))
    for y in (3.42, 2.52, 1.62): arrow(ax, (7.5, 2.7), (8.7, y))
    arrow(ax, (10.9, 2.52), (12.3, 3.05))
    ax.text(8, 0.35, "Current claim: verified local stub. Public deployment, authentication, durable telemetry, and monitoring remain pending.", ha="center", fontsize=9, color="#526579")

    output = Path("reports/d2/figures/system_architecture.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
