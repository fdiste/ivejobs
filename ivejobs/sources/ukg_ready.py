"""UKG Ready (Kronos Workforce Ready / SaaShr) career portals: secure*.entertimeonline.com, secure*.saashr.com."""
from .common import clean, get


def fetch(agency, log=print):
    ids = agency["ats_ids"]
    host = ids.get("host", "secure.entertimeonline.com")
    company = ids["company"]
    ein = f"&ein_id={ids['ein_id']}" if ids.get("ein_id") else ""
    base = f"https://{host}/ta/rest/ui/recruitment/companies/%7C{company}/job-requisitions"
    reqs, offset = [], 0
    while offset < 2000:
        d = get(f"{base}?offset={offset}&size=100&sort=desc{ein}&lang=en-US", headers={"Accept": "application/json"}).json()
        reqs += d.get("job_requisitions", [])
        offset += 100
        if offset >= (d.get("_paging") or {}).get("total", 0):
            break
    jobs = []
    for r in reqs:
        loc = r.get("location") or {}
        jobs.append({
            "id": r["id"],
            "title": clean(r.get("job_title")),
            "url": f"https://{host}/ta/{company}.careers?ShowJob={r['id']}",
            "city": loc.get("city"), "state": loc.get("state"),
            "location_raw": clean(" ".join(filter(None, [loc.get("city"), loc.get("state")]))),
            "posted": None, "closes": None, "continuous": None,
            "description": " ".join(c.get("name", "") if isinstance(c, dict) else str(c) for c in r.get("job_categories") or []),
        })
    return jobs
