"""County/city helpers for Michigan job locations.

County comes from (1) county names written in the posting title/location, or
(2) a city -> county lookup via OpenStreetMap Nominatim, cached in data/city_county.json
so each city is only looked up once.
"""
import json
import re
import time

import requests

from .paths import DATA_DIR

MI_COUNTIES = [
    "Alcona", "Alger", "Allegan", "Alpena", "Antrim", "Arenac", "Baraga", "Barry", "Bay", "Benzie",
    "Berrien", "Branch", "Calhoun", "Cass", "Charlevoix", "Cheboygan", "Chippewa", "Clare", "Clinton",
    "Crawford", "Delta", "Dickinson", "Eaton", "Emmet", "Genesee", "Gladwin", "Gogebic",
    "Grand Traverse", "Gratiot", "Hillsdale", "Houghton", "Huron", "Ingham", "Ionia", "Iosco", "Iron",
    "Isabella", "Jackson", "Kalamazoo", "Kalkaska", "Kent", "Keweenaw", "Lake", "Lapeer", "Leelanau",
    "Lenawee", "Livingston", "Luce", "Mackinac", "Macomb", "Manistee", "Marquette", "Mason", "Mecosta",
    "Menominee", "Midland", "Missaukee", "Monroe", "Montcalm", "Montmorency", "Muskegon", "Newaygo",
    "Oakland", "Oceana", "Ogemaw", "Ontonagon", "Osceola", "Oscoda", "Otsego", "Ottawa", "Presque Isle",
    "Roscommon", "Saginaw", "St. Clair", "St. Joseph", "Sanilac", "Schoolcraft", "Shiawassee", "Tuscola",
    "Van Buren", "Washtenaw", "Wayne", "Wexford",
]
_COUNTY_BY_LOWER = {c.lower(): c for c in MI_COUNTIES}
_COUNTY_BY_LOWER.update({"saint clair": "St. Clair", "st clair": "St. Clair", "saint joseph": "St. Joseph", "st joseph": "St. Joseph"})
# County names that are also common words; only accept these next to the word "County".
_AMBIGUOUS = {"Bay", "Lake", "Iron", "Delta", "Branch", "Mason", "Clare", "Cass", "Kent", "Huron", "Monroe",
              "Jackson", "Clinton", "Wayne", "Ottawa", "Livingston", "Chippewa", "Washtenaw", "Mackinac",
              "Marquette", "Midland", "Montcalm", "Eaton", "Barry", "Gladwin", "Benzie", "Emmet"}
_NAME_RE = "|".join(sorted((re.escape(c) for c in _COUNTY_BY_LOWER), key=len, reverse=True))
# "Huron/Tuscola County", "Clinton and Eaton County", "Otsego/Crawford/Oscoda Counties", "Montcalm and Ionia County"
_LIST_BEFORE_COUNTY = re.compile(
    rf"((?:\b(?:{_NAME_RE})\b\s*(?:/|,|&|and)\s*)*\b(?:{_NAME_RE})\b)\s+(?:County|Counties)\b", re.I)
# "Counties: Kent, Ottawa" / "(IONIA/MONTCALM)" style lists of unambiguous names
_ANY_NAME = re.compile(rf"\b({_NAME_RE})\b", re.I)

CACHE_FILE = DATA_DIR / "city_county.json"
_cache = None


def counties_in_text(text):
    """Find Michigan county names in free text. Returns a list in order of appearance."""
    if not text:
        return []
    found = []

    def add(name):
        c = _COUNTY_BY_LOWER.get(name.lower().replace("saint ", "st. ").strip())
        c = c or _COUNTY_BY_LOWER.get(name.lower())
        if c and c not in found:
            found.append(c)

    for m in _LIST_BEFORE_COUNTY.finditer(text):
        for n in _ANY_NAME.findall(m.group(1)):
            add(n)
    # Slash-separated lists without the word County, e.g. "(IONIA/MONTCALM)", "Shiawassee/Gratiot"
    for m in re.finditer(rf"\b(?:{_NAME_RE})\b(?:\s*/\s*\b(?:{_NAME_RE})\b)+", text, re.I):
        for n in _ANY_NAME.findall(m.group(0)):
            add(n)
    # Single unambiguous names standing alone, e.g. "Schoolcraft - SS", "Assistance Payments Worker - Presque Isle"
    for n in _ANY_NAME.findall(text):
        canon = _COUNTY_BY_LOWER.get(n.lower())
        if canon and canon not in _AMBIGUOUS:
            add(n)
    return found


def _load_cache():
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    return _cache


def save_cache():
    if _cache is not None:
        CACHE_FILE.write_text(json.dumps(dict(sorted(_cache.items())), indent=1), encoding="utf-8")


_last_call = 0.0


def county_for_city(city, log=print):
    """Look up the county for a Michigan city (cached). Returns None if unknown."""
    if not city:
        return None
    key = re.sub(r"\s+", " ", city).strip().lower()
    if key in ("", "various", "remote", "statewide", "multiple", "multiple locations", "michigan", "mi"):
        return None
    cache = _load_cache()
    if key in cache:
        return cache[key]
    global _last_call
    wait = 1.1 - (time.time() - _last_call)  # Nominatim usage policy: max 1 request/second
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    county = None
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "state": "Michigan", "country": "USA", "format": "json", "addressdetails": 1, "limit": 1},
            headers={"User-Agent": "michigan-title-iv-e-jobs/1.0 (job board builder)"},
            timeout=20,
        )
        r.raise_for_status()
        res = r.json()
        if res:
            addr = res[0].get("address", {})
            if addr.get("state") == "Michigan":
                name = (addr.get("county") or "").replace(" County", "").strip()
                county = _COUNTY_BY_LOWER.get(name.lower())
    except Exception as e:  # noqa: BLE001
        log(f"  county lookup failed for {city!r}: {e}")
        return None  # don't cache failures
    cache[key] = county
    return county


def split_location(raw):
    """Split a raw location like 'Grand Rapids, MI 49503' into (city, state)."""
    if not raw:
        return None, None
    s = re.sub(r"\s+", " ", raw).strip()
    s = re.sub(r"\b\d{5}(-\d{4})?\b", "", s).strip(" ,")
    s = re.sub(r",?\s*(US|USA|United States)$", "", s, flags=re.I).strip(" ,")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    state = None
    if parts and re.fullmatch(r"(MI|Michigan)", parts[-1], re.I):
        state = "MI"
        parts = parts[:-1]
    elif parts and re.fullmatch(r"[A-Z]{2}|[A-Za-z ]+", parts[-1]) and len(parts) > 1:
        state = parts[-1]
        parts = parts[:-1]
    city = parts[0] if parts else None
    if city and re.search(r"\bcounty\b", city, re.I):
        city = None
    return city, state
