"""Paychex Recruiting / AppOne boards: either the JSON portal API or the older RSS portal feed."""
import re
from email.utils import parsedate_to_datetime
from html import unescape

from .common import city_state, clean, get


def fetch(agency, log=print):
    ids = agency["ats_ids"]
    if ids.get("rss_portal"):
        return _fetch_rss(ids["rss_portal"])
    d = get(f"https://jobs.appone.com/api/portal/v1/companyjobposts/{ids['company_slug']}").json()
    jobs = []
    for p in d.get("jobPosts", []):
        city, state = city_state(p.get("location") or "")
        jobs.append({
            "id": p["jobPostId"],
            "title": clean(p["jobTitle"]),
            "url": p["jobPostUrl"],
            "city": city, "state": state, "location_raw": clean(p.get("location")),
            "posted": (p.get("datePosted") or "")[:10] or None,
            "closes": None, "continuous": None,
        })
    return jobs


def _fetch_rss(portal):
    # Item descriptions embed large base64 images, so only title/link/pubDate are read with a regex.
    raw = get(f"https://client.hrservicesinc.com/downloads/rss/portals/{portal}.xml", timeout=90).content.decode("latin-1")
    jobs = []
    for item in re.findall(r"<item>(.*?)</item>", raw, re.S):
        title = _tag(item, "title")
        link = unescape(_tag(item, "link"))
        # Titles look like "Foster Care Case Manager  (MI, Saginaw/Flint)"
        m = re.match(r"(.*?)\s*\(\s*([A-Z]{2})\s*,\s*([^)]*)\)\s*$", title)
        name, state, cities = (m.group(1), m.group(2), m.group(3)) if m else (title, None, "")
        rid = re.search(r"R_ID=(\d+)", link)
        try:
            posted = parsedate_to_datetime(_tag(item, "pubDate")).date().isoformat()
        except (TypeError, ValueError):
            posted = None
        jobs.append({
            "id": rid.group(1) if rid else link,
            "title": clean(name), "url": link,
            "cities": [clean(c) for c in re.split(r"[/,]", cities) if clean(c)],
            "state": state, "location_raw": clean(cities),
            "posted": posted, "closes": None, "continuous": None,
        })
    return jobs


def _tag(s, tag):
    m = re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", s, re.S)
    return clean(m.group(1)) if m else ""
