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


def fetch_private(agency):
    fetcher = ATS_FETCHERS.get(agency["ats"])
    if fetcher is None:
        raise ValueError(f"no fetcher for ATS {agency['ats']!r}")
    jobs = fetcher(agency, log=log)
    for j in jobs:
        j.update(source=agency["ats"], agency=agency["name"], employer_type="Private")
        j.setdefault("description", "")
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
    cities = [re.sub(r"\s+", " ", c).strip(" ,") for c in (job.get("cities") or [job.get("city")]) if c and c.strip()]
    cities = [c.title() if c.isupper() else c for c in cities]
    cities = [c for c in cities if c.lower() not in ("various", "remote", "statewide", "multiple locations", "anywhere")]
    # A title like "Case Manager- Benton Harbor Area" names the real work area; some boards only list headquarters.
    area = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?) Area\b", job["title"])
    if area and job["employer_type"] == "Private" and area.group(1) not in cities and geo.county_for_city(area.group(1), log=log):
        cities = [area.group(1)]
    cities = list(dict.fromkeys(cities))
    job["city"] = ", ".join(cities) or None
    counties = geo.counties_in_text(" ".join(filter(None, [job.get("county_hint"), job["title"], job.get("location_raw")])))
    # MDHHS titles name the counties served, so the office city adds nothing; private boards often list several cities.
    if not counties or job["employer_type"] == "Private":
        for c in cities:
            county = geo.county_for_city(c, log=log)
            if county and county not in counties:
                counties.append(county)
    job["counties"] = counties


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-refresh-eligible", action="store_true", help="use the cached eligible positions list")
    ap.add_argument("--only", help="only fetch this private agency (for testing)")
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
        sources.append({"name": "MDHHS", "status": "ok", "careers_url": "https://www.governmentjobs.com/careers/michigan/mdhhs", "_jobs": jobs})
    except Exception as e:  # noqa: BLE001
        log(f"ERROR fetching MDHHS feed: {e}")
        sources.append({"name": "MDHHS", "status": "error", "error": str(e), "careers_url": "https://www.governmentjobs.com/careers/michigan/mdhhs", "_jobs": []})

    log("Fetching private agency postings ...")
    for a in agencies:
        if args.only and a["name"] != args.only:
            continue
        entry = {"name": a["name"], "careers_url": a.get("careers_url"), "_jobs": []}
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
    out_jobs.sort(key=lambda j: (j["employer_type"] != "MDHHS", j["agency"], j["title"]))
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "eligible": eligible,
        "sources": sorted(sources, key=lambda s: (s["name"] != "MDHHS", s["name"].lower())),
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

    n_m = sum(1 for j in out_jobs if j["employer_type"] == "MDHHS")
    errs = [s["name"] for s in sources if s["status"] == "error"]
    log(f"Done: {len(out_jobs)} eligible postings ({n_m} MDHHS, {len(out_jobs) - n_m} private). Wrote {DOCS_DIR / 'index.html'}")
    if errs:
        log(f"Sources with errors: {', '.join(errs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
