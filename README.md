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
| `same-route-simulator.html` | The results website. It reads `web.json` from the same folder. |
| `web.json` | Website data exported from the run (2,000 of the 10,000 people, for the map replay). |

The full per-person output (about 440 MB) and the downloaded OpenStreetMap caches are not in the
repository; running `python pipeline.py` inside `hku-agents/` rebuilds them. Put your own Anthropic API key in
`hku-agents/.env` (never commit it).

Map data © OpenStreetMap contributors, ODbL.
