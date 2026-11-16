"""The browser UI: watch a simulation while it runs, replay a finished one on the map, and read its results.

    python -m sameroute ui                    # then open http://127.0.0.1:8765
    python -m sameroute ui --port 9000 --open

It only uses the Python standard library. It reads runs/ (see sameroute/runs.py) and graphs/, and it can start
free runs (the rule-based planner, no API key, no cost) so you can watch one fill up. Paid runs are started from
the command line (docs/RUNBOOK.md); the UI shows them while they run all the same.
"""
import argparse
import csv
import json
import mimetypes
import os
import random
import re
import signal
import subprocess
import sys
import threading
import webbrowser
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from sameroute import config as C
from sameroute import runs as R
from sameroute.world.groups import GROUPS, LABELS, group_of
from sameroute.world.world import World, xy

STATIC = Path(__file__).parent / "static"
NAME_OK = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
GROUP_NAMES = [LABELS[g] for g in GROUPS] + ["Unknown"]
_lock = threading.Lock()
_cache = {}
_groups = {}     # run -> {person id: (group, name, age)}, for the live positions


def cached(key, stamp, build):
    """Memoise build() under key until stamp changes."""
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
    value = build()
    with _lock:
        _cache[key] = (stamp, value)
    return value


# ---------------- the map ----------------
@lru_cache(maxsize=1)
def map_data():
    """Footpaths as polylines and places as points, in metres east and north of HKU (world.xy)."""
    g = json.loads((C.DATA / "graph.json").read_text(encoding="utf-8"))
    nodes = [[round(v, 1) for v in xy(n["lat"], n["lon"])] for n in g["nodes"]]
    edges = []
    for e in g["edges"]:
        pts = [c for lat, lon in e["geom"] for c in (round(v, 1) for v in xy(lat, lon))]
        edges.append({"p": pts, "s": 1 if e["steps"] > 0.5 * e["len"] else 0, "l": 1 if e["lift"] else 0})
    with (C.DATA / "places.csv").open(encoding="utf-8-sig") as f:
        info = {r["code"]: r for r in csv.DictReader(f)}
    places = []
    for p in g["places"]:
        r = info.get(p["code"], {})
        x, y = xy(float(r.get("lat", p.get("lat", 0))), float(r.get("lon", p.get("lon", 0))))
        places.append([p["code"], r.get("name", p.get("name", "")), r.get("category", p.get("category", "")),
                       round(x, 1), round(y, 1), p["node"]])
    xs, ys = [n[0] for n in nodes], [n[1] for n in nodes]
    areas = [[name, round(x, 1), round(y, 1)] for name, (x, y) in World().areas.items()]
    return json.dumps({"nodes": nodes, "edges": edges, "places": places, "areas": areas,
                       "bounds": [min(xs), min(ys), max(xs), max(ys)]}, separators=(",", ":")).encode()


# ---------------- a run's replay ----------------
def people_groups(name, ids):
    found = R.people(name, ids)
    return {i: (GROUPS.index(group_of(a)) if a else len(GROUPS), a.get("name", ""), a.get("age"))
            for i, a in ((i, found.get(i)) for i in ids)}


def build_replay(name, max_people):
    """Every trip of a sample of people, as [person, depart, arrive, auto, kind, [node, t, node, t, ...]]."""
    by_agent = {}
    for t in R.trips(name):
        if t.get("segments"):
            by_agent.setdefault(t["agent"], []).append(t)
    ids = sorted(by_agent)
    total = len(ids)
    if max_people and len(ids) > max_people:
        ids = sorted(random.Random(0).sample(ids, max_people))
    groups = people_groups(name, ids)
    kinds, people, out = [], [], []
    for pi, pid in enumerate(ids):
        g, pname, age = groups.get(pid, (len(GROUPS), "", None))
        people.append([pid, g, pname, age])
        for t in by_agent[pid]:
            segs = t["segments"]
            path = []
            for s in segs:
                path += [s["from"], s["t"]]
            end = t.get("arrive") if t.get("arrive") is not None else segs[-1]["t"]
            path += [segs[-1]["to"], end]
            kind = t.get("kind", "go")
            if kind not in kinds:
                kinds.append(kind)
            out.append([pi, segs[0]["t"], end, int(bool(t.get("auto"))), kinds.index(kind), path])
    out.sort(key=lambda r: r[1])
    t_lo = min((r[1] for r in out), default=6 * 3600)
    t_hi = max((r[2] for r in out), default=24 * 3600)
    return json.dumps({"run": name, "groups": GROUP_NAMES, "kinds": kinds, "people": people, "trips": out,
                       "people_total": total, "t_min": t_lo, "t_max": t_hi}, separators=(",", ":")).encode()


def replay(name, max_people):
    src, mtime = R.trips_source(name)
    if src is None:
        return json.dumps({"run": name, "groups": GROUP_NAMES, "kinds": [], "people": [], "trips": [],
                           "people_total": 0, "t_min": 6 * 3600, "t_max": 24 * 3600}).encode()
    stamp = (str(src), mtime, max_people)
    disk = C.OUT / name / ".ui_cache" / f"replay_{max_people or 'all'}.json"
    meta = disk.with_suffix(".stamp")

    def build():
        if src.is_file() and disk.exists() and meta.exists() and meta.read_text() == repr(stamp):
            return disk.read_bytes()
        data = build_replay(name, max_people)
        if src.is_file():   # finished runs only: a running one changes all the time
            try:
                disk.parent.mkdir(exist_ok=True)
                disk.write_bytes(data)
                meta.write_text(repr(stamp))
            except OSError:
                pass
        return data
    return cached(("replay", name, max_people), stamp, build)


def positions(name):
    """Where everyone is now in a running live world, with each person's group."""
    path = C.OUT / name / "live_positions.json"
    snap = R.read_json(path, {"clock": None, "people": []})
    with _lock:
        groups = _groups.setdefault(name, {})
    missing = [p[0] for p in snap["people"] if p[0] not in groups]
    if missing:
        fresh = people_groups(name, sorted(set(groups) | set(missing)))
        with _lock:
            groups.update(fresh)
    snap["groups"] = GROUP_NAMES
    snap["people"] = [p + [groups.get(p[0], (len(GROUPS),))[0]] for p in snap["people"]]
    return snap


# ---------------- starting a free run ----------------
def launch(body):
    kind = body.get("kind")
    name = str(body.get("run", "")).strip()
    n = max(10, min(10000, int(body.get("people", 300))))
    seed = int(body.get("seed", 7))
    slow = max(0.0, float(body.get("slow", 0)))
    if kind not in ("agent-world", "live"):
        raise ValueError("kind must be agent-world or live")
    if not NAME_OK.match(name) or name in ("day1", "census_run", "live_census"):
        raise ValueError("pick a new run name (letters, digits, - and _), not one of the kept runs")
    run_dir = C.OUT / name
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError(f"runs/{name} already exists: pick another name")
    run_dir.mkdir(parents=True, exist_ok=True)
    people = f"runs/{name}/people.jsonl"
    py = sys.executable
    cmds = [[py, "-m", "sameroute", "people", "--n", str(n), "--seed", str(seed), "--out", people]]
    if kind == "agent-world":
        cmds.append([py, "-m", "sameroute", "agent-world", "--run", name, "--planner", "mock", "--agents", people,
                     "--slow", str(slow)])
    else:
        cmds.append([py, "-m", "sameroute", "live", "--run", name, "--planner", "mock", "--agents", people,
                     "--slow", str(slow)])
    log = (run_dir / "ui.log").open("w", encoding="utf-8")

    def go():
        for cmd in cmds:
            log.write("$ python " + " ".join(cmd[1:]) + "\n")
            log.flush()
            if subprocess.call(cmd, cwd=C.ROOT, stdout=log, stderr=subprocess.STDOUT) != 0:
                log.write("stopped: the command above failed\n")
                break
        log.close()
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True, "run": name, "command": " && ".join("python " + " ".join(c[1:]) for c in cmds)}


def stop(name):
    p = R.read_json(C.OUT / name / "progress.json") or {}
    pid = p.get("pid")
    if not R.pid_alive(pid):
        raise ValueError("that run is not running")
    os.kill(pid, signal.SIGINT)    # the simulators save and stop cleanly on Ctrl+C
    return {"ok": True}


# ---------------- HTTP ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = "sameroute-ui"

    def log_message(self, fmt, *args):
        if os.environ.get("SAMEROUTE_UI_LOG"):
            super().log_message(fmt, *args)

    def send(self, body, ctype="application/json", status=200, cache=False):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, separators=(",", ":")).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def fail(self, status, msg):
        self.send({"error": msg}, status=status)

    def run_name(self, name):
        name = unquote(name)
        if not NAME_OK.match(name) or not (C.OUT / name).is_dir():
            raise FileNotFoundError(f"no run called {name!r}")
        return name

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        parts = [p for p in url.path.split("/") if p]
        try:
            if not parts or parts == ["index.html"]:
                return self.send((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if parts[0] == "static" and len(parts) == 2 and (STATIC / parts[1]).is_file():
                f = STATIC / parts[1]
                return self.send(f.read_bytes(), (mimetypes.guess_type(f.name)[0] or "text/plain") + "; charset=utf-8")
            if parts[0] == "graphs" and len(parts) == 2 and NAME_OK.match(parts[1]) and (C.GRAPHS / parts[1]).is_file():
                f = C.GRAPHS / parts[1]
                return self.send(f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream", cache=True)
            if parts[0] != "api":
                return self.fail(404, "not found")
            api = parts[1:]
            if api == ["map"]:
                return self.send(map_data(), cache=True)
            if api == ["runs"]:
                return self.send([R.info(n) for n in R.run_names()])
            if api == ["figures"]:
                figs = sorted(C.GRAPHS.glob("*.png"), key=lambda p: -p.stat().st_mtime)
                return self.send([{"name": p.stem, "png": p.name, "pdf": p.with_suffix(".pdf").exists(),
                                   "updated": p.stat().st_mtime} for p in figs])
            if len(api) >= 2 and api[0] == "runs":
                name = self.run_name(api[1])
                rest = api[2:]
                if not rest:
                    return self.send(R.info(name))
                if rest == ["replay"]:
                    n = int(q.get("people", ["3000"])[0])
                    return self.send(replay(name, n))
                if rest == ["positions"]:
                    return self.send(positions(name))
                if rest == ["log"]:
                    log = C.OUT / name / "ui.log"
                    text = log.read_text(encoding="utf-8", errors="replace")[-6000:] if log.exists() else ""
                    return self.send({"log": text})
                if len(rest) == 2 and rest[0] == "person" and re.match(r"^[A-Za-z0-9]{1,12}$", rest[1]):
                    rec = R.person(name, rest[1])
                    if rec is None:
                        return self.fail(404, "no record of that person in this run (yet)")
                    return self.send(rec)
                if rest == ["file"]:
                    rel = q.get("path", [""])[0]
                    base = (C.OUT / name / "analysis").resolve()
                    f = (base / rel).resolve()
                    if base not in f.parents or not f.is_file() or f.suffix not in (".md", ".csv", ".tex"):
                        return self.fail(404, "no such analysis file")
                    return self.send(f.read_text(encoding="utf-8", errors="replace"), "text/plain; charset=utf-8")
            return self.fail(404, "not found")
        except FileNotFoundError as e:
            return self.fail(404, str(e))
        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception as e:   # show the error in the page instead of a dropped connection
            return self.fail(500, f"{type(e).__name__}: {e}")

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            if parts == ["api", "launch"]:
                return self.send(launch(body))
            if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "stop":
                return self.send(stop(self.run_name(parts[2])))
            return self.fail(404, "not found")
        except (ValueError, FileNotFoundError) as e:
            return self.fail(400, str(e))
        except Exception as e:
            return self.fail(500, f"{type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser(description="Watch a simulation in progress, replay a run, and read its results.")
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to reach it from another machine")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="open it in the default browser")
    args = ap.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '') else args.host}:{args.port}"
    print(f"Same-route UI on {url}  (Ctrl+C to stop)", flush=True)
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
