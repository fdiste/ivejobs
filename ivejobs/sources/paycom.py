"""Paycom applicant tracking portals. The search API needs a session token from the public career page."""
import re

from .common import clean, session

SEARCH_FILTERS = {"distanceFrom": 0, "workEnvironments": [], "positionTypes": [], "educationLevels": [], "categories": [],
                  "travelTypes": [], "shiftTypes": [], "otherFilters": [], "keywordSearchText": "", "location": "", "sortOption": ""}


def fetch(agency, log=print):
    key = agency["ats_ids"]["clientkey"]
    # Some clients live on a regional host (e.g. phx.us-west.paycomonline.net) instead of www.
    host = agency["ats_ids"].get("host", "www.paycomonline.net")
    page_url = f"https://{host}/v4/ats/web.php/portal/{key}/career-page"
    r = session.get(page_url, timeout=45)
    r.raise_for_status()
    jwt = re.search(r'"sessionJWT":"([^"]+)"', r.text)
    api = re.search(r"portal-applicant-tracking\.[a-z0-9-]+\.paycomonline\.net", r.text)
    if not jwt or not api:
        raise ValueError("Paycom session token not found on career page")
    headers = {"authorization": jwt.group(1), "portal-host-referrer": page_url, "referer": f"https://{host}/",
               "accept": "application/json"}
    previews, skip = [], 0
    while skip < 1000:
        resp = session.post(f"https://{api.group(0)}/api/ats/job-posting-previews/search", headers=headers, timeout=45,
                            json={"skip": skip, "take": 100, "filtersForQuery": SEARCH_FILTERS})
        resp.raise_for_status()
        d = resp.json()
        previews += d.get("jobPostingPreviews", [])
        skip += 100
        if skip >= (d.get("jobPostingPreviewsCount") or 0):
            break
    jobs = []
    for p in previews:
        loc = clean(p.get("locations") if isinstance(p.get("locations"), str) else "; ".join(p.get("locations") or []))
        first = loc.split(";")[0]
        city, _, rest = first.partition(",")
        state = re.search(r"\b([A-Z]{2})\b", rest)
        jobs.append({
            "id": p["jobId"],
            "title": clean(p["jobTitle"]),
            "url": f"https://{host}/v4/ats/web.php/portal/{key}/jobs/{p['jobId']}",
            "city": clean(city) or None, "state": state.group(1) if state else None,
            "location_raw": loc,
            "posted": (p.get("postedOn") or "")[:10] or None,
            "closes": None, "continuous": None,
            "description": clean(p.get("description")),
        })
    return jobs
