"""Create synthetic people with a personal profile and the fixed things they must do today.

Who they are follows the people in the area on a weekday, in their real proportions (the authors' decision,
method.md section 3): residents of the nine census areas from Kennedy Town to Sai Ying Pun (2021 Population
Census), plus HKU's students and staff (HKU, 2025/26). Every count below comes from
data/population_figures.csv. Where the figures do not settle something, the choice is marked ASSUMPTION and
listed in method.md, section 3, for the authors to decide.

    python make_agents.py --n 10000 --seed 7 --out out/<run>/people.jsonl
"""
import argparse
import json
import random

import config as C
from world import World, hhmm, parse_hhmm

# ---- Counts (data/population_figures.csv) ----
HKU = {"undergrad": 20103,               # HKU 2025/26 headcounts
       "taught postgrad": 20366 - 1206,  # minus 1,206 studying on programmes in Beijing and Shanghai
       "research postgrad": 4834,
       "staff": 10076}                   # excluding honorary and visiting staff
HALL_PLACES = 7800                       # HKU hall and residence places, university-wide
RESIDENTS = {                            # 2021 census, sum of the nine areas = 143,781
    "works in Central & Western": 26413,
    "works outside Central & Western": 16442 + 10940 + 3542 + 1019 + 1440,   # other HK Island, Kowloon, NT, outside HK
    "works with no fixed place": 7809,
    "domestic helper": 9665,
    "works at home": 11272 - 9665,       # working at home, minus the domestic helpers
    "student": 18414,
    "retired": 25818,
    "home-maker": 5952,
    "unpaid carer": 2486,
    "not working": 12234,                # includes 3,445 unemployed
}
CENSUS_AGES = {"under 15": 14539, "15-24": 10619, "25-44": 45481, "45-64": 43062, "65+": 30080}   # for the check

# ---- ASSUMPTIONS the figures do not settle (method.md, section 3) ----
WORK_IN_AREA = 0.5      # share of residents working in Central & Western whose workplace is inside the study area
SCHOOL_PUPILS = 0.7     # share of resident students at school (age 6 to 17) rather than college elsewhere
MTR_SHARE = 0.75        # share of commuters (HKU people and residents working away) who use the MTR, not a bus
AGES = {                # age range of each kind of resident
    "works in Central & Western": (20, 64), "works outside Central & Western": (20, 64),
    "works with no fixed place": (20, 64), "domestic helper": (25, 55), "works at home": (25, 64),
    "student": None, "retired": (65, 95), "home-maker": (25, 70), "unpaid carer": (30, 80), "not working": (18, 80),
}

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


CENSUS_BANDS = [(0, 14, 14539), (15, 24, 10619), (25, 44, 45481), (45, 64, 43062), (65, 95, 30080)]


def census_age(rng, lo, hi):
    """An age between lo and hi, each year weighted by how many residents of that age band the census counts
    per year of age, so ages within a range follow the census shape."""
    years = list(range(lo, hi + 1))
    w = [next(n / (b - a + 1) for a, b, n in CENSUS_BANDS if a <= y <= b) for y in years]
    return rng.choices(years, weights=w)[0]


def mix():
    """Shares of each kind of person, from the counts above."""
    total = sum(HKU.values()) + sum(RESIDENTS.values())
    out = {f"HKU {k}": v / total for k, v in HKU.items()}
    out.update({f"resident: {k}": v / total for k, v in RESIDENTS.items()})
    return out


def within(world, times, cats, max_min, rng, fallback=None):
    """A random place of these categories within max_min minutes' walk."""
    near = [c for c, p in world.places.items() if p["category"] in cats and times[p["node"]] <= max_min * 60]
    return rng.choice(near) if near else fallback


def make(n, seed):
    world = World()
    rng = random.Random(seed)
    halls = [c for c, p in world.places.items() if p["category"] == "hall"]
    mtr = [c for c, p in world.places.items() if p["category"] == "mtr"]
    hku_mtr = [c for c in mtr if "HKU" in world.places[c]["name"]]
    bus = [c for c, p in world.places.items() if p["category"] == "bus"]
    homes = [c for c, p in world.places.items() if p["category"] == "building" and p["caption"].startswith("Residential")]
    markets = [c for c, p in world.places.items() if p["category"] == "shop"
               and any(w in p["caption"].lower() for w in ("market", "supermarket", "groceries", "vegetable"))]
    shares = mix()
    kinds, weights = list(shares), list(shares.values())
    hall_share = HALL_PLACES / sum(v for k, v in HKU.items() if k != "staff")
    agents = []
    for k in range(n):
        kind = rng.choices(kinds, weights=weights)[0]
        name = f"{rng.choice(GIVEN)} {rng.choice(SURNAMES)}"
        a = {"id": f"A{k + 1:05d}", "name": name, "kind": kind, "personality": rng.choice(PERSONALITY),
             "habits": rng.sample(HABITS, 2), "pace": round(rng.uniform(0.85, 1.2), 2)}
        if kind in ("HKU undergrad", "HKU taught postgrad", "HKU research postgrad"):
            role = "undergrad" if kind == "HKU undergrad" else "postgrad"
            fac = rng.choices(list(FACULTY_WEIGHT), weights=list(FACULTY_WEIGHT.values()))[0]
            a.update(role=role, role_detail=kind[4:], faculty=fac,
                     age=rng.randint(18, 23) if role == "undergrad" else rng.randint(22, 35),
                     year=rng.randint(1, 4) if role == "undergrad" else None)
            if rng.random() < hall_share:
                a["home"] = rng.choice(halls); a["home_kind"] = "lives in this hall"
            else:
                a["home"] = rng.choice(hku_mtr if rng.random() < MTR_SHARE else bus)
                a["home_kind"] = "commutes; arrives and leaves here"
            if kind == "HKU research postgrad":
                office = rng.choice(pick_codes(world, FACULTIES[fac]))
                a["commitments"] = [{"start": "09:30", "end": f"{rng.randint(17, 19)}:30", "place": office, "what": "research work in the lab or office"}]
            else:
                a["commitments"] = timetable(rng, world, fac, rng.randint(1, 4))
            first = int(a["commitments"][0]["start"][:2]) * 3600 + int(a["commitments"][0]["start"][3:]) * 60
            a["start"] = "07:30" if a["home_kind"].startswith("lives") else hhmm(max(7 * 3600, first - rng.randint(20, 50) * 60))
        elif kind == "HKU staff":
            fac = rng.choices(list(FACULTY_WEIGHT), weights=list(FACULTY_WEIGHT.values()))[0]
            office = rng.choice(pick_codes(world, FACULTIES[fac]))
            a.update(role="staff", role_detail="HKU staff", age=rng.randint(26, 64), faculty=fac,
                     home=rng.choice(mtr if rng.random() < MTR_SHARE else bus),
                     home_kind="commutes; arrives and leaves here", start=f"0{rng.randint(7, 9)}:{rng.choice(['00', '15', '30', '45'])}")
            a["commitments"] = [{"start": "09:30", "end": "17:30", "place": office, "what": "work in office"}]
            if rng.random() < 0.5:
                a["commitments"].append({"start": f"{rng.choice([10, 11, 14, 15])}:30", "end": f"{rng.choice([16, 17])}:20",
                                         "place": rng.choice(pick_codes(world, SHARED_ROOMS)), "what": "teach a class"})
                a["commitments"].sort(key=lambda c: c["start"])
        else:
            occ = kind.split(": ", 1)[1]
            home = rng.choice(homes)
            times = world.times_from(world.places[home]["node"])
            own_mtr = min(mtr, key=lambda c: times[world.places[c]["node"]])
            exit_ = own_mtr if rng.random() < MTR_SHARE else min(bus, key=lambda c: times[world.places[c]["node"]])
            market = min(markets, key=lambda c: times[world.places[c]["node"]]) if markets else None
            if occ == "student":
                pupil = rng.random() < SCHOOL_PUPILS
                age = census_age(rng, 6, 17) if pupil else census_age(rng, 18, 24)
                occ = "school pupil" if pupil else "student at a college elsewhere"
            else:
                age = census_age(rng, *AGES[occ])
            a.update(role="resident", role_detail=occ, occupation=occ, age=age, faculty=None, home=home,
                     home_kind="lives here, in a flat in this building", start=f"0{rng.randint(6, 8)}:{rng.choice(['00', '20', '40'])}")
            c = []
            if occ == "works in Central & Western":
                if rng.random() < WORK_IN_AREA:
                    job = within(world, times, ("food", "shop", "service", "money", "health", "school", "building"), 25, rng)
                    s = rng.choice([7, 9, 10, 14])
                    c.append({"start": f"{s:02d}:00", "end": f"{s + 8:02d}:00", "place": job, "what": "work"})
                    a["occupation"] = "works in the area"
                else:
                    c.append({"start": f"0{rng.randint(7, 9)}:{rng.choice(['00', '30'])}", "end": f"{rng.randint(17, 19)}:{rng.choice(['00', '30'])}",
                              "place": exit_, "what": "at work in Central or Sheung Wan: leave from here and come back here after work"})
                    a["occupation"] = "works elsewhere in Central & Western"
            elif occ in ("works outside Central & Western", "student at a college elsewhere"):
                c.append({"start": f"0{rng.randint(7, 9)}:{rng.choice(['00', '30'])}", "end": f"{rng.randint(17, 20)}:{rng.choice(['00', '30'])}",
                          "place": exit_, "what": ("at work" if occ.startswith("works") else "at college") + " outside the area: leave from here and come back here after"})
            elif occ == "works with no fixed place":
                for h in sorted(rng.sample(range(9, 17), 3)):
                    c.append({"start": f"{h:02d}:00", "end": "", "place": within(world, times, ("building", "shop", "food", "service"), 30, rng, home),
                              "what": "a job at this address"})
            elif occ == "school pupil":
                school = within(world, times, ("school",), 25, rng)
                if school:
                    c.append({"start": "08:00", "end": "15:30", "place": school, "what": "school"})
            elif occ == "domestic helper":
                if market:
                    c.append({"start": f"0{rng.randint(8, 9)}:00", "end": "", "place": market, "what": "buy groceries for the family"})
                school = within(world, times, ("school",), 20, rng)
                if school and rng.random() < 0.5:
                    c.append({"start": "15:30", "end": "", "place": school, "what": "pick up the family's child from school"})
            elif occ == "retired" or occ == "home-maker":
                if market:
                    c.append({"start": f"{rng.randint(8, 11):02d}:00", "end": "", "place": market, "what": "buy groceries"})
            elif occ == "unpaid carer":
                clinic = within(world, times, ("health",), 30, rng)
                if clinic:
                    c.append({"start": f"{rng.randint(9, 15):02d}:00", "end": "", "place": clinic, "what": "accompany a family member to the clinic or pharmacy"})
            if not c and occ not in ("works at home",):
                errand = within(world, times, ("food", "shop", "money", "health"), 15, rng)
                if errand:
                    c.append({"start": f"{rng.randint(10, 17)}:00", "end": "", "place": errand, "what": "an errand"})
            a["commitments"] = sorted(c, key=lambda x: x["start"])
            if c:
                first = int(a["commitments"][0]["start"][:2]) * 3600 + int(a["commitments"][0]["start"][3:]) * 60
                a["start"] = hhmm(max(6 * 3600, min(parse_hhmm(a["start"]), first - 30 * 60)))
        a.update(traits(rng, a["role"], a["age"]))
        agents.append(a)
    return agents


def check(agents):
    """The generated mix against the census and HKU proportions."""
    n = len(agents)
    want = mix()
    got = {}
    for a in agents:
        got[a["kind"]] = got.get(a["kind"], 0) + 1
    lines = [f"{'kind':48} {'target':>7} {'made':>7}"]
    for k, v in want.items():
        lines.append(f"{k:48} {100 * v:6.1f}% {100 * got.get(k, 0) / n:6.1f}%")
    res = [a for a in agents if a["role"] == "resident"]
    bands = {"under 15": (0, 14), "15-24": (15, 24), "25-44": (25, 44), "45-64": (45, 64), "65+": (65, 200)}
    tot = sum(CENSUS_AGES.values())
    lines.append(f"\nresidents' ages (census includes children under 6, who are not simulated on their own):")
    for b, (lo, hi) in bands.items():
        m = sum(lo <= a["age"] <= hi for a in res)
        lines.append(f"{b:48} {100 * CENSUS_AGES[b] / tot:6.1f}% {100 * m / max(1, len(res)):6.1f}%")
    return "\n".join(lines)


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
    print(f"wrote {len(agents)} agents to {args.out}")
    print(check(agents))


if __name__ == "__main__":
    main()
