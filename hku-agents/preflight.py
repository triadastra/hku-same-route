"""Check everything before spending money.

    python preflight.py              # files, SDK, and an offline test of the Claude loop (free, no key needed)
    python preflight.py --key        # also checks your API key with a free token-count call and estimates cost
    python preflight.py --one        # also runs ONE real agent for its whole day (about US$0.01)
"""
import argparse
import asyncio
import json
import os

import config as C

OK, BAD = "[ok]  ", "[FAIL]"


def check_files(agents_path):
    good = True
    for p, hint in ((C.DATA / "graph.json", "python build_map.py"), (C.DATA / "places.csv", "python captions.py"),
                    (agents_path, "python make_agents.py --n 200")):
        exists = os.path.exists(p)
        print(f"{OK if exists else BAD} {p}" + ("" if exists else f"  -> run: {hint}"))
        good &= exists
    return good


def offline_loop_test(world, agent):
    """Drive the real SDK through a fake server: proves the request shape and the tool loop, no key needed."""
    import anthropic
    import httpx2
    from anthropic import DefaultAsyncHttpxClient

    import run_day
    from agent_tools import system_prompt

    plan = [("where_am_i", {}), ("search_places", {"query": "food", "category": "food"}),
            ("go_to", {"to": agent["commitments"][0]["place"], "reason": "class"}),
            ("go_to", {"to": agent["home"], "reason": "home"}),
            ("stay", {"until": "22:30", "activity": "evening"}), ("end_day", {"summary": "test"})]
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append(body)
        name, inp = plan[min(len(seen), len(plan)) - 1]
        return httpx2.Response(200, json={
            "id": f"msg_{len(seen)}", "type": "message", "role": "assistant", "model": body["model"],
            "content": [{"type": "thinking", "thinking": "", "signature": "x"},
                        {"type": "tool_use", "id": f"toolu_{len(seen)}", "name": name, "input": inp}],
            "stop_reason": "tool_use", "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 80, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}})

    client = anthropic.AsyncAnthropic(api_key="offline-test", http_client=DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)))
    rec = asyncio.run(run_day.claude_day(client, system_prompt(world), agent, world, run_day.Spend(1)))
    ok = rec["stop"] == "ended" and len(rec["trips"]) == 2 and all(not l["error"] for l in rec["log"])
    print(f"{OK if ok else BAD} offline Claude loop: {rec['calls']} calls, {len(rec['trips'])} trips, request fields {sorted(seen[0])}")
    return ok


def key_check(world, agent):
    import anthropic

    from agent_tools import TOOLS, persona_card, system_prompt
    client = anthropic.Anthropic()
    try:
        n = client.messages.count_tokens(model=C.MODEL, system=system_prompt(world), tools=TOOLS,
                                         messages=[{"role": "user", "content": persona_card(agent, world)}]).input_tokens
    except TypeError:  # the SDK found no credentials at all
        print(f"{BAD} no API key found. Set ANTHROPIC_API_KEY to a key from console.anthropic.com")
        return False
    except anthropic.AuthenticationError:
        print(f"{BAD} API key rejected. Set ANTHROPIC_API_KEY to a key from console.anthropic.com")
        return False
    except anthropic.APIStatusError as e:
        print(f"{BAD} token count failed: {e.status_code} {e.message}")
        return False
    except anthropic.APIConnectionError:
        print(f"{BAD} cannot reach the Anthropic API (network)")
        return False
    print(f"{OK} API key works; the shared prompt plus one persona is {n} tokens")
    # Rough per-agent cost: every call re-reads the conversation from cache, writes the new turn, and
    # generates thinking plus one tool call. Growth and output sizes are guesses until --one measures them.
    for calls in (20, C.MAX_CALLS_PER_AGENT):
        growth, out_tok = 350, 300
        read = sum(n + i * growth for i in range(calls))
        usd = (read * C.PRICE_CACHE_READ + calls * growth * C.PRICE_CACHE_WRITE + calls * out_tok * C.PRICE_OUT) / 1e6
        print(f"       ~{calls} calls per agent: about US${usd:.4f} per agent, US${usd * 5000:.0f} for 5,000, US${usd * 10000:.0f} for 10,000")
    return True


def one_agent(world, agent):
    import anthropic

    import run_day
    from agent_tools import system_prompt
    spend = run_day.Spend(1.0)
    rec = asyncio.run(run_day.claude_day(anthropic.AsyncAnthropic(max_retries=4), system_prompt(world), agent, world, spend))
    for l in rec["log"]:
        print(f"       {l['t']} {l['tool']:<14} {json.dumps(l['input'], ensure_ascii=False)[:90]}{'  (error)' if l['error'] else ''}")
    print(f"{OK} one real day: {rec['calls']} calls, {len(rec['trips'])} trips, ended '{rec['stop']}', cost US${rec['cost_usd']:.4f}, "
          f"tokens {spend.tok}")
    out = C.OUT / "preflight"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{agent['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"       saved to {out / (agent['id'] + '.json')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", default=str(C.DATA / "agents.jsonl"))
    ap.add_argument("--key", action="store_true")
    ap.add_argument("--one", action="store_true")
    args = ap.parse_args()

    if not check_files(args.agents):
        raise SystemExit(1)
    try:
        import anthropic
        print(f"{OK} anthropic SDK {anthropic.__version__}")
    except ImportError:
        raise SystemExit(f"{BAD} anthropic SDK missing  -> run: pip install anthropic")
    from world import World
    world = World()
    agent = json.loads(open(args.agents, encoding="utf-8").readline())
    ok = offline_loop_test(world, agent)
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    print(f"{OK if has_key else '[--]  '} API key in environment: {'yes' if has_key else 'not set (fine for now)'}")
    if args.key or args.one:
        ok &= key_check(world, agent)
    if args.one and ok:
        one_agent(world, agent)
    print("\nReady." if ok else "\nFix the items marked FAIL first.")


if __name__ == "__main__":
    main()
