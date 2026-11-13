"""Write data/places.csv: one row per place with a caption and aliases the agents can search.

Edit the caption and aliases columns by hand (Excel is fine). Running this again after a map rebuild
keeps every caption and alias you changed, matched by place name.

    python captions.py
"""
import csv
import json

import config as C

# Hand-written captions for HKU buildings. Checked against general knowledge, not an official list:
# the team should confirm or correct these in data/places.csv.
KNOWN = {
    "Central Podium": ("Centennial Campus podium (CPD): classrooms and lecture rooms linking the three towers", "CPD; Centennial Campus"),
    "Run Run Shaw Tower": ("Centennial Campus tower: Faculty of Arts offices and classrooms", "Centennial Campus"),
    "The University of Hong Kong Run Run Shaw Tower": ("Centennial Campus tower: Faculty of Arts offices and classrooms", "Centennial Campus"),
    "The Jockey Club Tower": ("Centennial Campus tower: Faculty of Social Sciences offices and classrooms", "Centennial Campus"),
    "Cheng Yu Tung Tower": ("Centennial Campus tower: Faculty of Law offices and classrooms", "Centennial Campus"),
    "Lee Shau Kee Lecture Centre": ("Large lecture theatres on Centennial Campus", "Centennial Campus"),
    "Main Library (Old Wing)": ("Main Library: books, quiet study desks, open into the evening", "library; study"),
    "Library Extension": ("Main Library extension: study desks and collections", "library; study"),
    "Chi Wah Learning Commons": ("Student study space with group rooms and computers", "study; learning commons"),
    "Main Building": ("Historic Main Building with Loke Yew Hall: offices and ceremonies", ""),
    "Haking Wong Building": ("Faculty of Engineering: labs, classrooms and offices", "engineering"),
    "Haking Wong Podium": ("Engineering podium with classrooms", "engineering"),
    "Chow Yei Ching Building": ("Engineering and computer science classrooms and labs", "engineering; computer science"),
    "K.K. Leung Building": ("Faculty of Business and Economics: classrooms and offices", "business; economics"),
    "Meng Wah Complex": ("Classrooms, lecture theatres and offices", "lecture"),
    "Knowles Building": ("Classrooms and departmental offices", "lecture"),
    "Chong Yuet Ming Amenities Centre": ("Canteen, shops and student services", "canteen; food; shops"),
    "University Health Service, The University of Hong Kong": ("Campus clinic for students and staff", "clinic; doctor"),
    "Rayson Huang Theatre": ("Theatre used for big lectures, shows and events", "lecture; theatre"),
    "Fung Ping Shan Building": ("University Museum and Art Gallery", "museum"),
    "Graduate House": ("Postgraduate residence with a cafe", "residence; cafe"),
    "Large Moot Court": ("Law school courtroom used for teaching", "law"),
    "Visitor and Information Centre": ("Information desk for visitors", ""),
    "HSBC": ("Bank branch on campus", "bank; ATM"),
    "The Bank of East Asia HKU Branch": ("Bank branch on campus", "bank; ATM"),
    "Centennial Gate": ("Entrance to the campus", "gate; entrance"),
    "Yuet Ming Fountain": ("Fountain and open space on campus, a meeting point", "meeting point"),
}
SCIENCE = ("Science", "Biological", "Physics", "Chemistry")

CAT_TEXT = {
    "hall": "Student residence hall: residents sleep here and eat in the hall",
    "mtr": "MTR station exit: where people arrive and leave by train",
    "bus": "Bus stop",
    "library": "Library",
    "park": "Park or sports ground",
    "hku": "HKU campus building with classrooms or offices",
    "toilet": "Public toilet",
    "worship": "Place of worship",
    "school": "School (not part of HKU)",
}
SHOP_TEXT = {
    "convenience": ("Convenience store: snacks, drinks, daily items", "snacks; drinks; 7-Eleven; Circle K"),
    "supermarket": ("Supermarket: groceries and daily items", "groceries; food shopping"),
    "bakery": ("Bakery: bread, buns and pastries", "bread; snacks; breakfast"),
    "clothes": ("Clothes shop", "clothes; fashion"),
    "books": ("Bookshop", "books; stationery"),
    "stationery": ("Stationery shop", "stationery; printing"),
    "mobile_phone": ("Mobile phone shop", "phone; electronics"),
    "electronics": ("Electronics shop", "electronics; gadgets"),
    "hairdresser": ("Hair salon", "haircut"),
    "beauty": ("Beauty salon", "beauty"),
    "chemist": ("Personal care and pharmacy goods (e.g. Watsons, Mannings)", "toiletries; medicine"),
    "laundry": ("Laundry", "laundry; washing"),
    "dry_cleaning": ("Dry cleaner", "laundry"),
    "seafood": ("Seafood shop", "fish; market"),
    "butcher": ("Butcher", "meat; market"),
    "greengrocer": ("Fruit and vegetable shop", "fruit; vegetables; market"),
    "optician": ("Optician", "glasses"),
    "copyshop": ("Print and copy shop", "printing; copies"),
}
BUILDING_TEXT = {
    "residential": "Residential building: people's homes", "apartments": "Residential building: people's homes",
    "house": "House", "commercial": "Office or commercial building", "office": "Office building",
    "retail": "Shops and commercial building", "hotel": "Hotel", "church": "Church", "hospital": "Hospital building",
    "public": "Public building", "government": "Government building", "industrial": "Industrial building",
    "school": "School building", "university": "University building",
}


def auto_caption(p):
    name, cat, t = p["name"], p["cat"], p.get("tags", {})
    hours = f" · open {t['opening_hours']}" if t.get("opening_hours") and len(t["opening_hours"]) < 40 else ""
    cap, alias = _caption(name, cat, t)
    return cap + hours, alias


def _caption(name, cat, t):
    if name in KNOWN:
        return KNOWN[name]
    if cat == "hku" and any(s in name for s in SCIENCE):
        return ("Faculty of Science: labs and classrooms", "science")
    if cat == "food":
        kind = t.get("amenity", "restaurant").replace("_", " ")
        cuisine = t.get("cuisine", "").replace(";", ", ").replace("_", " ")
        return (f"{kind.capitalize()}" + (f" serving {cuisine}" if cuisine else ""), "food; eat; " + kind)
    if cat == "shop":
        s = t.get("shop", "shop")
        if s in SHOP_TEXT:
            return SHOP_TEXT[s]
        return (f"{s.replace('_', ' ').capitalize()} shop", "shop; buy")
    if cat == "money":
        if t.get("amenity") == "atm":
            return ("ATM: withdraw cash", "cash; money; bank")
        return (f"{t.get('amenity', 'bank').replace('_', ' ').capitalize()}: cash and banking", "bank; ATM; money")
    if cat == "health":
        a = t.get("amenity")
        text = {"pharmacy": "Pharmacy: medicine", "clinic": "Clinic: see a doctor", "doctors": "Doctor's clinic",
                "hospital": "Hospital", "dentist": "Dentist", "veterinary": "Vet for pets"}.get(a, "Health service")
        return (text, "health; doctor; medicine")
    if cat == "vending":
        if t.get("amenity") == "vending_machine":
            return (f"Vending machine selling {t.get('vending', 'drinks').replace('_', ' ').replace(';', ', ')}", "drinks; snacks; vending")
        return ("Drinking water fountain: refill a bottle", "water; drink; refill")
    if cat == "worship":
        return (f"Place of worship ({t.get('religion', 'religion unknown')})", "church; temple; pray")
    if cat == "service":
        return (t.get("amenity", "public service").replace("_", " ").capitalize(), "service")
    if cat == "building":
        if t.get("tourism") in ("hotel", "hostel", "guest_house"):
            return (t["tourism"].replace("_", " ").capitalize(), "stay; hotel")
        b = t.get("building", "yes")
        return (BUILDING_TEXT.get(b, "Building"), "building")
    if cat == "sight":
        if t.get("tourism") == "viewpoint":
            return ("Viewpoint", "view; sight")
        if t.get("historic"):
            return (f"Historic {t['historic'].replace('_', ' ')}", "history; sight")
        if t.get("tourism") in ("museum", "gallery"):
            return (t["tourism"].capitalize(), "museum; gallery; sight")
        if t.get("man_made") == "pier" or any(w in name for w in ("Pier", "Promenade", "Waterfront", "Praya")):
            return ("Waterfront by the harbour", "waterfront; harbour; sea; sight")
        return ("Local sight or landmark", "sight; landmark")
    if cat == "park":
        return (f"{t.get('leisure', 'park').replace('_', ' ').capitalize()}: exercise, rest or meet friends", "exercise; rest")
    return (CAT_TEXT.get(cat, ""), "")


def main():
    graph = json.loads((C.DATA / "graph.json").read_text(encoding="utf-8"))
    path = C.DATA / "places.csv"
    edited = {}
    if path.exists():
        with path.open(encoding="utf-8-sig") as f:
            edited = {r["name"]: r for r in csv.DictReader(f)}
    rows = []
    for p in graph["places"]:
        cap, alias = auto_caption(p)
        old = edited.get(p["name"])
        if old:
            cap, alias = old["caption"] or cap, old["aliases"] or alias
        rows.append({"code": p["code"], "name": p["name"], "category": p["cat"], "caption": cap, "aliases": alias,
                     "lat": p["lat"], "lon": p["lon"]})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} places to {path} ({sum(1 for r in rows if r['name'] in edited)} kept from earlier edits)")


if __name__ == "__main__":
    main()
