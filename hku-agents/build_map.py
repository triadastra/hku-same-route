"""Download the walking network and places around HKU from OpenStreetMap and save data/graph.json.

The graph keeps only junctions, places and lifts as nodes; every chain of path between them becomes
one segment with its length, walking time, whether it has steps, lighting and its drawn shape.

    python build_map.py            # downloads (cached in data/osm_*.json) and builds
"""
import json
import math
import time
import urllib.parse
import urllib.request
from collections import defaultdict

import config as C

WALKABLE = {
    "footway", "path", "pedestrian", "steps", "corridor", "living_street", "residential", "service",
    "unclassified", "tertiary", "tertiary_link", "secondary", "secondary_link", "primary",
    "primary_link", "track", "elevator", "cycleway",
}
NO_FOOT = {"no", "private"}

HKU_CENTRE = (22.2830, 114.1371)


def overpass(query, cache_name):
    path = C.DATA / f"osm_{cache_name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["elements"]
    body = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(C.OVERPASS_URL, body, headers={"User-Agent": C.USER_AGENT, "Accept": "application/json"})
    for attempt in range(4):
        try:
            raw = urllib.request.urlopen(req, timeout=180).read()
            break
        except Exception as e:  # Overpass is a shared free service: back off and retry
            print(f"  overpass {cache_name} failed ({e}), retrying")
            time.sleep(10 * (attempt + 1))
    else:
        raise SystemExit("Overpass is not answering; try again in a few minutes.")
    C.DATA.mkdir(exist_ok=True)
    path.write_bytes(raw)
    return json.loads(raw)["elements"]


def metres(lat, lon):
    lat0, lon0 = HKU_CENTRE
    return ((lon - lon0) * math.cos(math.radians(lat0)) * 111320.0, (lat - lat0) * 110540.0)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def fetch():
    s, w, n, e = C.BBOX
    bb = f"{s},{w},{n},{e}"
    ways = overpass(f'[out:json][timeout:120];way["highway"]({bb});out body;>;out skel qt;', "ways")
    # `out skel` drops node tags, so lifts (highway=elevator nodes) need their own query
    lifts = overpass(f'[out:json][timeout:60];node["highway"="elevator"]({bb});out tags;', "lifts")
    lift_ids = {el["id"] for el in lifts}
    for el in ways:
        if el["type"] == "node" and el["id"] in lift_ids:
            el.setdefault("tags", {})["highway"] = "elevator"
    # Which features sit on the HKU campus (so their buildings count as university buildings)
    campus = overpass(f"""[out:json][timeout:120];
(
  way["amenity"="university"]["name"~"University of Hong Kong"]({bb});
  relation["amenity"="university"]["name"~"University of Hong Kong"]({bb});
)->.u;
.u map_to_area->.campus;
(nwr["building"](area.campus); nwr["amenity"](area.campus); nwr["leisure"](area.campus););
out ids;""", "campus_ids")
    campus_ids = {(el["type"], el["id"]) for el in campus}
    # Every named building and every amenity, shop, park, sight and transport stop in the area
    places = overpass(f"""[out:json][timeout:180];
(
  nwr["building"]["name"]({bb});
  nwr["amenity"]({bb});
  nwr["shop"]({bb});
  nwr["leisure"]["name"]({bb});
  nwr["tourism"]({bb});
  nwr["historic"]["name"]({bb});
  node["railway"="subway_entrance"]({bb});
  nwr["highway"="bus_stop"]({bb});
  nwr["name"~"Promenade|Waterfront|Pier|Praya"]({bb});
);
out center tags;""", "places_all")
    for el in places:
        el["campus"] = (el["type"], el["id"]) in campus_ids
    return ways, places


def build_graph(elements):
    coord, ways = {}, []
    lift_nodes = set()
    for el in elements:
        if el["type"] == "node":
            coord[el["id"]] = metres(el["lat"], el["lon"])
            if el.get("tags", {}).get("highway") == "elevator":
                lift_nodes.add(el["id"])
        elif el["type"] == "way":
            t = el.get("tags", {})
            hw = t.get("highway")
            if hw not in WALKABLE or t.get("foot") in NO_FOOT or t.get("access") == "no":
                continue
            if t.get("area") == "yes" and hw != "pedestrian":
                continue
            ways.append(el)
    latlon = {el["id"]: (el["lat"], el["lon"]) for el in elements if el["type"] == "node"}

    # Raw node-level adjacency, one entry per OSM segment
    nbrs = defaultdict(set)
    seg_info = {}
    for w in ways:
        t = w["tags"]
        steps = t["highway"] == "steps"
        lift = t["highway"] == "elevator"
        lit = t.get("lit")
        lit = False if lit == "no" else True if lit in ("yes", "24/7", "automatic") else None
        nd = [x for x in w["nodes"] if x in coord]
        for a, b in zip(nd, nd[1:]):
            if a == b:
                continue
            nbrs[a].add(b); nbrs[b].add(a)
            seg_info[(a, b)] = seg_info[(b, a)] = (steps, lift, lit, w["id"], t.get("name", ""))
    return coord, latlon, nbrs, seg_info, lift_nodes


def components(nodes, nbrs):
    seen, best = set(), []
    for s in nodes:
        if s in seen:
            continue
        comp, stack = [], [s]
        seen.add(s)
        while stack:
            u = stack.pop(); comp.append(u)
            for v in nbrs[u]:
                if v not in seen:
                    seen.add(v); stack.append(v)
        if len(comp) > len(best):
            best = comp
    return set(best)


FOOD = {"restaurant", "cafe", "fast_food", "food_court", "canteen", "bar", "pub", "ice_cream", "biergarten"}
MONEY = {"atm", "bank", "bureau_de_change", "money_transfer"}
HEALTH = {"pharmacy", "clinic", "doctors", "hospital", "dentist", "veterinary"}
SCHOOL = {"school", "kindergarten", "college", "language_school", "music_school", "training", "prep_school"}
VENDING = {"vending_machine", "drinking_water", "water_point"}
# Street furniture and car infrastructure: not somewhere a person walks to
SKIP = {"parking", "parking_space", "parking_entrance", "bicycle_parking", "motorcycle_parking", "bench",
        "waste_basket", "waste_disposal", "recycling", "fuel", "charging_station", "taxi", "shelter", "clock",
        "post_box", "telephone", "loading_dock", "grit_bin", "car_wash", "car_rental", "smoking_area",
        "letter_box", "fountain", "trolley_bay", "lounger", "atm;bank", "compressed_air", "vacuum_cleaner",
        "university"}  # the campus outline itself; its buildings are added one by one
SIGHT_WORDS = ("Promenade", "Waterfront", "Pier", "Praya")


def classify(tags, campus):
    """Category of a map feature, or None when nobody would walk to it."""
    name, am = tags.get("name", ""), tags.get("amenity")
    if tags.get("railway") == "subway_entrance":
        return "mtr"
    if tags.get("highway") == "bus_stop" or am == "bus_station":
        return "bus"
    if am in SKIP:
        return None
    if tags.get("building") == "dormitory" or (tags.get("building") and (name.endswith(" Hall") or "Hall of" in name
                                                                          or name.endswith("College"))):
        return "hall"
    if am == "library":
        return "library"
    if am in FOOD:
        return "food"
    if am in MONEY:
        return "money"
    if am in HEALTH:
        return "health"
    if am == "toilets":
        return "toilet"
    if am in VENDING:
        return "vending"
    if am == "place_of_worship":
        return "worship"
    if tags.get("shop") or am == "marketplace":
        return "shop"
    if not tags.get("building") and (tags.get("tourism") in ("viewpoint", "attraction", "museum", "gallery", "artwork")
                                     or tags.get("historic") or tags.get("man_made") == "pier"
                                     or any(w in name for w in SIGHT_WORDS)):
        return "sight"
    if tags.get("tourism") in ("museum", "gallery"):
        return "sight"
    if tags.get("leisure"):
        return "park"
    if campus:
        return "hku"
    if am in SCHOOL or tags.get("building") in ("school", "kindergarten"):
        return "school"
    if am:
        return "service"
    if tags.get("tourism") in ("hotel", "hostel", "guest_house", "apartment"):
        return "building"
    if tags.get("building") and name:
        return "building"
    return None


GENERIC = {  # names for amenities that have none on the map
    "toilet": lambda t: "Public toilet",
    "vending": lambda t: "Drinking water" if t.get("amenity") != "vending_machine" else
    f"Vending machine ({t.get('vending', 'drinks').replace('_', ' ').split(';')[0]})",
    "money": lambda t: (f"ATM ({english(t.get('operator') or t.get('brand'))})" if t.get("operator") or t.get("brand") else "ATM")
    if t.get("amenity") == "atm" else (english(t.get("brand")) or t.get("amenity").replace("_", " ").capitalize()),
    "shop": lambda t: (t.get("brand") or f"{t.get('shop', 'shop').replace('_', ' ').capitalize()} shop"),
    "food": lambda t: t.get("brand") or t.get("amenity").replace("_", " ").capitalize(),
    "health": lambda t: t.get("brand") or t.get("amenity").capitalize(),
    "worship": lambda t: f"{t.get('religion', 'place of worship').capitalize()} place of worship",
    "bus": lambda t: "Bus stop",
    "service": lambda t: t.get("amenity", "service").replace("_", " ").capitalize(),
    "school": lambda t: t.get("amenity", "school").replace("_", " ").capitalize(),
    "park": lambda t: t.get("leisure", "park").replace("_", " ").capitalize(),
}


STATIONS = {"HKU": (22.2840, 114.1350), "Kennedy Town": (22.2813, 114.1287), "Sai Ying Pun": (22.2856, 114.1424)}


def english(s):
    """'薄扶林道 Pok Fu Lam Road' -> 'Pok Fu Lam Road'; pure Chinese names are kept as they are."""
    if not s:
        return s
    latin = "".join(ch for ch in s if ord(ch) < 0x2E80).strip(" -/")
    return latin if sum(ch.isalpha() for ch in latin) >= 3 else s


def place_name(tags, cat, lat, lon):
    if cat == "mtr":
        stn = min(STATIONS, key=lambda k: math.hypot(STATIONS[k][0] - lat, STATIONS[k][1] - lon))
        street = english(tags.get("name:en") or tags.get("name", ""))
        return f"MTR {stn} Exit {tags.get('ref', '?')}" + (f" ({street})" if street else "")
    return english(tags.get("name:en") or tags.get("name"))


def main():
    elements, place_els = fetch()
    coord, latlon, nbrs, seg_info, lift_nodes = build_graph(elements)
    main_comp = components(list(nbrs), nbrs)
    print(f"walk network: {len(nbrs)} OSM nodes, largest connected part {len(main_comp)}")

    # Places, snapped to the nearest node of the main walking network
    grid = defaultdict(list)
    for nid in main_comp:
        x, y = coord[nid]
        grid[(int(x // 50), int(y // 50))].append(nid)

    def snap(p):
        gx, gy = int(p[0] // 50), int(p[1] // 50)
        best, bd = None, 1e18
        for r in range(0, 6):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    for nid in grid.get((gx + dx, gy + dy), ()):
                        d = dist(coord[nid], p)
                        if d < bd:
                            best, bd = nid, d
            if best is not None and bd < r * 50:
                break
        return best, bd

    places, seen = [], set()
    for el in place_els:
        t = el.get("tags", {})
        if (t.get("type") in ("route", "route_master") or any(k.startswith("seamark") for k in t)
                or "Cardinal Mark" in t.get("name", "")):
            continue  # bus routes and sea buoys are not places to walk to
        cat = classify(t, el["campus"])
        if not cat:
            continue
        lat, lon = (el["lat"], el["lon"]) if "lat" in el else (el["center"]["lat"], el["center"]["lon"])
        name = place_name(t, cat, lat, lon) if t.get("name") or cat == "mtr" else None
        generic = not name
        if generic:
            if cat not in GENERIC:
                continue
            name = GENERIC[cat](t)
        if "Pumping Station" in name or "Treatment Works" in name:
            continue
        key = (name, cat, round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)
        p = metres(lat, lon)
        node, d = snap(p)
        if node is None or d > 150:
            continue
        places.append({"name": name, "cat": cat, "osm_node": node, "lat": round(lat, 6), "lon": round(lon, 6), "xy": p,
                       "generic": generic, "street": english(t.get("addr:street", "")),
                       "tags": {k: t[k] for k in ("cuisine", "operator", "brand", "building", "building:levels", "amenity",
                                                  "shop", "leisure", "description", "tourism", "historic", "man_made",
                                                  "religion", "vending", "opening_hours") if k in t}})

    # Unnamed amenities and repeated names (chain shops) get "near <landmark>" so each name is unique
    name_count = defaultdict(int)
    for p in places:
        name_count[p["name"]] += 1
    # reference points: places whose name is already unique, so labels never nest
    landmarks = [(p["name"], p["xy"]) for p in places if not p["generic"] and name_count[p["name"]] == 1
                 and p["cat"] in ("mtr", "hku", "hall", "sight", "park", "library", "building", "bus", "school")]
    for p in places:
        if p["generic"] or name_count[p["name"]] > 1:
            near = min((q for q in landmarks if q[0] != p["name"]), key=lambda q: dist(q[1], p["xy"]), default=None)
            where = p["street"] or (near[0] if near else "")
            if near and dist(near[1], p["xy"]) < 120:
                where = near[0]
            if where:
                p["name"] = f"{p['name']} near {where}" if p["generic"] else f"{p['name']} ({where})"
    seen_final = defaultdict(int)
    for p in places:  # anything still repeated gets a number
        seen_final[p["name"]] += 1
        if seen_final[p["name"]] > 1:
            p["name"] = f"{p['name']} #{seen_final[p['name']]}"

    keep = set(lift_nodes & main_comp)
    prefix = {"hku": "H", "hall": "R", "mtr": "M", "bus": "B", "food": "F", "shop": "S", "park": "P", "library": "L",
              "sight": "V", "money": "A", "health": "D", "toilet": "T", "vending": "N", "worship": "W", "school": "E",
              "service": "G", "building": "K"}
    order = list(prefix)
    places.sort(key=lambda p: (order.index(p["cat"]), dist(p["xy"], (0, 0))))  # nearest to HKU first
    counts = defaultdict(int)
    for p in places:
        keep.add(p["osm_node"])
        counts[p["cat"]] += 1
        p["code"] = f"{prefix[p['cat']]}{counts[p['cat']]:03d}"
        for k in ("xy", "generic", "street"):
            p.pop(k)

    # Contract chains of degree-2 nodes into single segments
    for nid in main_comp:
        if len(nbrs[nid]) != 2:
            keep.add(nid)
    index = {nid: i for i, nid in enumerate(sorted(keep))}
    edges, done = [], set()
    for s in index:
        for nxt in nbrs[s]:
            if (s, nxt) in done:
                continue
            chain = [s, nxt]
            while chain[-1] not in index:
                a, b = chain[-2], chain[-1]
                c = next(iter(nbrs[b] - {a}))
                chain.append(c)
                if len(chain) > 5000:
                    break
            for a, b in zip(chain, chain[1:]):
                done.add((a, b)); done.add((b, a))
            u, v = chain[0], chain[-1]
            if u == v:
                continue
            length = steps_len = 0.0
            lit_vals, lift, names = [], False, set()
            for a, b in zip(chain, chain[1:]):
                d = dist(coord[a], coord[b])
                st, lf, lt, wid, nm = seg_info[(a, b)]
                length += d
                if st:
                    steps_len += d
                lift |= lf
                lit_vals.append(lt)
                if nm:
                    names.add(nm)
            lift |= u in lift_nodes or v in lift_nodes
            secs = (length - steps_len) / C.WALK_SPEED + steps_len * C.STEPS_FACTOR / C.WALK_SPEED
            if lift:
                secs += C.LIFT_SECONDS / 2
            lit = False if False in lit_vals else (True if all(x is True for x in lit_vals) else None)
            edges.append({
                "u": index[u], "v": index[v], "len": round(length, 1), "secs": round(secs, 1),
                "steps": round(steps_len, 1), "lift": lift, "lit": lit, "name": " / ".join(sorted(names))[:60],
                "geom": [[round(latlon[n][0], 6), round(latlon[n][1], 6)] for n in chain],
            })
    nodes = [{"lat": round(latlon[nid][0], 6), "lon": round(latlon[nid][1], 6), "lift": nid in lift_nodes} for nid in sorted(keep)]
    for p in places:
        p["node"] = index[p.pop("osm_node")]

    out = {"bbox": C.BBOX, "nodes": nodes, "edges": edges, "places": places,
           "source": "OpenStreetMap contributors (ODbL), downloaded via Overpass API"}
    (C.DATA / "graph.json").write_text(json.dumps(out), encoding="utf-8")
    by_cat = defaultdict(int)
    for p in places:
        by_cat[p["cat"]] += 1
    print(f"graph: {len(nodes)} junctions, {len(edges)} segments, {sum(e['len'] for e in edges) / 1000:.1f} km of path")
    print(f"  steps segments {sum(1 for e in edges if e['steps'] > 0)}, lift segments {sum(e['lift'] for e in edges)}, "
          f"lighting known on {sum(e['lit'] is not None for e in edges)}")
    print("places:", dict(by_cat))


if __name__ == "__main__":
    main()
