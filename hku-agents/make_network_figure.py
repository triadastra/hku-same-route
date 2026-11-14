"""Paper figure for the preprocessing: the walking network as decision points.

  graphs/intersections.pdf  (a) every real intersection, coloured by how many roads it has;
                            (b) a close-up near HKU station: the map's raw junctions against the merged
                                intersections, with each road out of an intersection drawn as a short tick.

Run:  python hku-agents/make_network_figure.py      (needs matplotlib)
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

from decisions import Decisions
from make_figures import save
from world import World, xy

COLOURS = {3: "#2a78d6", 4: "#eb6834", 5: "#1baf7a", 6: "#eda100"}
INK, MUTED, STREET = "#1f2423", "#6b7370", "#c9cecb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42, "text.color": INK})


def main():
    w = World()
    D = Decisions(w)
    lines = [[xy(*p) for p in E["geom"]] for E in w.edges]
    dec = [c for c in range(len(D.arms)) if D.is_decision[c]]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.6), gridspec_kw={"width_ratios": [1.55, 1]})

    a.add_collection(LineCollection(lines, colors=STREET, linewidths=0.35, zorder=1))
    for n in (3, 4, 5, 6):
        pts = [D.centre[c] for c in dec if min(len(D.arms[c]), 6) == n]
        a.scatter([p[0] for p in pts], [p[1] for p in pts], s=7 if n == 3 else 10, c=COLOURS[n], linewidths=0, zorder=3,
                  label=f"{n}{'+' if n == 6 else ''} roads ({len(pts)})")
    a.autoscale(); a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    for s in a.spines.values():
        s.set_visible(False)
    a.legend(frameon=False, fontsize=7, loc="lower right", title="Intersections people decide at", title_fontsize=7,
             markerscale=1.6, handletextpad=0.3)
    a.set_title("(a) Decision points", fontsize=8, loc="left")

    # close-up near HKU station and University Street
    cx, cy = xy(22.28320, 114.13690)
    half_w, half_h = 140, 120
    box = (cx - half_w, cx + half_w, cy - half_h, cy + half_h)
    a.add_patch(plt.Rectangle((box[0], box[2]), 2 * half_w, 2 * half_h, fill=False, ec=INK, lw=0.6, zorder=4))
    b.add_collection(LineCollection(lines, colors=STREET, linewidths=0.8, zorder=1))
    raw = [n for n in range(len(w.adj)) if len(w.adj[n]) >= 3]
    b.scatter([w.xy[n][0] for n in raw], [w.xy[n][1] for n in raw], s=5, c=MUTED, linewidths=0, zorder=2)
    for c in dec:
        x, y = D.centre[c]
        if not (box[0] - 30 < x < box[1] + 30 and box[2] - 30 < y < box[3] + 30):
            continue
        col = COLOURS[min(len(D.arms[c]), 6)]
        r = max(6.0, max(math.dist(w.xy[m], (x, y)) for m in D.members[c]) + 3)
        b.add_patch(plt.Circle((x, y), r, fc=col, ec="white", lw=0.6, alpha=0.35, zorder=3))
        for A in D.arms[c]:
            h = A["heading"]
            b.plot([x + r * math.cos(h), x + (r + 10) * math.cos(h)], [y + r * math.sin(h), y + (r + 10) * math.sin(h)],
                   color=col, lw=1.4, solid_capstyle="round", zorder=4)
    b.set_xlim(box[0], box[1]); b.set_ylim(box[2], box[3]); b.set_aspect("equal"); b.set_xticks([]); b.set_yticks([])
    for s in b.spines.values():
        s.set_edgecolor(INK); s.set_linewidth(0.6)
    b.plot([box[0] + 12, box[0] + 62], [box[2] + 12, box[2] + 12], color=INK, lw=1.4, solid_capstyle="butt", zorder=6)
    b.text(box[0] + 37, box[2] + 16, "50 m", ha="center", va="bottom", fontsize=7, zorder=6)
    b.legend(handles=[Line2D([], [], ls="", marker="o", ms=3, mfc=MUTED, mec=MUTED, label=f"map junctions ({len(raw):,} in all)"),
                      Line2D([], [], ls="", marker="o", ms=8, mfc="#2a78d655", mec="white", label="merged intersection"),
                      Line2D([], [], color=INK, lw=1.4, label="a road out of it")],
             frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=1, borderpad=0.2)
    b.set_title("(b) Near HKU station: raw junctions and merged intersections", fontsize=8, loc="left")
    fig.tight_layout(w_pad=0.8)
    save(fig, "intersections")
    print(f"{len(raw)} map junctions -> {len(dec)} decision intersections")


if __name__ == "__main__":
    main()
