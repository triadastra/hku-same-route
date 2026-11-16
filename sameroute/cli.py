"""One command for everything: python -m sameroute <command> [options].

Every command runs one module's main() with the options that follow it, so

    python -m sameroute analyse following --run census_run

is exactly what `cd hku-agents && python following.py --run census_run` was before the repository was
reorganised: the same code, the same options, the same results.
`python -m sameroute <command> --help` lists a command's options.
"""
import importlib
import signal
import sys

# (command words, module, what it does, costs money). The order is the order of a full experiment.
COMMANDS = [
    ("Set up", None, None, False),
    ("build-map", "sameroute.world.build_map", "download OpenStreetMap and build data/graph.json (already done)", False),
    ("captions", "sameroute.world.captions", "write data/places.csv: a caption and aliases for every place", False),
    ("people", "sameroute.people", "make the synthetic people (e.g. --n 10000 --seed 7 --out runs/census_run/people.jsonl)", False),
    ("check", "sameroute.sim.preflight", "offline checks; --key checks the API key, --one runs one real person (< US$0.01)", False),

    ("Simulate", None, None, False),
    ("agent-world", "sameroute.sim.agent_world", "experiment 2: each person plans their day with map tools", True),
    ("live", "sameroute.sim.live_world", "experiment 3: one shared clock, everyone picks every junction", True),
    ("random-walk", "sameroute.sim.random_walk", "random place to random place, one trip per real trip (free)", False),
    ("pipeline", "sameroute.pipeline", "people -> Agent World -> summary -> website data, in one go", True),

    ("Analyse a finished run (results go to runs/<run>/analysis/)", None, None, False),
    ("analyse following", "sameroute.analysis.following", "the main analysis: being followed through k junctions, Markov chains, chi-square", False),
    ("analyse follower-rl", "sameroute.analysis.follower_rl", "the Q-learning follower (needs torch)", False),
    ("analyse arms", "sameroute.analysis.arms", "Agent World against random walking: shared turns, Markov, road use", False),
    ("analyse summary", "sameroute.analysis.summary", "the first analysis: shared turns, by hour, by group, road use", False),
    ("analyse model-tests", "sameroute.analysis.model_tests", "chain tests (chi-square, G-test), bar charts and the net-flow map", False),
    ("analyse shared-turns-table", "sameroute.analysis.shared_turns_table", "results/shared_turns.csv and .tex for the four conditions", False),
    ("analyse live-shared-turns", "sameroute.analysis.live_shared_turns", "shared turns in the live world (graphs/live-shared-turns)", False),
    ("analyse follower", "sameroute.analysis.follower", "the earlier rule-based follower (superseded by follower-rl)", False),

    ("Figures (written to graphs/)", None, None, False),
    ("figure following", "sameroute.figures.following", "following-models, -pairs, -roads, -hours", False),
    ("figure arms", "sameroute.figures.arms", "shared-turns-three-arms, markov-turns, road-use-ratio", False),
    ("figure junction-shares", "sameroute.figures.junction_shares", "junction-shares: where people leave each intersection", False),
    ("figure junction-probabilities", "sameroute.figures.junction_probabilities", "junction-probabilities: a window of the map", False),
    ("figure live-vs-agent-world", "sameroute.figures.live_vs_agent_world", "live world against the Agent World, and the paper tables", False),
    ("figure live-single", "sameroute.figures.live_single", "live-following, live-pairs, live-hours", False),
    ("figure intersections", "sameroute.figures.intersections", "intersections: every real intersection on the map", False),
    ("figure amenity", "sameroute.figures.amenity", "amenity-density and amenity-functions", False),
    ("figure map", "sameroute.figures.constructed_map", "constructed-map: streets and places", False),

    ("Export", None, None, False),
    ("export web", "sameroute.export.web", "website data for a run (runs/<run>/web/web.json)", False),
    ("export amenity-map", "sameroute.export.amenity_map", "website/amenity-heat-map.html", False),
    ("export partial-live", "sameroute.export.partial_live", "results of a live run stopped before midnight, from its checkpoint", False),

    ("Look at runs", None, None, False),
    ("ui", "sameroute.ui.server", "open the browser UI: watch a run in progress, replay it, read its results", False),
    ("status", "sameroute.runs", "list the runs in runs/ and how far each one got", False),
]
ALIASES = {"analyze": "analyse", "figures": "figure", "fig": "figure"}
TABLE = {words: (module, about, paid) for words, module, about, paid in COMMANDS if module}


def usage():
    lines = ["Same route, by coincidence: the HKU same-route simulator.", "",
             "usage: python -m sameroute <command> [options]      (python -m sameroute <command> --help for its options)"]
    for words, module, about, paid in COMMANDS:
        if module is None:
            lines += ["", words + ":"]
        else:
            lines.append(f"  {words:<31} {about}" + ("  ($)" if paid else ""))
    lines += ["", "($) costs money with --planner claude; --planner mock is free.",
              "Start here: README.md (what is where) and docs/RUNBOOK.md (the final experiments).",
              "Try it free:  python -m sameroute ui   then press 'New free run' in the browser."]
    return "\n".join(lines)


def resolve(argv):
    """The command named at the start of argv, and the options after it."""
    words = [ALIASES.get(argv[0], argv[0])] + argv[1:2] if argv else []
    if len(words) >= 2 and " ".join(words[:2]) in TABLE:
        return " ".join(words[:2]), argv[2:]
    if words and words[0] in TABLE:
        return words[0], argv[1:]
    return None, argv


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage())
        return 0
    name, rest = resolve(argv)
    if name is None:
        group = [w for w in TABLE if w.startswith(ALIASES.get(argv[0], argv[0]) + " ")]
        if group:
            print(f"'{argv[0]}' needs one of: " + ", ".join(w.split(" ", 1)[1] for w in group))
        else:
            print(f"unknown command {' '.join(argv[:2])!r}\n\n" + usage())
        return 2
    module = importlib.import_module(TABLE[name][0])
    # Ctrl+C (or Stop in the UI) must reach the simulators, which then save and stop cleanly, even when this process
    # was started in the background, where the shell would have it ignore Ctrl+C.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    sys.argv = [f"python -m sameroute {name}"] + rest    # the module's own argparse reads sys.argv
    result = module.main()
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
