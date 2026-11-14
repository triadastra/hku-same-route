"""The constructed map as a paper figure, drawn with seaborn: the walking network and every place on it.

  graphs/constructed-map.pdf   streets in grey, places as dots coloured by function

Run:  python hku-agents/make_map_figure.py      (needs seaborn, matplotlib, numpy, scipy)
"""
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from export_amenity_map import FUNCTIONS, GROUP
from make_figures import COLOURS, frame, load, save


def main():
    places, lines = load()
    names = [name for name, _ in FUNCTIONS]
    df = pd.DataFrame({"x": [p["x"] for p in places], "y": [p["y"] for p in places],
                       "Function": [names[GROUP[p["cat"]]] for p in places]})
    counts = df["Function"].value_counts()
    labels = {n: f"{n} ({counts[n]})" for n in names}
    df["Function"] = df["Function"].map(labels)

    sns.set_theme(style="white", font="DejaVu Sans", font_scale=0.7, rc={"pdf.fonttype": 42, "axes.linewidth": 0.6})
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    sns.scatterplot(data=df, x="x", y="y", hue="Function", hue_order=[labels[n] for n in names],
                    palette=COLOURS, s=9, linewidth=0.25, edgecolor="white", alpha=0.9, zorder=4, ax=ax)
    frame(ax, places, lines, "#8a938d")
    ax.set_xlabel(""); ax.set_ylabel("")
    sns.move_legend(ax, "center left", bbox_to_anchor=(1.01, 0.5), frameon=False, title=None, markerscale=1.6,
                    handletextpad=0.2)
    save(fig, "constructed-map")
    print(f"wrote graphs/constructed-map (.pdf and .png): {len(lines)} segments, {len(places)} places")


if __name__ == "__main__":
    main()
