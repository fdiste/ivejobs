"""Build the Title IV-E eligible job postings site.

Usage:  py -m ivejobs.build [--no-refresh-eligible] [--only "Agency Name"]
Output: docs/index.html, docs/jobs.json, docs/jobs.csv
"""
import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone

from . import geo
from .eligible import load_eligible_positions
from .matching import Matcher
from .paths import CONFIG_DIR, DOCS_DIR, TEMPLATE_DIR
from .sources import ATS_FETCHERS, neogov


def log(msg):
    print(msg, flush=True)


def employer_type(agency):
    """"Private" (default) or "Tribal", from the agency's "type" in config/agencies.json."""
    return "Tribal" if (agency.get("type") or "").lower() == "tribal" else "Private"


def fetch_private(agency):
    """Fetch one private or tribal agency's job board."""
    fetcher = ATS_FETCHERS.get(agency["ats"])
    if fetcher is None:
        raise ValueError(f"no fetcher for ATS {agency['ats']!r}")
    jobs = fetcher(agency, log=log)
    for j in jobs:
        j.update(source=agency["ats"], agency=agency["name"], employer_type=employer_type(agency))
        j.setdefault("description", "")
        # Boards that don't give a location (e.g. a list of PDFs) fall back to the agency's main office city.
        if agency.get("city") and not j.get("city") and not j.get("cities"):
            j.update(city=agency["city"], state=j.get("state") or "MI")
        j["id"] = f"{agency['ats']}-{j.get('id') or j['url']}"
    return jobs


def in_michigan(job):
    """Drop out-of-state postings from multi-state agencies (e.g. national boards)."""
    st = (job.get("state") or "").strip()
    if not st:
        return True
    return st.upper() in ("MI", "MICHIGAN")


def add_location(job):
    # Some boards list several cities per posting ("cities"); others a single "city".
    # "Fulton/Grand Rapids" means two cities.
    raw_cities = [part for c in (job.get("cities") or [job.get("city")]) if c for part in c.split("/")]
    cities = [re.sub(r"\s+", " ", c).strip(" ,") for c in raw_cities if c.strip()]
    cities = [c.title() if c.isupper() else c for c in cities]
    cities = [c for c in cities if c.lower() not in ("various", "remote", "statewide", "multiple locations", "anywhere")]
    # A title like "Case Manager- Benton Harbor Area" names the real work area; some boards only list headquarters.
    area = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?) Area\b", job["title"])
    if area and job["employer_type"] != "MDHHS" and area.group(1) not in cities and geo.county_for_city(area.group(1), log=log):
        cities = [area.group(1)]
    cities = list(dict.fromkeys(cities))
    job["city"] = ", ".join(cities) or None
    counties = geo.counties_in_text(" ".join(filter(None, [job.get("county_hint"), job["title"], job.get("location_raw")])))
    # MDHHS titles name the counties served, so the office city adds nothing; other boards often list several cities.
    if not counties or job["employer_type"] != "MDHHS":
        for c in cities:
            county = geo.county_for_city(c, log=log)
            if county and county not in counties:
                counties.append(county)
    job["counties"] = counties


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-refresh-eligible", action="store_true", help="use the cached eligible positions list")
    ap.add_argument("--only", help="only fetch this private or tribal agency (for testing)")
    args = ap.parse_args(argv)

    log("Loading eligible positions from michildwelfare.org ...")
    eligible = load_eligible_positions(refresh=not args.no_refresh_eligible, log=log)
    n_pos = sum(len(v) for v in eligible["groups"].values())
    log(f"  {n_pos} eligible positions (retrieved {eligible['fetched_at']})")
    matcher = Matcher(eligible, log=log)

    agencies = json.loads((CONFIG_DIR / "agencies.json").read_text(encoding="utf-8"))["agencies"]
    sources, raw = [], []

    log("Fetching MDHHS postings ...")
    try:
        jobs = neogov.fetch(matcher.mdhhs_departments, log=log)
        raw += jobs
        sources.append({"name": "MDHHS", "type": "MDHHS", "status": "ok", "careers_url": "https://www.governmentjobs.com/careers/michigan/mdhhs", "_jobs": jobs})
    except Exception as e:  # noqa: BLE001
        log(f"ERROR fetching MDHHS feed: {e}")
        sources.append({"name": "MDHHS", "type": "MDHHS", "status": "error", "error": str(e), "careers_url": "https://www.governmentjobs.com/careers/michigan/mdhhs", "_jobs": []})

    log("Fetching private and tribal agency postings ...")
    for a in agencies:
        if args.only and a["name"] != args.only:
            continue
        entry = {"name": a["name"], "type": employer_type(a), "careers_url": a.get("careers_url"), "_jobs": []}
        if a.get("ats") in (None, "manual"):
            entry["status"] = "manual"
        else:
            try:
                jobs = fetch_private(a)
                entry.update(status="ok", _jobs=jobs)
                raw += jobs
                log(f"  {a['name']}: {len(jobs)} postings")
            except Exception as e:  # noqa: BLE001
                entry.update(status="error", error=f"{type(e).__name__}: {e}"[:300])
                log(f"  {a['name']}: ERROR {entry['error']}")
        sources.append(entry)

    log("Matching postings to eligible positions ...")
    kept, seen = [], set()
    for j in raw:
        if j["id"] in seen or not in_michigan(j):
            continue
        seen.add(j["id"])
        roles = matcher.match(j)
        if not roles:
            continue
        j["roles"] = roles
        add_location(j)
        kept.append(j)
    geo.save_cache()
    for s in sources:
        ids = {j["id"] for j in s.pop("_jobs")}
        s["matched"] = sum(1 for j in kept if j["id"] in ids)

    fields = ["title", "agency", "employer_type", "counties", "city", "posted", "closes", "continuous", "roles", "url"]
    out_jobs = [{k: j.get(k) for k in fields} for j in kept]
    type_order = {"MDHHS": 0, "Private": 1, "Tribal": 2}
    out_jobs.sort(key=lambda j: (type_order.get(j["employer_type"], 9), j["agency"], j["title"]))
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "eligible": eligible,
        "sources": sorted(sources, key=lambda s: (type_order.get(s["type"], 9), s["name"].lower())),
        "jobs": out_jobs,
    }

    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "jobs.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    payload = json.dumps(data).replace("</", "<\\/")
    html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8").replace("__DATA__", payload)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    with open(DOCS_DIR / "jobs.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Job title", "Employer", "Employer type", "County", "City", "Posted", "Closes", "Continuous", "Eligible position", "Link"])
        for j in out_jobs:
            w.writerow([j["title"], j["agency"], j["employer_type"], ", ".join(j["counties"]), j["city"] or "",
                        j["posted"] or "", j["closes"] or "",
                        {True: "Yes", False: "No", None: "Not stated"}[j["continuous"]], "; ".join(j["roles"]), j["url"]])

    n = {t: sum(1 for j in out_jobs if j["employer_type"] == t) for t in type_order}
    errs = [s["name"] for s in sources if s["status"] == "error"]
    log(f"Done: {len(out_jobs)} eligible postings ({n['MDHHS']} MDHHS, {n['Private']} private, {n['Tribal']} tribal). "
        f"Wrote {DOCS_DIR / 'index.html'}")
    if errs:
        log(f"Sources with errors: {', '.join(errs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
