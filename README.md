# Same route, by coincidence

COMP1110 group project at HKU (Celsia, Jerry, Angie, Bryan, Michelle): *Modeling and understanding
coincidences: accidentally having the same route.*

10,000 synthetic people live one weekday on the real footpaths from Kennedy Town to Sai Ying Pun. Each
person is played by Claude Haiku 5.5 and plans their own day with map tools; every walk follows the
quickest path and records each turn. The analysis measures how often a stranger makes your same turns
in a row, within 90 seconds, purely by coincidence.

**Results website:** https://claude.ai/artifact/KwTUxCbLH9h1zDb2tTBqUp

| Path | What it is |
|---|---|
| `hku-agents/` | The simulator: map building, people, agent tools, the day runner and the analysis. Its README explains how to run everything. |
| `hku-agents/out/day1/analysis/` | Result tables from the 10,000-person run (one weekday, US$20.49, 57,530 trips). |
| `results.xlsx` | All the results in one workbook: a summary sheet with the key findings, then every table from the analysis. |
| `same-route-simulator.html` | The results website. It reads `web.json` from the same folder. |
| `amenity-heat-map.html` | Heat map of what each block is for: the 1,538 places on the map, counted per one-hectare block in eight functions. Rebuilt by `python hku-agents/export_amenity_map.py`. |
| `web.json` | Website data exported from the run (2,000 of the 10,000 people, for the map replay). |

## Repeat it

```bash
pip install -r hku-agents/requirements.txt
```

```bash
python hku-agents/pipeline.py check
```

```bash
python hku-agents/pipeline.py default
```

`check` is free and needs no key: it confirms that your copy rebuilds the published people and walks.
`default` is our setup, 10,000 people played by Claude Haiku 5.5 (about US$20, two hours); it needs your
own Anthropic API key in `hku-agents/.env` (copy `hku-agents/.env.example`; never commit it). Other modes,
including free ones and other ways of routing walks, are in `hku-agents/README.md`.

The full per-person output of the published run (about 440 MB) and the downloaded OpenStreetMap caches
are not in the repository.

Map data © OpenStreetMap contributors, ODbL.
