"""Regenerate the analysis figures from the round data archive.

The competition platform is offline. The official result pages that were
saved as screenshots live in each round's results/ folder; the figures built
here are reconstructions from the historical CSVs the platform distributed
each round (kept in a local archive, not in this repository), from the
figures quoted on the result pages, and from backtest logs summarized in
data/. Every figure is labeled as such.

Backtests were run with prosperity4btx 5.0.0 (the community backtester):
    prosperity4btx roundN/trader.py N --data <archive> --match-trades none

Usage:
    python analysis/figures/generate_figures.py --data-dir _sources
"""

import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Palette: categorical slots in fixed order, plus chart chrome
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SERIES_LIGHT = "#86b6ef"   # lighter step of slot 1, for an estimated value
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

CAPTION_DATA = ("Reconstruction from the round's historical data (the platform is offline). "
                "Not an official competition chart.")


def load_mid_prices(csv_path: Path, product: str):
    ts, mid = [], []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            # Empty-book ticks are recorded with mid_price 0.0: skip them.
            if row["product"] == product and row["mid_price"] and float(row["mid_price"]) > 0:
                ts.append(int(row["timestamp"]))
                mid.append(float(row["mid_price"]))
    order = np.argsort(ts)
    return np.asarray(ts)[order], np.asarray(mid)[order]


def load_all_mid_prices(csv_path: Path):
    series = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            if row["mid_price"] and float(row["mid_price"]) > 0:
                series.setdefault(row["product"], []).append(
                    (int(row["timestamp"]), float(row["mid_price"])))
    return {p: np.asarray(sorted(v)) for p, v in series.items()}


def style_axis(ax, x_thousands=False):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    if x_thousands:
        ax.xaxis.set_major_formatter(lambda x, _: f"{x / 1000:.0f}k")


def new_figure(width, height):
    fig = plt.figure(figsize=(width, height), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    return fig


# ─── Black-Scholes, same formulas as the round 4 trader ──────────────────────

def _nc(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_delta(S, K, T, sigma):
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    return _nc(d1)


# ─── Figures ─────────────────────────────────────────────────────────────────

def fig_round1(data_dir: Path, out_dir: Path):
    day0 = data_dir / "round1" / "data" / "prices_round_1_day_0.csv"
    t_p, m_p = load_mid_prices(day0, "INTARIAN_PEPPER_ROOT")
    t_o, m_o = load_mid_prices(day0, "ASH_COATED_OSMIUM")

    slope, intercept = np.polyfit(t_p, m_p, 1)
    fit = slope * t_p + intercept
    r2 = 1 - np.sum((m_p - fit) ** 2) / np.sum((m_p - np.mean(m_p)) ** 2)

    fig = new_figure(9.6, 3.6)
    ax1, ax2 = fig.subplots(1, 2)

    ax1.plot(t_p, m_p, color=SERIES[0], linewidth=1.4)
    ax1.plot(t_p, fit, color=INK_2, linewidth=1.0, linestyle=(0, (4, 3)))
    ax1.annotate(f"linear fit\nslope {slope:.4f}/tick, R² = {r2:.4f}",
                 xy=(0.05, 0.78), xycoords="axes fraction",
                 fontsize=8, color=INK_2)
    ax1.set_title("INTARIAN_PEPPER_ROOT: a deterministic trend",
                  fontsize=9.5, color=INK, loc="left")

    ax2.plot(t_o, m_o, color=SERIES[0], linewidth=1.0)
    ax2.axhline(10_000, color=INK_2, linewidth=1.0, linestyle=(0, (4, 3)))
    ax2.annotate(f"reference 10,000 (day mean {np.mean(m_o):,.1f}, std {np.std(m_o):.1f})",
                 xy=(0.05, 0.9), xycoords="axes fraction",
                 fontsize=8, color=INK_2)
    ax2.set_title("ASH_COATED_OSMIUM: mean reversion",
                  fontsize=9.5, color=INK, loc="left")

    for ax in (ax1, ax2):
        style_axis(ax, x_thousands=True)
        ax.set_xlabel("timestamp (historical day 0)", fontsize=8, color=MUTED)
    ax1.set_ylabel("mid price", fontsize=8, color=MUTED)

    fig.suptitle("Round 1, the signal in the data: two products, two regimes",
                 fontsize=11, color=INK, x=0.065, ha="left")
    fig.text(0.065, 0.005, CAPTION_DATA, fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(out_dir / "round1-two-regimes.png", facecolor=SURFACE)
    plt.close(fig)


def fig_trajectory(out_dir: Path):
    """Rank and cumulative PnL after each round, from the official result pages."""
    rounds = ["Round 1", "Round 2", "Round 3", "Round 4", "Round 5"]
    rank = [3170, 1759, 1276, 1445, 845]
    pnl = [126_709, 396_880, 92_151, 125_797, 245_000]   # round 5 total is approximate
    x = [1.0, 2.0, 3.5, 4.5, 5.5]                        # the gap marks the reset

    fig = new_figure(9.6, 3.9)
    ax1, ax2 = fig.subplots(1, 2)

    # Left: rank, lower is better so the axis is inverted
    for seg in (slice(0, 2), slice(2, 5)):
        ax1.plot(x[seg], rank[seg], color=SERIES[0], linewidth=2,
                 marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=2,
                 solid_capstyle="round")
    for xi, r in zip(x, rank):
        offset, align = ((12, -3), "left") if r == 1759 else ((0, -14), "center")
        ax1.annotate(f"#{r:,}", (xi, r), xytext=offset, textcoords="offset points",
                     ha=align, fontsize=8, color=INK_2)
    ax1.axvline(2.75, color=BASELINE, linewidth=1)
    ax1.text(2.68, 3450, "leaderboard reset", rotation=90, fontsize=7, color=MUTED,
             ha="right", va="bottom")
    ax1.text(1.5, 560, "Qualifier", ha="center", fontsize=8, color=INK_2)
    ax1.text(4.5, 560, "Final phase", ha="center", fontsize=8, color=INK_2)
    ax1.set_ylim(3600, 400)
    ax1.set_yticks([500, 1000, 1500, 2000, 2500, 3000, 3500])
    ax1.yaxis.set_major_formatter(lambda v, _: f"#{v:,.0f}")
    ax1.set_xticks(x)
    ax1.set_xticklabels(rounds)
    ax1.set_xlim(0.4, 6.1)
    ax1.set_title("Worldwide rank after each round", fontsize=9.5, color=INK, loc="left")

    # Right: cumulative PnL, restarting from zero at the reset
    colors = [SERIES[0]] * 4 + [SERIES_LIGHT]
    ax2.bar(x, pnl, width=0.22, color=colors)
    for xi, p, approx in zip(x, pnl, [False] * 4 + [True]):
        label = f"≈{p / 1000:.0f}K" if approx else f"{p / 1000:.0f}K"
        ax2.annotate(label, (xi, p), xytext=(0, 4), textcoords="offset points",
                     ha="center", fontsize=8, color=INK_2)
    ax2.axvline(2.75, color=BASELINE, linewidth=1)
    ax2.set_ylim(0, 440_000)
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v / 1000:.0f}K")
    ax2.set_xticks(x)
    ax2.set_xticklabels(rounds)
    ax2.set_xlim(0.4, 6.1)
    ax2.set_ylabel("cumulative PnL (XIRECs)", fontsize=8, color=MUTED)
    ax2.set_title("Cumulative PnL after each round", fontsize=9.5, color=INK, loc="left")
    ax2.annotate("round 5 total: about 245,000, exact\nfigure not archived before the\nplatform closed",
                 xy=(5.5, 245_000), xytext=(3.05, 330_000), fontsize=7, color=INK_2,
                 arrowprops=dict(arrowstyle="-", color=BASELINE, linewidth=0.8))

    for ax in (ax1, ax2):
        style_axis(ax)
        ax.grid(True, axis="y", color=GRID, linewidth=0.6)
        ax.grid(False, axis="x")

    fig.suptitle("Five rounds: rank and cumulative PnL, qualifier then final phase",
                 fontsize=11, color=INK, x=0.065, ha="left")
    fig.text(0.065, 0.005,
             "Figures transcribed from the official round result pages (see each round's results folder); "
             "the round 5 total is from memory, to the nearest thousand.",
             fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(out_dir / "score-and-rank-trajectory.png", facecolor=SURFACE)
    plt.close(fig)


def fig_round2_backtest(out_dir: Path):
    """v7 (round 1 code) against v8 on the three round 2 historical days, in backtest.

    The series come from two prosperity4btx runs (--match-trades none) whose
    activity logs were summarized into data/round2-backtest-v7-v8.csv.
    """
    rows = list(csv.DictReader(open(out_dir / "data" / "round2-backtest-v7-v8.csv")))
    days = ["-1", "0", "1"]

    fig = new_figure(9.6, 3.7)
    axes = fig.subplots(1, 3, sharey=True)
    for ax, day in zip(axes, days):
        r = [x for x in rows if x["day"] == day]
        t = np.array([int(x["tick"]) for x in r])
        v7 = np.array([float(x["v7_total"]) for x in r])
        v8 = np.array([float(x["v8_total"]) for x in r])
        ax.plot(t, v8, color=SERIES[1], linewidth=2, label="v8, day length fixed", solid_capstyle="round")
        ax.plot(t, v7, color=SERIES[0], linewidth=1.6, linestyle=(0, (4, 3)), label="v7, round 1 code")
        if day == "-1":
            ax.axvline(99_900, color=BASELINE, linewidth=1)
            ax.text(0.15, 0.80, "from here v7 reads\nzero remaining gain", transform=ax.transAxes,
                    fontsize=7, color=INK_2, va="bottom")
            for arr, name, dy in ((v8, "v8", 6), (v7, "v7", -14)):
                ax.annotate(f"{name} {arr[-1]:,.0f}", (t[-1], arr[-1]), xytext=(-2, dy),
                            textcoords="offset points", ha="right", fontsize=8, color=INK_2)
        else:
            ax.text(0.5, 0.90, "v7 and v8 identical to the unit", transform=ax.transAxes,
                    ha="center", fontsize=7.5, color=INK_2)
        ax.set_title(f"Round 2 historical day {day}", fontsize=9.5, color=INK, loc="left")
        style_axis(ax, x_thousands=True)
        ax.set_xlabel("timestamp", fontsize=8, color=MUTED)
    axes[0].set_ylabel("PnL over the day (XIRECs)", fontsize=8, color=MUTED)
    axes[0].yaxis.set_major_formatter(lambda v, _: f"{v / 1000:.0f}K")
    axes[2].legend(loc="lower right", fontsize=7.5, frameon=False, labelcolor=INK_2)

    fig.suptitle("Round 2, v7 against v8 in backtest: the day-length bug bites on one day out of three",
                 fontsize=11, color=INK, x=0.065, ha="left")
    fig.text(0.065, 0.005,
             "Backtest reproduction with prosperity4btx 5.0.0, --match-trades none, on the round 2 historical data. "
             "Not an official competition chart.",
             fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(out_dir / "round2-backtest-v7-vs-v8.png", facecolor=SURFACE)
    plt.close(fig)


def fig_round4(data_dir: Path, out_dir: Path):
    """Why VEV_5000 and VEV_5100 were removed from quoting in round 4."""
    day3 = data_dir / "round4" / "data" / "prices_round_4_day_3.csv"
    _, vef = load_mid_prices(day3, "VELVETFRUIT_EXTRACT")
    S = float(np.mean(vef))
    T, sigma, limit_opt, limit_vef = 4.0 / 365.0, 0.24, 300, 200
    strikes = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
    needed = [limit_opt * bs_delta(S, K, T, sigma) for K in strikes]
    # 3-day historical P&L per strike, as quoted in the round 4 trader header
    hist_pnl = {5000: -20_070, 5100: -1_617, 5200: 6_467, 5300: 9_390, 5400: 2_776, 5500: 888}

    fig = new_figure(9.6, 3.9)
    ax1, ax2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.35, 1]})

    xs = np.arange(len(strikes))
    ax1.bar(xs, needed, width=0.5, color=SERIES[0])
    ax1.axhline(limit_vef, color=INK_2, linewidth=1.0)
    ax1.text(len(strikes) - 0.5, limit_vef + 6, "VELVETFRUIT_EXTRACT position limit: 200",
             ha="right", fontsize=7.5, color=INK_2)
    for i, (K, n) in enumerate(zip(strikes, needed)):
        if K in (5000, 5100):
            ax1.annotate(f"{n:.0f}", (i, n), xytext=(0, 3), textcoords="offset points",
                         ha="center", fontsize=8, color=INK_2)
        elif K == 5200:
            ax1.annotate(f"{n:.0f}", (i, n), xytext=(0, -11), textcoords="offset points",
                         ha="center", fontsize=8, color=SURFACE)
    ax1.annotate("removed from quoting", xy=(2.5, 322), xytext=(2.5, 352),
                 ha="center", fontsize=7.5, color=INK_2,
                 arrowprops=dict(arrowstyle="-[, widthB=1.6, lengthB=0.3", color=INK_2, linewidth=0.8))
    ax1.set_xticks(xs)
    ax1.set_xticklabels([f"VEV_{K}" for K in strikes], rotation=45, ha="right", fontsize=7)
    ax1.set_ylim(0, 380)
    ax1.set_ylabel("VEF units needed to hedge 300 contracts", fontsize=8, color=MUTED)
    ax1.set_title(f"Hedge size per strike (delta × 300, VEF at {S:,.0f}, 4 days to expiry, σ = 0.24)",
                  fontsize=9.5, color=INK, loc="left")

    ks = list(hist_pnl)
    xs2 = np.arange(len(ks))
    ax2.bar(xs2, [hist_pnl[k] for k in ks], width=0.5, color=SERIES[0])
    ax2.axhline(0, color=BASELINE, linewidth=1)
    for i, k in enumerate(ks):
        v = hist_pnl[k]
        ax2.annotate(f"{v:+,}", (i, v), xytext=(0, 3 if v >= 0 else -10),
                     textcoords="offset points", ha="center", fontsize=7.5, color=INK_2)
    ax2.set_xticks(xs2)
    ax2.set_xticklabels([f"VEV_{k}" for k in ks], rotation=45, ha="right", fontsize=7)
    ax2.set_ylim(-25_000, 14_000)
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v / 1000:+.0f}K")
    ax2.set_title("Backtest P&L per strike, 3 historical days (v2)", fontsize=9.5, color=INK, loc="left")

    for ax in (ax1, ax2):
        style_axis(ax)
        ax.grid(True, axis="y", color=GRID, linewidth=0.6)
        ax.grid(False, axis="x")

    fig.suptitle("Round 4, the strikes a 200-unit underlying limit cannot hedge",
                 fontsize=11, color=INK, x=0.065, ha="left")
    fig.text(0.065, 0.005,
             "Left: deltas recomputed with the trader's own Black-Scholes code on the last historical day. "
             "Right: per-strike backtest figures quoted in the round 4 trader header. Not an official chart.",
             fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(out_dir / "round4-unhedgeable-strikes.png", facecolor=SURFACE)
    plt.close(fig)


def _round5_tiers(trader_path: Path):
    src = trader_path.read_text()

    def names(block):
        return set(re.findall(r'"([A-Z0-9_]+)"', block))
    tier1 = names(src.split("TIER1_LONG = {")[1].split("}")[0]) | \
        names(src.split("TIER1_SHORT = {")[1].split("}")[0])
    tier2 = names(src.split("TIER2_BIAS")[1].split("TIER3_SKIP")[0])
    return tier1, tier2


def fig_round5_tiers(data_dir: Path, out_dir: Path, trader_path: Path):
    """Daily price change of the 50 products over the 3 historical days, by tier."""
    days = [2, 3, 4]
    moves = {}
    for d in days:
        series = load_all_mid_prices(data_dir / "round5" / "data" / f"prices_round_5_day_{d}.csv")
        for p, arr in series.items():
            moves.setdefault(p, []).append(100 * (arr[-1, 1] - arr[0, 1]) / arr[0, 1])
    tier1, tier2 = _round5_tiers(trader_path)
    color_of = {p: SERIES[0] if p in tier1 else SERIES[1] if p in tier2 else MUTED for p in moves}
    ordered = sorted(moves, key=lambda p: -np.mean(moves[p]))
    half = (len(ordered) + 1) // 2

    fig = new_figure(9.6, 6.9)
    axes = fig.subplots(1, 2)
    for ax, chunk in zip(axes, (ordered[:half], ordered[half:])):
        for row, p in enumerate(chunk):
            ax.plot(moves[p], [row] * len(days), linestyle="none", marker="o", markersize=6,
                    color=color_of[p], markeredgecolor=SURFACE, markeredgewidth=1.2)
        ax.axvline(0, color=BASELINE, linewidth=1)
        ax.set_yticks(range(len(chunk)))
        ax.set_yticklabels(chunk, fontsize=6.5)
        ax.set_ylim(len(chunk) - 0.5, -0.5)
        ax.set_xlim(-26, 26)
        ax.set_xlabel("price change over the day, % of the opening mid", fontsize=8, color=MUTED)
        style_axis(ax)
        ax.grid(True, axis="x", color=GRID, linewidth=0.6)
        ax.grid(False, axis="y")

    handles = [plt.Line2D([], [], linestyle="none", marker="o", markersize=7, color=c, label=l)
               for c, l in ((SERIES[0], "Tier 1: same direction on all 3 days, full size"),
                            (SERIES[1], "Tier 2: 2 days out of 3, historical bias"),
                            (MUTED, "Tier 3: not traded"))]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.985, 0.955),
               ncol=3, fontsize=7.5, frameon=False, labelcolor=INK_2)
    fig.suptitle("Round 5, one dot per historical day: the directional consistency behind the tiers",
                 fontsize=11, color=INK, x=0.065, ha="left")
    fig.text(0.065, 0.005,
             CAPTION_DATA + "\nTiers are read from the submitted trader; products are sorted by mean daily change.",
             fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    fig.savefig(out_dir / "round5-tier-classification.png", facecolor=SURFACE)
    plt.close(fig)


def fig_round5(data_dir: Path, out_dir: Path):
    day4 = data_dir / "round5" / "data" / "prices_round_5_day_4.csv"
    products = [
        ("OXYGEN_SHAKE_GARLIC", "long in Tier 1"),
        ("GALAXY_SOUNDS_BLACK_HOLES", "long in Tier 1"),
        ("MICROCHIP_OVAL", "short in Tier 1"),
        ("PEBBLES_XS", "short in Tier 1"),
    ]

    fig = new_figure(9.6, 4.2)
    ax = fig.subplots()

    for (name, role), color in zip(products, [SERIES[0], SERIES[2], SERIES[3], "#e87ba4"]):
        t, m = load_mid_prices(day4, name)
        indexed = 100 * m / m[0]
        ax.plot(t, indexed, color=color, linewidth=1.6, label=name)
        ax.annotate(f"{name}\n({role})", xy=(t[-1], indexed[-1]),
                    xytext=(6, 0), textcoords="offset points",
                    fontsize=7.5, color=INK_2, va="center")

    ax.axhline(100, color=BASELINE, linewidth=0.8)
    style_axis(ax, x_thousands=True)
    ax.set_xlabel("timestamp (historical day 4)", fontsize=8, color=MUTED)
    ax.set_ylabel("mid price, indexed to 100 at day open", fontsize=8, color=MUTED)
    ax.legend(loc="upper left", fontsize=7.5, frameon=False, labelcolor=INK_2)
    ax.set_xlim(right=ax.get_xlim()[1] * 1.28)

    ax.set_title("Round 5, the signal behind the tier classification: "
                 "near-monotone intraday trends",
                 fontsize=11, color=INK, loc="left", pad=12)
    fig.text(0.065, 0.005, CAPTION_DATA, fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out_dir / "round5-tier1-trends.png", facecolor=SURFACE)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("_sources"),
                        help="local archive holding round*/data/*.csv")
    args = parser.parse_args()
    out_dir = Path(__file__).resolve().parent
    repo = out_dir.parent.parent
    fig_trajectory(out_dir)
    fig_round1(args.data_dir, out_dir)
    fig_round2_backtest(out_dir)
    fig_round4(args.data_dir, out_dir)
    fig_round5(args.data_dir, out_dir)
    fig_round5_tiers(args.data_dir, out_dir, repo / "round5" / "trader.py")
    print(f"Figures written to {out_dir}")


if __name__ == "__main__":
    main()
