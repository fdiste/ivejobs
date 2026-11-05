import re

from .common import clean, get, iso_date, post_json, relative_posted


def fetch(agency, log=print):
    ids = agency["ats_ids"]
    host = f"https://{ids['tenant']}.{ids['wd']}.myworkdayjobs.com"
    api = f"{host}/wday/cxs/{ids['tenant']}/{ids['site']}"
    postings, offset = [], 0
    while True:
        d = post_json(f"{api}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""})
        postings += d.get("jobPostings", [])
        offset += 20
        if offset >= d.get("total", 0) or not d.get("jobPostings"):
            break
    jobs = []
    for p in postings:
        path = p["externalPath"]
        info = {}
        try:  # the detail record has exact start/end dates and the full location
            info = get(f"{api}{path}", headers={"Accept": "application/json"}).json().get("jobPostingInfo", {})
        except Exception as e:  # noqa: BLE001
            log(f"    workday detail failed for {path}: {e}")
        loc = info.get("location") or p.get("locationsText") or ""
        city, _, state = loc.partition(",")
        jobs.append({
            "id": (p.get("bulletFields") or [path])[0],
            "title": clean(p["title"]),
            "url": f"{host}/{ids['site']}{path}",
            "city": None if "location" in city.lower() else clean(city) or None,
            "state": clean(state) or None,
            "location_raw": clean(loc + " " + " ".join(info.get("additionalLocations") or [])),
            "posted": iso_date(info.get("startDate")) or relative_posted(p.get("postedOn")),
            "closes": iso_date(info.get("endDate")),
            "continuous": None,
            "description": clean(re.sub(r"<[^>]+>", " ", info.get("jobDescription") or ""))[:3000],
        })
    return jobs
