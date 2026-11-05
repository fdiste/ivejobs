import json
import re

from .common import clean, get


def fetch(agency, log=print):
    html = get(f"https://recruiting.paylocity.com/recruiting/jobs/All/{agency['ats_ids']['guid']}").text
    m = re.search(r"window\.pageData\s*=\s*(\{.*?\});\s*\n", html, re.S)
    if not m:
        raise ValueError("Paylocity pageData not found")
    jobs = []
    for j in json.loads(m.group(1))["Jobs"]:
        if j.get("IsInternal"):
            continue
        loc = j.get("JobLocation") or {}
        jobs.append({
            "id": j["JobId"],
            "title": clean(j["JobTitle"]),
            "url": f"https://recruiting.paylocity.com/Recruiting/Jobs/Details/{j['JobId']}",
            "city": loc.get("City"),
            "state": loc.get("State"),
            "location_raw": clean(j.get("LocationName")),
            "posted": (j.get("PublishedDate") or "")[:10] or None,
            "closes": None,
            "continuous": None,
            "description": clean(j.get("Description")),
        })
    return jobs
