"""Create synthetic people with a personal profile and the fixed things they must do today.

Everything here is made up and drawn at random from the mix below. Change MIX and the lists to match
real HKU numbers before a final run, and cite where those numbers came from.

    python make_agents.py --n 200 --seed 1          # -> data/agents.jsonl
"""
import argparse
import json
import random

import config as C
from world import World, hhmm

MIX = {"undergrad": 0.62, "postgrad": 0.12, "staff": 0.10, "resident": 0.16}
HALL_SHARE = {"undergrad": 0.35, "postgrad": 0.15}   # the rest commute by MTR or bus

FACULTIES = {
    "Arts": ["Run Run Shaw Tower"],
    "Social Sciences": ["Jockey Club Tower"],
    "Law": ["Cheng Yu Tung Tower"],
    "Engineering": ["Haking Wong Building", "Chow Yei Ching Building"],
    "Business and Economics": ["K.K. Leung Building"],
    "Science": ["Chong Yuet Ming Physics", "Chong Yuet Ming Chemistry", "James Hsioung Lee", "Kadoorie Biological"],
}
FACULTY_WEIGHT = {"Arts": 12, "Social Sciences": 14, "Law": 7, "Engineering": 20, "Business and Economics": 22, "Science": 18}
SHARED_ROOMS = ["Central Podium", "Lee Shau Kee Lecture Centre", "Meng Wah Complex", "Knowles Building",
                "Rayson Huang Theatre", "Main Building"]
# HKU classes start at :30 and end at :20.
SLOTS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]

SURNAMES = ["Chan", "Wong", "Lee", "Cheung", "Lau", "Ng", "Ho", "Leung", "Lam", "Tsang", "Chow", "Yip", "Kwok",
            "Tang", "Mak", "Fung", "Liu", "Zhang", "Wang", "Li", "Chen", "Singh", "Patel", "Kim", "Nguyen", "Smith"]
GIVEN = ["Ka Yan", "Hoi Ching", "Chun Hei", "Wing Sze", "Tsz Long", "Yuen Ting", "Ming", "Yan", "Jason", "Chloe",
         "Kelvin", "Mandy", "Ivan", "Karen", "Ryan", "Sharon", "Hayden", "Michelle", "Yuxuan", "Zihan", "Arjun",
         "Minjun", "Linh", "Emily", "Oliver", "Sophie"]
HABITS = ["avoids stairs when there is a lift", "always takes the quickest way", "walks with headphones on",
          "likes busy, well-lit paths at night", "is usually running late", "stops for bubble tea",
          "studies in the library until late", "goes to the gym after class", "eats lunch at the same place daily",
          "explores new food places", "walks slowly and looks at the harbour", "meets friends at the fountain"]
PERSONALITY = ["quiet and organised", "sociable and spontaneous", "stressed about exams", "relaxed and curious",
               "very punctual", "a night owl", "an early bird", "always on the phone"]
# Interests with rough popularity weights. Walking-type interests are a few among many, so any
# wandering comes from who a person is, not from the instructions.
INTERESTS = {"gaming": 5, "cafés": 4, "street food": 4, "reading": 3, "shopping": 3, "music": 4, "gym": 3,
             "basketball or football": 3, "running": 2, "hiking": 2, "photography": 2, "walking around neighbourhoods": 2,
             "harbour views": 2, "anime and comics": 2, "board games": 2, "cooking": 2, "volunteering": 1,
             "art and museums": 1, "history": 1, "dancing": 1, "swimming": 2, "badminton": 2}
FEELINGS = (["tired", "well rested", "full of energy"], [3, 5, 2])
MOODS = (["stressed", "fine", "cheerful", "bored", "a bit lonely", "restless"], [3, 6, 3, 2, 1, 1])


def traits(rng, role, age):
    """Spontaneity, interests and how today feels: drawn at random, never scripted."""
    spont = rng.betavariate(2, 3)
    style = ("Usually sticks closely to plans." if spont < 0.3 else
             "Sometimes changes plans on the day." if spont < 0.6 else "Often acts on a whim.")
    pool = list(INTERESTS)
    picks = []
    while len(picks) < rng.choice([2, 2, 3]):
        x = rng.choices(pool, weights=[INTERESTS[i] for i in pool])[0]
        if x not in picks:
            picks.append(x)
    notes = []
    if role in ("undergrad", "postgrad"):
        if rng.random() < 0.3:
            notes.append("An assignment is due tomorrow")
        if rng.random() < 0.15:
            notes.append("Money is tight this week")
    elif role == "staff" and rng.random() < 0.25:
        notes.append("A work deadline is coming up")
    if rng.random() < 0.15:
        notes.append("A friend said they might be free this evening")
    if age >= 60 and rng.random() < 0.3:
        notes.append("Knees ache on long staircases")
    today = {"feeling": f"{rng.choices(*FEELINGS)[0]} and {rng.choices(*MOODS)[0]}", "notes": notes}
    return {"spontaneity": round(spont, 2), "plans_style": style, "interests": picks, "today": today}


def pick_codes(world, names):
    return [c for c in (world.code_by_name(n) for n in names) if c]


def timetable(rng, world, faculty, n_classes):
    home_rooms = pick_codes(world, FACULTIES[faculty])
    shared = pick_codes(world, SHARED_ROOMS)
    starts = sorted(rng.sample(SLOTS, n_classes))
    out, busy_until = [], 0
    for h in starts:
        if h < busy_until:
            continue
        length = rng.choice([1, 1, 2])
        room = rng.choice(home_rooms if rng.random() < 0.6 else shared)
        out.append({"start": f"{h:02d}:30", "end": f"{h + length:02d}:20", "place": room,
                    "what": rng.choice(["lecture", "tutorial", "lab", "seminar"]) if faculty != "Law" else "lecture"})
        busy_until = h + length
    return out


def make(n, seed):
    world = World()
    rng = random.Random(seed)
    halls = [c for c, p in world.places.items() if p["category"] == "hall"]
    mtr = [c for c, p in world.places.items() if p["category"] == "mtr"]
    hku_mtr = [c for c in mtr if "HKU" in world.places[c]["name"]]
    bus = [c for c, p in world.places.items() if p["category"] == "bus"]
    homes = [c for c, p in world.places.items() if p["category"] == "building" and p["caption"].startswith("Residential")]
    agents = []
    for k in range(n):
        role = rng.choices(list(MIX), weights=list(MIX.values()))[0]
        name = f"{rng.choice(GIVEN)} {rng.choice(SURNAMES)}"
        a = {"id": f"A{k + 1:05d}", "name": name, "role": role, "personality": rng.choice(PERSONALITY),
             "habits": rng.sample(HABITS, 2), "pace": round(rng.uniform(0.85, 1.2), 2)}
        if role in ("undergrad", "postgrad"):
            fac = rng.choices(list(FACULTY_WEIGHT), weights=list(FACULTY_WEIGHT.values()))[0]
            a.update(age=rng.randint(18, 23) if role == "undergrad" else rng.randint(22, 35), faculty=fac,
                     year=rng.randint(1, 4) if role == "undergrad" else None)
            if rng.random() < HALL_SHARE[role]:
                a["home"] = rng.choice(halls); a["home_kind"] = "lives in this hall"
            else:
                a["home"] = rng.choice(hku_mtr if rng.random() < 0.75 else bus)
                a["home_kind"] = "commutes; arrives and leaves here"
            a["commitments"] = timetable(rng, world, fac, rng.randint(1, 4))
            a["start"] = "07:30" if a["home_kind"].startswith("lives") else hhmm(
                max(7 * 3600, (int(a["commitments"][0]["start"][:2]) * 60 + 30) * 60 - rng.randint(20, 50) * 60))
        elif role == "staff":
            fac = rng.choices(list(FACULTY_WEIGHT), weights=list(FACULTY_WEIGHT.values()))[0]
            office = rng.choice(pick_codes(world, FACULTIES[fac]))
            a.update(age=rng.randint(26, 64), faculty=fac, home=rng.choice(mtr if rng.random() < 0.8 else bus),
                     home_kind="commutes; arrives and leaves here", start=f"0{rng.randint(7, 9)}:{rng.choice(['00', '15', '30', '45'])}")
            a["commitments"] = [{"start": "09:30", "end": "17:30", "place": office, "what": "work in office"}]
            if rng.random() < 0.5:
                a["commitments"].append({"start": f"{rng.choice([10, 11, 14, 15])}:30", "end": f"{rng.choice([16, 17])}:20",
                                         "place": rng.choice(pick_codes(world, SHARED_ROOMS)), "what": "teach a class"})
                a["commitments"].sort(key=lambda c: c["start"])
        else:
            age = rng.randint(16, 82)
            home = rng.choice(homes)
            times = world.times_from(world.places[home]["node"])
            own_mtr = min(mtr, key=lambda c: times[world.places[c]["node"]])
            a.update(age=age, faculty=None, home=home, home_kind="lives here, in a flat in this building",
                     start=f"0{rng.randint(6, 9)}:{rng.choice(['00', '20', '40'])}")
            if age >= 62:
                a["occupation"] = "retired"
                market = min((c for c, p in world.places.items() if p["category"] == "shop"
                              and any(w in p["caption"].lower() for w in ("market", "supermarket", "groceries", "vegetable"))),
                             key=lambda c: times[world.places[c]["node"]])
                a["commitments"] = [{"start": f"{rng.randint(8, 11)}:00", "end": "", "place": market, "what": "buy groceries"}]
            elif age >= 20 and rng.random() < 0.55:
                a["occupation"] = "works outside the area"
                a["commitments"] = [{"start": f"0{rng.randint(7, 9)}:{rng.choice(['00', '30'])}", "end": f"{rng.randint(17, 20)}:{rng.choice(['00', '30'])}",
                                     "place": own_mtr, "what": "at work outside the area: take the MTR from this exit and come back here after work"}]
            elif age >= 18 and rng.random() < 0.4:
                a["occupation"] = "works a shift nearby"
                job = rng.choice([c for c, p in world.places.items() if p["category"] in ("food", "shop")
                                  and times[p["node"]] < 20 * 60])
                s = rng.choice([7, 10, 14])
                a["commitments"] = [{"start": f"{s:02d}:00", "end": f"{s + 8:02d}:00", "place": job, "what": "work a shift"}]
            else:
                a["occupation"] = "at home today" if age >= 18 else "secondary school student, a day off school"
                errand = rng.choice([c for c, p in world.places.items() if p["category"] in ("food", "shop", "money", "health")
                                     and times[p["node"]] < 15 * 60])
                a["commitments"] = [{"start": f"{rng.randint(10, 17)}:00", "end": "", "place": errand, "what": "an errand"}]
            a["role_detail"] = a["occupation"]
        a.update(traits(rng, role, a["age"]))
        agents.append(a)
    return agents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=str(C.DATA / "agents.jsonl"))
    args = ap.parse_args()
    agents = make(args.n, args.seed)
    with open(args.out, "w", encoding="utf-8") as f:
        for a in agents:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    roles = {r: sum(a["role"] == r for a in agents) for r in MIX}
    print(f"wrote {len(agents)} agents to {args.out}: {roles}")


if __name__ == "__main__":
    main()
