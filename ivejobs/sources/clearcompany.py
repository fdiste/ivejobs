"""ClearCompany career sites (careers-api.clearcompany.com)."""
import re

from .common import clean, get


def fetch(agency, log=print):
    ids = agency["ats_ids"]
    results, page = [], 0
    while page < 30:
        d = get(f"https://careers-api.clearcompany.com/v1/{ids['siteId']}?pageIndex={page}").json()
        results += d.get("results", [])
        if not d.get("results") or len(results) >= (d.get("totalCount") or 0):
            break
        page += 1
    seen, jobs = set(), []
    for r in results:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        locs = r.get("locations") or []
        mi = [loc for loc in locs if loc.get("subdivision") == "MI"]
        jobs.append({
            "id": r["id"],
            # Titles often end with the location ("... - Grand Rapids, MI"); keep the title as posted.
            "title": clean(r["positionTitle"]),
            "url": f"https://{ids['subdomain']}/careers/jobs/{r['id']}",
            "cities": [loc["city"] for loc in (mi or locs) if loc.get("city")],
            "state": "MI" if mi else (locs[0].get("subdivision") if locs else None),
            "location_raw": clean(r.get("location")),
            "posted": (r.get("postedDate") or r.get("openDate") or "")[:10] or None,
            "closes": None, "continuous": None,
            "description": clean(re.sub(r"<[^>]+>", " ", r.get("departmentName") or "")),
        })
    return jobs
