"""Same route, by coincidence: the HKU COMP1110 same-route simulator.

Run everything through one command from the repository root:

    python -m sameroute                 # list every command
    python -m sameroute ui              # watch a run in progress, or look at its results, in the browser

Layout
    sameroute/config.py     every setting and number the simulation uses, and where files live
    sameroute/world/        the map: building it, places, routing and walking, intersections, groups
    sameroute/people.py     the synthetic population
    sameroute/sim/          the simulations: Agent World, live world, random walking, preflight checks
    sameroute/analysis/     the analyses: following, Markov chains, tests, the followers, shared turns
    sameroute/figures/      the paper figures (written to graphs/)
    sameroute/export/       website data, the amenity heat map, results of a stopped live run
    sameroute/ui/           the browser UI
"""
