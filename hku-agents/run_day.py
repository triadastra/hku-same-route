"""Let every agent live its day, then save the trips for analysis.

    python run_day.py --run pilot --planner mock                 # free, rule-based, for testing
    python run_day.py --run pilot-claude --planner claude --limit 20
    python run_day.py --run day1 --planner claude --budget 30    # stops starting calls at US$30
    python run_day.py --run stepfree --planner replay --replay-from day1 --routes step-free

Planners: 'claude' (each person is played by the model), 'mock' (a free rule-based timetable-follower)
and 'replay' (repeats the tool calls of a finished run, free). --routes sets how walks are routed; see
ROUTE_MODES in agent_tools.py. Most people should use pipeline.py, which calls this.

Each agent's day is saved to out/<run>/agents/<id>.json as soon as it finishes, so a stopped run can be
restarted with the same command and only the unfinished agents run again.
"""
import argparse
import asyncio
import json
import random
import time

import config as C
import plans
from agent_tools import ROUTE_MODES, TOOLS, AgentDay, persona_card, route_policy, system_prompt, tool_result_text
from world import World, hhmm, parse_hhmm


class Spend:
    def __init__(self, budget):
        self.budget, self.usd, self.calls = budget, 0.0, 0
        self.tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}

    def add(self, u):
        cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        cr = getattr(u, "cache_read_input_tokens", 0) or 0
        usd = (u.input_tokens * C.PRICE_IN + cw * C.PRICE_CACHE_WRITE + cr * C.PRICE_CACHE_READ
               + u.output_tokens * C.PRICE_OUT) / 1e6
        self.usd += usd
        self.calls += 1
        for k, v in (("input", u.input_tokens), ("cache_write", cw), ("cache_read", cr), ("output", u.output_tokens)):
            self.tok[k] += v
        return usd

    @property
    def exhausted(self):
        return self.usd >= self.budget


# ---------------- Claude planner ----------------
async def claude_day(client, system, agent, world, spend, policy="quickest"):
    day = AgentDay(agent, world, policy=policy)
    messages = [{"role": "user", "content": persona_card(agent, world)}]
    cost, nudges, stop = 0.0, 0, ""
    while not day.done:
        if day.calls >= C.MAX_CALLS_PER_AGENT:
            stop = "call limit"; break
        if spend.exhausted:
            stop = "budget"; break
        if day.t >= 24 * 3600 - 60:
            stop = "midnight"; break
        resp = await client.messages.create(
            model=C.MODEL, max_tokens=C.MAX_TOKENS, tools=TOOLS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages, output_config={"effort": C.EFFORT},
            cache_control={"type": "ephemeral"},
        )
        day.calls += 1
        cost += spend.add(resp.usage)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "refusal":
            stop = "refusal"; break
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            nudges += 1
            if nudges > 2:
                stop = "no tool call"; break
            messages.append({"role": "user", "content": f"Continue your day with the tools. It is {hhmm(day.t)}."})
            continue
        results = []
        for b in uses:
            if day.done:  # end_day came earlier in this same reply
                out, err = {"error": "the day has ended"}, True
            else:
                out, err = day.run(b.name, dict(b.input))
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": tool_result_text(out), "is_error": err})
        messages.append({"role": "user", "content": results})
    day.finish()
    return day.record(cost, stop)


# ---------------- free rule-based planner ----------------
def mock_day(agent, world, rng, policy="quickest"):
    """A simple timetable-follower that uses the same tools, for testing the pipeline at no cost."""
    day = AgentDay(agent, world, policy=policy)
    habits = " ".join(agent["habits"])
    ate_lunch = False

    def call(name, **kw):
        day.calls += 1
        return day.run(name, kw)[0]

    def fill(until_t):
        nonlocal ate_lunch
        free = until_t - day.t
        if free < 20 * 60:
            return
        if not ate_lunch and 11.5 * 3600 <= day.t <= 14 * 3600 and free >= 50 * 60:
            food = call("nearby", category="food", max_minutes=8)["results"] or call("search_places", query="canteen food", category="any")["results"]
            if food:
                pick = rng.choice(food[:4])["code"]
                if pick != day.at:
                    call("go_to", to=pick, reason="lunch")
                call("stay", until=hhmm(min(until_t - 15 * 60, day.t + rng.randint(30, 50) * 60)), activity="lunch")
                ate_lunch = True
                return
        if free >= 70 * 60:
            spot = rng.choice(call("search_places", query="study library", category="any")["results"][:3])["code"]
            if spot != day.at:
                call("go_to", to=spot, reason="study between classes")
            if until_t - 15 * 60 > day.t:
                call("stay", until=hhmm(until_t - 15 * 60), activity="study")

    for c in sorted(agent["commitments"], key=lambda c: c["start"]):
        start = parse_hhmm(c["start"])
        fill(start)
        if c["place"] != day.at:
            info = call("route_info", to=c["place"])
            leave = start - (info["minutes"] + rng.randint(2, 10)) * 60
            if leave > day.t + 60:
                call("stay", until=hhmm(leave), activity="getting ready")
            call("go_to", to=c["place"], reason=c["what"])
        end = parse_hhmm(c["end"]) if c.get("end") else day.t + rng.randint(30, 90) * 60
        if end > day.t:
            call("stay", until=hhmm(end), activity=c["what"])
    if "gym" in habits and day.t < 20 * 3600:
        gym = call("search_places", query="sports gym", category="any")["results"]
        if gym and gym[0]["code"] != day.at:
            call("go_to", to=gym[0]["code"], reason="gym")
            call("stay", until=hhmm(day.t + 60 * 60), activity="workout")
    if "library until late" in habits and day.t < 21 * 3600:
        lib = world.code_by_name("Main Library")
        if day.at != lib:
            call("go_to", to=lib, reason="study late")
        call("stay", until="22:30", activity="study")
    elif day.t < 19.5 * 3600 and rng.random() < 0.5:
        food = call("nearby", category="food", max_minutes=10)["results"]
        if food:
            pick = rng.choice(food[:5])["code"]
            if pick != day.at:
                call("go_to", to=pick, reason="dinner")
            call("stay", until=hhmm(day.t + rng.randint(30, 60) * 60), activity="dinner")
    walker = any(w in " ".join(agent.get("interests", [])) for w in ("walking", "harbour", "photography", "hiking", "running"))
    if walker and agent.get("spontaneity", 0) > 0.45 and day.t < 20 * 3600:
        sights = call("nearby", category="sight", max_minutes=30)["results"]
        if sights:
            call("stroll", toward=rng.choice(sights)["code"], minutes=rng.randint(25, 80), reason="wander")
    if day.at != agent["home"]:
        call("go_to", to=agent["home"], reason="home")
    if not day.commuter and day.t < 22 * 3600:
        call("stay", until="22:30", activity="evening at home")
    call("end_day", summary="followed the timetable")
    return day.record(0.0, "ended")


# ---------------- replay planner ----------------
def replay_day(agent, plan, world, policy="quickest"):
    """Repeat the tool calls of an earlier day, in order. With the same route mode this rebuilds the
    earlier trips exactly; with another, the same decisions are walked by different routes (a call
    that no longer fits, such as staying until a time already past, fails as it would have then)."""
    if plan["who"] != plans.fingerprint(agent):
        raise SystemExit(f"{agent['id']} is not the person these plans were made for. Use the people file of the "
                         f"replayed run (same --n and --seed, same make_agents.py).")
    day = AgentDay(agent, world, policy=policy)
    for tool, args in plan["log"]:
        if day.done:
            break
        day.run(tool, dict(args))
    day.calls = plan["calls"]
    day.finish()
    return day.record(0.0, plan["stop"] if day.summary or plan["stop"] != "ended" else "cut")


# ---------------- runner ----------------
async def run_all(args, agents, world, out_dir):
    spend = Spend(args.budget)
    # The budget covers the whole run, including agents finished by earlier, interrupted attempts.
    spend.usd = sum(json.loads(p.read_text(encoding="utf-8"))["cost_usd"] for p in out_dir.glob("A*.json"))
    todo = [a for a in agents if not (out_dir / f"{a['id']}.json").exists()]
    print(f"{len(agents) - len(todo)} agents already done, {len(todo)} to run with the {args.planner} planner")
    t0 = time.time()
    if args.planner == "mock":
        for a in todo:
            # One random stream per person, so a resumed or shortened run gives the same days.
            rec = mock_day(a, world, random.Random(f"{args.seed}:{a['id']}"), route_policy(a, args.routes))
            (out_dir / f"{a['id']}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return spend, time.time() - t0
    if args.planner == "replay":
        source = args.source[1]
        missing = [a["id"] for a in todo if a["id"] not in source]
        if missing:
            print(f"  {len(missing)} people have no plan in '{args.replay_from}' (unfinished there) and are left out")
        for a in todo:
            if a["id"] in source:
                rec = replay_day(a, source[a["id"]], world, route_policy(a, args.routes))
                (out_dir / f"{a['id']}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return spend, time.time() - t0

    try:
        import anthropic
    except ImportError:
        raise SystemExit("Install the Anthropic SDK first:  pip install anthropic")
    client = anthropic.AsyncAnthropic(max_retries=8)
    system = system_prompt(world)
    sem = asyncio.Semaphore(args.concurrency)
    done, fatal = 0, []

    async def one(a):
        nonlocal done
        async with sem:
            if spend.exhausted or fatal:
                return
            try:
                rec = await claude_day(client, system, a, world, spend, route_policy(a, args.routes))
            except TypeError as e:  # raised by the SDK when no API key is set at all
                if not fatal:
                    print(f"  stopping: no API key found ({e}). Set ANTHROPIC_API_KEY first.")
                fatal.append(e)
                return
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
                    anthropic.NotFoundError, anthropic.BadRequestError) as e:
                # The same error would hit every agent: stop the whole run.
                if not fatal:
                    print(f"  stopping: {type(e).__name__} {e.status_code}: {e.message}")
                fatal.append(e)
                return
            except anthropic.APIStatusError as e:
                print(f"  {a['id']}: API error {e.status_code}, will retry on the next run: {e.message}")
                return
            except anthropic.APIConnectionError:
                print(f"  {a['id']}: network error, will retry on the next run")
                return
            if rec["stop"] == "budget":
                return  # half a day would skew the results; this agent runs again when the budget is raised
            (out_dir / f"{a['id']}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            done += 1
            if done % 10 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)} agents, {spend.calls} calls, US${spend.usd:.3f} spent")

    await asyncio.gather(*(one(a) for a in todo))
    if spend.exhausted:
        print(f"  budget of US${args.budget:.2f} reached; rerun with a higher --budget to finish the rest")
    return spend, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="pilot")
    ap.add_argument("--planner", choices=["mock", "claude", "replay"], default="mock")
    ap.add_argument("--routes", choices=list(ROUTE_MODES), default="quickest", help="how walks are routed")
    ap.add_argument("--replay-from", default="", help="for --planner replay: a finished run (name, folder or plans file)")
    ap.add_argument("--agents", default=str(C.DATA / "agents.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="only the first N agents")
    ap.add_argument("--budget", type=float, default=C.BUDGET_USD)
    ap.add_argument("--concurrency", type=int, default=C.CONCURRENCY)
    ap.add_argument("--seed", type=int, default=1, help="only the mock planner draws random numbers")
    args = ap.parse_args()
    if args.planner == "replay" and not args.replay_from:
        ap.error("--planner replay needs --replay-from <run>")
    model = None
    if args.planner == "claude":
        model = C.MODEL
    elif args.planner == "replay":
        args.source = plans.load_plans(args.replay_from)
        model = args.source[0].get("model")

    world = World()
    agents = [json.loads(l) for l in open(args.agents, encoding="utf-8")]
    if args.limit:
        agents = agents[: args.limit]
    out_dir = C.OUT / args.run / "agents"
    out_dir.mkdir(parents=True, exist_ok=True)
    spend, secs = asyncio.run(run_all(args, agents, world, out_dir))

    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("A*.json"))]
    with open(C.OUT / args.run / "trips.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            for t in r["trips"]:
                f.write(json.dumps(t) + "\n")
    n = len(recs)
    calls = sum(r["calls"] for r in recs)
    usd = sum(r["cost_usd"] for r in recs)
    trips = sum(len(r["trips"]) for r in recs)
    stops = {}
    for r in recs:
        stops[r["stop"]] = stops.get(r["stop"], 0) + 1
    policies = {}
    for r in recs:
        policies[r.get("route_policy", "quickest")] = policies.get(r.get("route_policy", "quickest"), 0) + 1
    summary = {"planner": args.planner, "model": model, "routes": args.routes, "route_policies": policies,
               "replayed_from": args.replay_from or None, "seed": args.seed, "agents": n, "calls": calls, "trips": trips, "usd": round(usd, 4),
               "usd_per_agent": round(usd / n, 5) if n else 0, "projected_usd_10k_agents": round(usd / n * 10000, 2) if n else 0,
               "tokens_this_session": spend.tok, "seconds_this_session": round(secs, 1), "how_days_ended": stops}
    (C.OUT / args.run / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if recs:
        plans.write_plans(C.OUT / args.run, recs, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
