"""
Brand X budget reallocation: optimiser, sensitivity and charts.

Case: Novartis Accelerated Leadership Program, IIM Bangalore campus selection, Nov 2026.
All inputs come from the case data pack (Exhibits 1 to 3). Anything marked ASSUMPTION is mine.

Run:  python budget_optimizer.py          (Windows: py -3 budget_optimizer.py)
Out:  output/allocation.csv, output/summary.txt and seven charts (PNG)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linprog

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

# ----------------------------------------------------------------------------
# 1. Case data
# ----------------------------------------------------------------------------
MARKETS = ["A", "B", "C", "D", "E"]
CHANNELS = ["Field force", "Digital", "Medical events", "Patient support"]

SALES = {"A": 120, "B": 95, "C": 80, "D": 60, "E": 45}             # USD m, last year
GROWTH = {"A": .14, "B": .20, "C": .06, "D": .05, "E": .22}        # last year
GROWTH_PRIOR = {"A": .20, "B": .24, "C": .26, "D": .25, "E": .30}  # year before
BUDGET = {"A": 14, "B": 11, "C": 15, "D": 12, "E": 8}              # USD m
COMPETITOR = {"A": False, "B": False, "C": True, "D": True, "E": False}

MIX = {  # Exhibit 2, share of each market's budget
    "A": [.55, .15, .20, .10],
    "B": [.50, .20, .20, .10],
    "C": [.60, .10, .20, .10],
    "D": [.62, .08, .20, .10],
    "E": [.40, .30, .15, .15],
}

# Exhibit 3: incremental sales per USD 1 (next dollar, indicative)
RETURN = {"Field force": 1.8, "Digital": 3.1, "Medical events": 1.5, "Patient support": 2.4}
FIELD_FLAT_ABOVE = 0.55     # field force return is flat above ~55% of budget
DIGITAL_FALLS_ABOVE = 0.30  # digital return falls above ~30% of budget

# ----------------------------------------------------------------------------
# 2. Assumptions (all mine, all adjustable)
# ----------------------------------------------------------------------------
MOVE_CAP = 0.25             # case rule: no more than 25% of a market's budget moves in a year
HOLD_MARKET_TOTALS = True   # country totals stay flat: Exhibit 3 has no returns by market
FIELD_RETURN_ABOVE = 0.0    # ASSUMPTION: "flat" means the extra dollar adds nothing
DIGITAL_RETURN_ABOVE = 1.5  # ASSUMPTION: about half the return once past 30%
FIELD_FLOOR = 0.50          # ASSUMPTION: keep reps at half the budget (competitor has 2x reps)
EVENTS_FLOOR = 0.15         # ASSUMPTION: keep medical credibility; E already runs at 15%
SUPPORT_CAP = 0.15          # ASSUMPTION: no evidence beyond the level E runs at
SUPPORT_FLOOR = True        # ASSUMPTION: never cut patient support, it protects the existing base
MAX_CHANNEL_GROWTH = 2.0    # ASSUMPTION: no channel more than doubles in a year (content, review, hiring)


def market_lp(m, returns=RETURN, guardrails=True):
    """Best channel mix for one market. Returns (new allocation in USD m, gain in USD m).

    Variables: field_low, field_high, digital_low, digital_high, events, support.
    The two-piece channels are concave, so a linear programme fills the high-return piece first.
    """
    B = BUDGET[m]
    cur = np.array(MIX[m]) * B
    r = [returns["Field force"], FIELD_RETURN_ABOVE, returns["Digital"], DIGITAL_RETURN_ABOVE,
         returns["Medical events"], returns["Patient support"]]
    c = -np.array(r)                                    # linprog minimises

    A_eq, b_eq = [[1, 1, 1, 1, 1, 1]], [B]              # market total held flat
    bounds = [(0, FIELD_FLAT_ABOVE * B), (0, None), (0, DIGITAL_FALLS_ABOVE * B), (0, None),
              (0, None), (0, None)]

    # 25% rule: dollars added to channels (equal to dollars removed) <= cap x budget.
    # Linearised with one helper variable per channel for the increase.
    # x = [fl, fh, dl, dh, ev, ps, up_f, up_d, up_e, up_p]
    c = np.concatenate([c, np.zeros(4)])
    A_eq = [A_eq[0] + [0, 0, 0, 0]]
    bounds += [(0, None)] * 4
    A_ub, b_ub = [], []
    chan_vars = [(0, 1), (2, 3), (4,), (5,)]
    for k, idx in enumerate(chan_vars):                 # channel_total - up_k <= current
        row = [0.0] * 10
        for i in idx:
            row[i] = 1
        row[6 + k] = -1
        A_ub.append(row); b_ub.append(cur[k])
    A_ub.append([0] * 6 + [1, 1, 1, 1]); b_ub.append(MOVE_CAP * B)

    if guardrails:
        def add(idx, sign, limit):                      # sign=+1: total <= limit, -1: total >= limit
            row = [0.0] * 10
            for i in idx:
                row[i] = sign
            A_ub.append(row); b_ub.append(sign * limit)
        add((0, 1), -1, min(cur[0], FIELD_FLOOR * B))
        add((4,), -1, min(cur[2], EVENTS_FLOOR * B))
        add((5,), +1, max(cur[3], SUPPORT_CAP * B))
        if SUPPORT_FLOOR:
            add((5,), -1, cur[3])
        for k, idx in enumerate(chan_vars):
            add(idx, +1, MAX_CHANNEL_GROWTH * cur[k])

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    assert res.success, res.message
    x = res.x
    new = np.array([x[0] + x[1], x[2] + x[3], x[4], x[5]])
    return new, value(m, new, returns) - value(m, cur, returns)


def value(m, alloc, returns=RETURN):
    """Sales supported by an allocation, using the piecewise returns. Only differences matter."""
    B = BUDGET[m]
    f, d, e, p = alloc
    f_lo, d_lo = min(f, FIELD_FLAT_ABOVE * B), min(d, DIGITAL_FALLS_ABOVE * B)
    return (returns["Field force"] * f_lo + FIELD_RETURN_ABOVE * (f - f_lo)
            + returns["Digital"] * d_lo + DIGITAL_RETURN_ABOVE * (d - d_lo)
            + returns["Medical events"] * e + returns["Patient support"] * p)


def solve(guardrails=True, returns=RETURN):
    rows, plan = [], {}
    for m in MARKETS:
        new, gain = market_lp(m, returns, guardrails)
        cur = np.array(MIX[m]) * BUDGET[m]
        plan[m] = new
        moved = np.clip(new - cur, 0, None).sum()
        for k, ch in enumerate(CHANNELS):
            rows.append({"market": m, "channel": ch, "current_usd_m": cur[k], "new_usd_m": new[k],
                         "current_share": cur[k] / BUDGET[m], "new_share": new[k] / BUDGET[m]})
        rows.append({"market": m, "channel": "TOTAL", "current_usd_m": BUDGET[m], "new_usd_m": new.sum(),
                     "moved_usd_m": moved, "moved_share": moved / BUDGET[m], "gain_usd_m": gain})
    return pd.DataFrame(rows), plan


# ----------------------------------------------------------------------------
# 3. Diagnosis: where the 11 points of growth went
# ----------------------------------------------------------------------------
def diagnosis():
    prior = {m: SALES[m] / (1 + GROWTH[m]) for m in MARKETS}
    total_prior = sum(prior.values())
    free = [m for m in MARKETS if not COMPETITOR[m]]
    hit = [m for m in MARKETS if COMPETITOR[m]]
    g_free = sum(SALES[m] for m in free) / sum(prior[m] for m in free) - 1
    g_total = sum(SALES.values()) / total_prior - 1
    g_before = 0.24
    gap_usd = sum(prior[m] * (1 + g_free) - SALES[m] for m in hit)
    return {
        "growth_before": g_before, "growth_now": g_total, "growth_free_markets": g_free,
        "points_franchise_wide": (g_before - g_free) * 100,
        "points_c_and_d": (g_free - g_total) * 100,
        "sales_gap_c_d_usd_m": gap_usd,
        "budget_to_sales": {m: BUDGET[m] / SALES[m] for m in MARKETS},
        "dead_field_spend_usd_m": sum(max(MIX[m][0] - FIELD_FLAT_ABOVE, 0) * BUDGET[m] for m in MARKETS),
    }


# ----------------------------------------------------------------------------
# 4. Sensitivity: does the plan still win if Exhibit 3 is wrong?
# ----------------------------------------------------------------------------
def monte_carlo(plan, n=10_000, seed=7):
    """Vary each channel return by +/-30% and apply a 50-100% realisation factor to the gain."""
    rng = np.random.default_rng(seed)
    gains = np.empty(n)
    for i in range(n):
        r = {ch: RETURN[ch] * rng.uniform(0.7, 1.3) for ch in CHANNELS}
        g = sum(value(m, plan[m], r) - value(m, np.array(MIX[m]) * BUDGET[m], r) for m in MARKETS)
        gains[i] = g * rng.uniform(0.5, 1.0)
    return gains


# ----------------------------------------------------------------------------
# 5. Charts (Novartis-style navy and orange; text stays dark, colour only on marks)
# ----------------------------------------------------------------------------
INK, MUTED, GRID = "#1A1A1A", "#6B7280", "#E5E7EB"
NAVY, ORANGE = "#0B2545", "#E8540A"
CH_COL = {"Field force": "#2F64B5", "Digital": "#E8540A", "Medical events": "#7B4FA3", "Patient support": "#17A589"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})


def chart_sales_trend():
    years, sales = ["Year 1", "Year 2", "Year 3\n(last year)"], [286, 354, 400]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar(years, sales, color=[NAVY, NAVY, ORANGE], width=0.55)
    for x, (v, g) in enumerate(zip(sales, ["", "+24%", "+13%"])):
        ax.text(x, v + 8, f"USD {v}m" + (f"\n{g}" if g else ""), ha="center", fontweight="bold")
    ax.set_ylim(0, 480); ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.set_title("Net sales by year: growth almost halved", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "chart_0_sales_trend.png", dpi=200); plt.close(fig)


def bridge(plan):
    """Where the gain comes from, channel by channel, and how much rests on the saturation reading."""
    cur = {m: np.array(MIX[m]) * BUDGET[m] for m in MARKETS}
    delta = sum(plan[m] - cur[m] for m in MARKETS)                       # by channel, USD m
    dead = sum(min(max(cur[m][0] - FIELD_FLAT_ABOVE * BUDGET[m], 0), cur[m][0] - plan[m][0]) for m in MARKETS)
    b = {"Digital": delta[1] * RETURN["Digital"], "Patient support": delta[3] * RETURN["Patient support"],
         "Medical events": delta[2] * RETURN["Medical events"],
         "Field force": (delta[0] + dead) * RETURN["Field force"]}
    b["net_saturation"] = sum(b.values())
    b["dead_field_usd_m"] = dead
    b["net_uniform"] = b["net_saturation"] - dead * RETURN["Field force"]
    return b


def chart_growth_by_market():
    fig, ax = plt.subplots(figsize=(7.5, 4))
    x = np.arange(5)
    ax.bar(x - 0.2, [GROWTH_PRIOR[m] * 100 for m in MARKETS], width=0.38, color="#8FA3BF", label="Year before")
    cols = [ORANGE if COMPETITOR[m] else NAVY for m in MARKETS]
    ax.bar(x + 0.2, [GROWTH[m] * 100 for m in MARKETS], width=0.38, color=cols, label="Last year")
    for i, m in enumerate(MARKETS):
        ax.text(i - 0.2, GROWTH_PRIOR[m] * 100 + 0.6, f"{GROWTH_PRIOR[m]:.0%}", ha="center", color=MUTED)
        ax.text(i + 0.2, GROWTH[m] * 100 + 0.6, f"{GROWTH[m]:.0%}", ha="center", fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels([f"Market {m}" + ("\ncompetitor" if COMPETITOR[m] else "") for m in MARKETS])
    ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.set_ylim(0, 36)
    ax.legend(frameon=False, loc="upper center", ncol=2)
    ax.set_title("Growth by market: every market slowed, C and D far more", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "chart_1b_growth_by_market.png", dpi=200); plt.close(fig)


def chart_two_by_two():
    fig, ax = plt.subplots(figsize=(6.5, 5))
    xm, ym = 15, 13
    ax.axvline(xm, color=GRID, linewidth=1.5); ax.axhline(ym, color=GRID, linewidth=1.5)
    for m in MARKETS:
        x, y = BUDGET[m] / SALES[m] * 100, GROWTH[m] * 100
        ax.scatter(x, y, s=SALES[m] * 14, color=ORANGE if COMPETITOR[m] else NAVY, edgecolor="white", linewidth=2, zorder=3)
        ax.text(x, y, m, ha="center", va="center", color="white", fontweight="bold", zorder=4)
    ax.set_xlim(8, 23); ax.set_ylim(0, 28)
    for (x, y, t) in [(11.5, 26.5, "GROW EFFICIENTLY"), (19, 26.5, "BENCHMARK"), (19, 1.2, "FIX THE MIX"), (11.5, 1.2, "")]:
        ax.text(x, y, t, ha="center", color=MUTED, fontsize=9, fontweight="bold")
    ax.set_xlabel("Budget as % of sales  (higher = more spend behind each dollar of sales)")
    ax.set_ylabel("Sales growth last year, %")
    ax.set_title("C and D spend the most and grow the least", loc="left", fontweight="bold")
    ax.text(22.8, ym + 0.4, "Franchise growth 13%", color=MUTED, fontsize=8, ha="right")
    fig.tight_layout(); fig.savefig(OUT / "chart_1c_spend_vs_growth.png", dpi=200); plt.close(fig)


def chart_bridge(b):
    steps = [("Digital", b["Digital"]), ("Patient\nsupport", b["Patient support"]),
             ("Medical\nevents", b["Medical events"]), ("Field force\nbelow 55%", b["Field force"])]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    run = 0
    for i, (lab, v) in enumerate(steps):
        ax.bar(i, abs(v), bottom=min(run, run + v), color=NAVY if v > 0 else "#8FA3BF", width=0.6)
        ax.text(i, max(run, run + v) + 0.3, f"{v:+.1f}", ha="center", fontweight="bold")
        run += v
    ax.bar(4, b["net_saturation"], color=ORANGE, width=0.6)
    ax.text(4, b["net_saturation"] + 0.3, f"{b['net_saturation']:.1f}", ha="center", fontweight="bold")
    ax.bar(5, b["net_uniform"], color=ORANGE, width=0.6, alpha=0.55)
    ax.text(5, b["net_uniform"] + 0.3, f"{b['net_uniform']:.1f}", ha="center", fontweight="bold")
    ax.set_xticks(range(6))
    ax.set_xticklabels([s[0] for s in steps] + ["Net gain if field\nspend above 55%\nadds nothing", "Net gain if\nit still\nearns 1.8"])
    ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.set_ylim(0, 19.5)
    ax.set_title("Where the extra sales come from, USD m a year", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "chart_2b_sales_bridge.png", dpi=200); plt.close(fig)


def chart_waterfall(d):
    fig, ax = plt.subplots(figsize=(7.5, 4))
    b, f, c, n = d["growth_before"] * 100, d["points_franchise_wide"], d["points_c_and_d"], d["growth_now"] * 100
    labels = ["Growth,\nyear before", "Slowdown in\nall five markets", "Extra loss in\nC and D", "Growth,\nlast year"]
    bottoms, heights, cols = [0, b - f, n, 0], [b, f, c, n], [NAVY, "#8FA3BF", ORANGE, NAVY]
    ax.bar(labels, heights, bottom=bottoms, color=cols, width=0.55)
    for x, (bt, h, t) in enumerate(zip(bottoms, heights, [f"{b:.0f}%", f"-{f:.1f} pts", f"-{c:.1f} pts", f"{n:.0f}%"])):
        ax.text(x, bt + h + 0.5, t, ha="center", fontweight="bold")
    ax.set_ylim(0, 28); ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.set_title("C and D explain 4.5 of the 11 lost points, the rest is shared", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "chart_1_growth_waterfall.png", dpi=200); plt.close(fig)


def chart_mix(plan):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    xs, ticks = [], []
    for i, m in enumerate(MARKETS):
        for j, (tag, alloc) in enumerate([("Now", np.array(MIX[m]) * BUDGET[m]), ("Plan", plan[m])]):
            x = i * 2.6 + j; xs.append(x); ticks.append(f"{tag}")
            bottom = 0
            for k, ch in enumerate(CHANNELS):
                share = alloc[k] / BUDGET[m] * 100
                ax.bar(x, share, bottom=bottom, color=CH_COL[ch], width=0.86, edgecolor="white", linewidth=2,
                       label=ch if (i == 0 and j == 0) else None)
                ax.text(x, bottom + share / 2, f"{share:.0f}", ha="center", va="center", fontsize=9,
                        color="white", fontweight="bold")
                bottom += share
        ax.text(i * 2.6 + 0.5, 104, f"Market {m}  (${BUDGET[m]}m)", ha="center", fontweight="bold")
    ax.set_xticks(xs); ax.set_xticklabels(ticks); ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.set_ylim(0, 112)
    ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1))
    ax.set_title("Share of each market's budget by channel, % (totals unchanged)", loc="left", fontweight="bold", pad=18)
    fig.tight_layout(); fig.savefig(OUT / "chart_2_mix_before_after.png", dpi=200); plt.close(fig)


def chart_mc(gains):
    p10, p50, p90 = np.percentile(gains, [10, 50, 90])
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.hist(gains, bins=50, color=NAVY, edgecolor="white", linewidth=0.5)
    for v, t in [(p10, "P10"), (p50, "Median"), (p90, "P90")]:
        ax.axvline(v, color=ORANGE, linewidth=2)
        ax.text(v, ax.get_ylim()[1] * 0.97, f" {t}\n ${v:.1f}m", va="top", fontweight="bold")
    ax.set_xlabel("Extra net sales from the new mix, USD m"); ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.set_title(f"{(gains > 0).mean():.0%} of 10,000 runs beat today's mix", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "chart_3_sensitivity.png", dpi=200); plt.close(fig)


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    d = diagnosis()
    table, plan = solve(guardrails=True)
    table_free, plan_free = solve(guardrails=False)
    gains = monte_carlo(plan)
    table.to_csv(OUT / "allocation.csv", index=False)

    tot = table[table.channel == "TOTAL"]
    tot_free = table_free[table_free.channel == "TOTAL"]
    shares = table[table.channel != "TOTAL"].pivot(index="market", columns="channel", values="new_share")[CHANNELS]
    cur_sh = table[table.channel != "TOTAL"].pivot(index="market", columns="channel", values="current_share")[CHANNELS]
    p10, p50, p90 = np.percentile(gains, [10, 50, 90])
    lines = [
        "DIAGNOSIS",
        f"  Franchise growth {d['growth_before']:.0%} -> {d['growth_now']:.1%}",
        f"  Markets without a competitor grew {d['growth_free_markets']:.1%}",
        f"  Slowdown shared by all markets: {d['points_franchise_wide']:.1f} pts",
        f"  Extra loss in C and D: {d['points_c_and_d']:.1f} pts (USD {d['sales_gap_c_d_usd_m']:.1f}m)",
        "  Budget as % of sales: " + ", ".join(f"{m} {v:.1%}" for m, v in d["budget_to_sales"].items()),
        f"  Field spend above the 55% line: USD {d['dead_field_spend_usd_m']:.2f}m",
        "", "CURRENT MIX (% of market budget)", (cur_sh * 100).round(0).to_string(),
        "", "RECOMMENDED MIX (% of market budget)", (shares * 100).round(0).to_string(),
        "", "MOVES AND GAIN BY MARKET",
        tot[["market", "moved_usd_m", "moved_share", "gain_usd_m"]].round(2).to_string(index=False),
        f"  Total moved USD {tot.moved_usd_m.sum():.2f}m ({tot.moved_usd_m.sum() / 60:.0%} of budget)",
        f"  Gain at face value USD {tot.gain_usd_m.sum():.1f}m (+{tot.gain_usd_m.sum() / 400 * 100:.1f} pts of growth)",
        f"  Without my guardrails (25% rule only): USD {tot_free.gain_usd_m.sum():.1f}m, "
        f"USD {tot_free.moved_usd_m.sum():.1f}m moved",
        "", "SENSITIVITY (10,000 runs, returns +/-30%, 50-100% of the gain realised)",
        f"  P10 USD {p10:.1f}m | median USD {p50:.1f}m | P90 USD {p90:.1f}m | runs that beat today's mix: {(gains > 0).mean():.0%}",
    ]
    (OUT / "summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    b = bridge(plan)
    extra = ["", "BRIDGE (USD m a year)"] + [f"  {k}: {v:+.2f}" for k, v in b.items()]
    with open(OUT / "summary.txt", "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(extra))
    print("\n".join(extra))
    # Every other figure quoted in the deck, so nothing rests on hand arithmetic
    prior = {m: SALES[m] / (1 + GROWTH[m]) for m in MARKETS}
    prior2 = {m: prior[m] / (1 + GROWTH_PRIOR[m]) for m in MARKETS}
    hit, free = ["C", "D"], ["A", "B", "E"]
    grp = lambda ms, a, b: sum(a[m] for m in ms) / sum(b[m] for m in ms) - 1
    cur_ch = sum(np.array(MIX[m]) * BUDGET[m] for m in MARKETS)
    new_ch = sum(plan[m] for m in MARKETS)
    checks = ["", "DECK CHECKS",
        f"  C and D share of budget {sum(BUDGET[m] for m in hit) / 60:.0%}, of sales {sum(SALES[m] for m in hit) / 400:.0%}, "
        f"of last year's growth dollars {sum(SALES[m] - prior[m] for m in hit) / sum(SALES[m] - prior[m] for m in MARKETS):.0%}",
        f"  Growth year before: A, B, E {grp(free, prior, prior2):.1%} | C, D {grp(hit, prior, prior2):.1%}",
        f"  Growth last year:   A, B, E {grp(free, SALES, prior):.1%} | C, D {grp(hit, SALES, prior):.1%}",
        f"  Implied sales: year 1 USD {sum(prior2.values()):.0f}m, year 2 USD {sum(prior.values()):.0f}m, year 3 USD 400m",
        "  Channel totals today, USD m: " + ", ".join(f"{ch} {v:.2f} ({v / 60:.0%})" for ch, v in zip(CHANNELS, cur_ch)),
        "  Channel totals in plan, USD m: " + ", ".join(f"{ch} {v:.2f} ({v / 60:.0%})" for ch, v in zip(CHANNELS, new_ch)),
        f"  Growth points: uniform {b['net_uniform'] / 4:.1f}, saturation {b['net_saturation'] / 4:.1f}, "
        f"P10 {np.percentile(gains, 10) / 4:.1f}, P90 {np.percentile(gains, 90) / 4:.1f}",
        f"  Largest move in one market: {tot.moved_share.max():.0%} of its budget"]
    with open(OUT / "summary.txt", "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(checks))
    print("\n".join(checks))
    chart_sales_trend(); chart_growth_by_market(); chart_two_by_two(); chart_bridge(b)
    chart_waterfall(d); chart_mix(plan); chart_mc(gains)
    print(f"\nSaved to {OUT}")
