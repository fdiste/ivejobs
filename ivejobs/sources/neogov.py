"""MDHHS postings from the State of Michigan NEOGOV (governmentjobs.com) RSS feed."""
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

FEED_URL = "https://www.governmentjobs.com/SearchEngine/JobsFeed?agency=michigan"
NS = {"j": "http://www.neogov.com/namespaces/JobListing"}


def _date(s):
    # e.g. "Thu, 12 Nov 2026 23:59:00:0"
    if not s or s.strip().lower() == "continuous":
        return None
    m = re.match(r"\w{3}, (\d{2} \w{3} \d{4})", s.strip())
    return datetime.strptime(m.group(1), "%d %b %Y").date().isoformat() if m else None


def _strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def fetch(department_pattern, log=print):
    r = requests.get(FEED_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    dept_re = re.compile(department_pattern, re.I)
    jobs = []
    for it in root.findall("channel/item"):
        g = lambda tag: (it.findtext(f"j:{tag}", namespaces=NS) or "").strip()  # noqa: E731
        dept = g("department")
        if not dept_re.search(dept):
            continue
        closes_raw = g("advertiseToDateTime")
        continuous = g("continuous").lower() == "yes" or closes_raw.lower() == "continuous"
        jobs.append({
            "source": "neogov",
            "id": "mdhhs-" + g("jobId"),
            "agency": "MDHHS",
            "employer_type": "MDHHS",
            "title": re.sub(r"\s+", " ", it.findtext("title") or "").strip(),
            "classspec": g("classspec"),
            "description": " ".join(_strip_html(x) for x in (it.findtext("description"), g("examplesofduties"))),
            "location_raw": g("location"),
            "city": g("location") if g("location").lower() not in ("various", "statewide", "") else None,
            "posted": _date(g("advertiseFromDate")),
            "closes": None if continuous else _date(closes_raw),
            "continuous": continuous,
            "url": (it.findtext("link") or "").strip(),
            "department": dept,
        })
    log(f"  NEOGOV feed: {len(jobs)} postings in MDHHS county/central offices")
    return jobs
