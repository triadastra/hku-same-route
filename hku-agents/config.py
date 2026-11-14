"""Shared settings for the HKU same-route experiment."""
import os
from pathlib import Path

ROOT = Path(__file__).parent


def _load_env(path):
    """Read KEY=value lines from .env into the environment (a value already set in the shell wins)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value and not os.environ.get(key.strip()):
            os.environ[key.strip()] = value


_load_env(ROOT / ".env")
DATA = ROOT / "data"
OUT = ROOT / "out"

# Kennedy Town (west) to Sai Ying Pun (east), Pok Fu Lam Road halls (south) to the waterfront (north).
BBOX = (22.276, 114.124, 22.292, 114.147)  # south, west, north, east
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "comp1110-same-route-study/0.1"

# Walking model (authors' decision 3: speeds from published studies; sources in data/walking_speeds.csv,
# taken from abstracts and quotes, so check the originals before citing).
WALK_SPEED = 1.34          # m/s: mean free walking speed on the flat (Weidmann 1993; Bosina & Weidmann 2017).
                           # Map walking times are computed at this speed, then scaled by each person's own speed.
STAIRS_SPEED = 0.67        # m/s along a stair (horizontal): mean of up 0.57 and down 0.77 (Fruin 1971). The map
                           # does not say which way a stair goes up, so both directions get the mean.
STEPS_FACTOR = WALK_SPEED / STAIRS_SPEED   # a metre of stairs takes this many times as long as a flat metre (2.0)
LIFT_SECONDS = 40          # wait + ride for one lift link: no published source found, an assumption
SPEED_BY_AGE = {           # comfortable speed by age, m/s: mean of men and women (Bohannon & Andrews 2011)
    20: 1.35, 30: 1.385, 40: 1.41, 50: 1.37, 60: 1.29, 70: 1.195, 80: 0.955}
CHILD_SPEED = 1.2          # ages 6 to 9: an assumption within the 0.82-1.34 m/s range for ages 1-10 (Dusing & Thorpe 2007);
                           # ages 10 to 19 walk like adults (McKay et al. 2017) and use the value for 20-29
SPEED_SD = 0.15            # m/s, spread between people of the same age (Bohannon 1997)
PACES = {"slow": 0.76, "normal": 1.0, "fast": 1.30}   # a person's choice for each walk, relative to their own
                           # comfortable speed (Lythgo, Wilson & Galea 2011; Oberg et al. 1993 give the same ratios)
UNLIT_PENALTY = 60         # extra "felt" seconds per unlit segment after dark (route choice only)
SHARED_WINDOW = 90         # seconds: a stranger must enter the same segment within this of you

# The simulated day (the same for everyone)
WEATHER = "a dry, mild November weekday, about 23°C, sunny with a light breeze"

# LLM planner
MODEL = "claude-haiku-5-5"
EFFORT = "low"             # low | medium | high; Haiku 5.5 thinks adaptively at every level
MAX_CALLS_PER_AGENT = 40
MAX_TOKENS = 4000
CONCURRENCY = 16
# US$ per million tokens for claude-haiku-5-5 (Anthropic list price, Oct 2026). Cache read/write use
# the standard 0.1x / 1.25x multipliers. Check the pricing page before a big run.
PRICE_IN = 0.10
PRICE_OUT = 0.50
PRICE_CACHE_READ = PRICE_IN * 0.1
PRICE_CACHE_WRITE = PRICE_IN * 1.25
BUDGET_USD = 30.0          # the planner stops starting new calls once this much is spent
