"""ApplicantPro boards (<sub>.applicantpro.com, or white-labelled e.g. recruitpro.com)."""
import html
from datetime import datetime

from .common import clean, get


def _date(s):
    try:
        return datetime.strptime(s, "%b %d, %Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def fetch(agency, log=print):
    ids = agency["ats_ids"]
    host = f"{ids['subdomain']}.{ids.get('domain', 'applicantpro.com')}"
    d = get(f"https://{host}/core/jobs/{ids['domain_id']}?getParams=%7B%22isInternal%22:0%7D").json()
    jobs = []
    for j in d["data"]["jobs"]:
        until_filled = str(j.get("untilFilled")) == "1"
        jobs.append({
            "id": j["id"],
            "title": clean(html.unescape(j["title"])),  # some boards return "&amp;"
            "url": j.get("jobUrl") or f"https://{host}/jobs/{j['id']}",
            "city": j.get("city"), "state": j.get("abbreviation"),
            "location_raw": clean(j.get("jobLocation")),
            "posted": _date(j.get("startDateRef")),
            # When "until filled", endDateRef is a placeholder years out, not a real closing date.
            "closes": None if until_filled else _date(j.get("endDateRef")),
            "continuous": True if until_filled else False,
            "description": clean(j.get("orgTitle")),
        })
    return jobs
