"""Progress reports that the UI reads while a simulation runs.

A running simulation writes runs/<run>/progress.json (how far it got, the spend, its status) and, for the live
world, runs/<run>/live_positions.json (where everyone is on the shared clock). Writing them only reads the
simulation's state: it uses no random numbers and changes nothing, so a run gives the same results with or
without anyone watching. Both files are replaced atomically, at most a few times a second, and git ignores them.
"""
import json
import os
import time

MIN_INTERVAL = 0.5     # seconds between two writes of the same file (a forced write ignores this)


def write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


class Progress:
    """runs/<run>/progress.json: kind ('agent-world' or 'live'), planner, status, people, done, calls, spend."""

    def __init__(self, run_dir, kind, planner, people, budget=None, people_file=None, **extra):
        self.path = run_dir / "progress.json"
        self.positions_path = run_dir / "live_positions.json"
        self.last = self.last_positions = 0.0
        self.state = {"run": run_dir.name, "kind": kind, "planner": planner, "status": "running", "message": "",
                      "pid": os.getpid(), "started": time.time(), "updated": time.time(), "people": people,
                      "done": 0, "calls": 0, "usd": 0.0, "budget": budget,
                      "people_file": str(people_file) if people_file else None, **extra}
        self.write(force=True)

    def write(self, force=False):
        now = time.time()
        if not force and now - self.last < MIN_INTERVAL:
            return
        self.last = self.state["updated"] = now
        try:
            write_json(self.path, self.state)
        except OSError:
            pass   # a report that cannot be written never stops the simulation

    def update(self, force=False, **fields):
        self.state.update(fields)
        self.write(force)

    def finish(self, status="finished", message="", **fields):
        self.update(force=True, status=status, message=message, **fields)

    # ---------------- the live world ----------------
    def live_tick(self, live, clock, spend, force=False):
        """Counts and everyone's position at this moment of the shared clock (live.position and live.visible are
        read-only)."""
        now = time.time()
        if not force and now - self.last_positions < MIN_INTERVAL:
            return
        self.last_positions = now
        people, walking, at_place, gone, started = [], 0, 0, 0, 0
        for p in live.people.values():
            if p.gone:
                gone += 1
                continue
            if not p.started:
                continue
            started += 1
            x, y, step = live.position(p, clock)
            moving = step is not None
            if moving:
                walking += 1
            elif p.place:
                at_place += 1
            # [id, x, y, 1 walking / 0 still, 1 visible from the street / 0 indoors, calls so far]
            people.append([p.id, round(x, 1), round(y, 1), int(moving), int(live.visible(p, clock)), p.calls])
        try:
            write_json(self.positions_path, {"clock": clock, "updated": now, "people": people})
        except OSError:
            pass
        self.update(force=force, clock=clock, walking=walking, at_place=at_place, gone=gone, started_people=started,
                    done=sum(1 for p in live.people.values() if p.done), calls=spend.calls, usd=round(spend.usd, 4))
