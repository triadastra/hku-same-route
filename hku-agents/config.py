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

# Walking model
WALK_SPEED = 1.35          # m/s on the flat
STEPS_FACTOR = 2.2         # a metre of stairs takes this many times as long as a flat metre
LIFT_SECONDS = 40          # wait + ride for one lift link
UNLIT_PENALTY = 60         # extra "felt" seconds per unlit segment after dark (route choice only)
STAIRS_AVOID = 6           # extra "felt" seconds per metre of stairs on step-free routes (route choice only)
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
