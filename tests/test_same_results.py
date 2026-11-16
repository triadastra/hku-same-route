"""The simulation gives exactly the results it gave before the repository was reorganised.

The fingerprints below were taken from the code as it was in hku-agents/ (commit 0b353a3), running the same free
commands. If one of these tests fails, the simulation now gives different results: find out why before trusting
any new run. If you changed the method on purpose (a setting in sameroute/config.py, the map, the people), take the
new fingerprints from the failure message and say so in docs/method.md.

    python -m unittest discover tests          # about 30 seconds, free, no API key
"""
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PEOPLE_300_SEED_7 = "176182990b7dd8554128ba8c98021299"         # python -m sameroute people --n 300 --seed 7
AGENT_WORLD_MOCK_TRIPS = "169da29dff944c7510bead417599776d"    # agent-world --planner mock on those 300 people
AGENT_WORLD_MOCK_AGENTS = "a3dc8847834c7ace6276d3e1a165612c"   # every person's record, in order of id
LIVE_MOCK_TRIPS = "a2ac3df8aa9c99218b6fb3a0a30e9890"           # live --planner mock --limit 200 on the same people
LIVE_MOCK_AGENTS = "706c9f7e69153052e11d70f915f2b10d"


def md5(*paths):
    h = hashlib.md5()
    for p in paths:
        h.update(Path(p).read_bytes())
    return h.hexdigest()


class SameResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runs = Path(cls.tmp.name)
        cls.env = {**os.environ, "SAMEROUTE_RUNS": str(cls.runs), "PYTHONHASHSEED": "0"}
        people = cls.runs / "people.jsonl"
        cls.sr("people", "--n", "300", "--seed", "7", "--out", str(people))
        cls.sr("agent-world", "--run", "aw", "--planner", "mock", "--agents", str(people))
        cls.sr("live", "--run", "lw", "--planner", "mock", "--agents", str(people), "--limit", "200")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def sr(cls, *args):
        r = subprocess.run([sys.executable, "-m", "sameroute", *args], cwd=ROOT, env=cls.env,
                           capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(f"python -m sameroute {' '.join(args)} failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        return r.stdout

    def agents(self, run):
        return sorted((self.runs / run / "agents").glob("A*.json"))

    def test_people(self):
        self.assertEqual(md5(self.runs / "people.jsonl"), PEOPLE_300_SEED_7)

    def test_agent_world(self):
        self.assertEqual(md5(self.runs / "aw" / "trips.jsonl"), AGENT_WORLD_MOCK_TRIPS)
        self.assertEqual(md5(*self.agents("aw")), AGENT_WORLD_MOCK_AGENTS)
        progress = json.loads((self.runs / "aw" / "progress.json").read_text())
        self.assertEqual((progress["status"], progress["done"]), ("finished", 300))

    def test_live_world(self):
        self.assertEqual(md5(self.runs / "lw" / "trips.jsonl"), LIVE_MOCK_TRIPS)
        self.assertEqual(md5(*self.agents("lw")), LIVE_MOCK_AGENTS)
        progress = json.loads((self.runs / "lw" / "progress.json").read_text())
        self.assertEqual(progress["status"], "finished")

    def test_census_population_matches_the_committed_one(self):
        """The 10,000 census people (seed 7) are exactly the people of runs/census_run."""
        committed = ROOT / "runs" / "census_run" / "people.jsonl.gz"
        if not committed.exists():
            self.skipTest("runs/census_run/people.jsonl.gz is not here")
        out = self.runs / "census.jsonl"
        self.sr("people", "--n", "10000", "--seed", "7", "--out", str(out))
        self.assertEqual(hashlib.md5(gzip.decompress(committed.read_bytes())).hexdigest(), md5(out))


if __name__ == "__main__":
    unittest.main()
