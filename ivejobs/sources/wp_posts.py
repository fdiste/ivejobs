"""WordPress sites that publish each job opening as a blog post in a "careers" category (read via the WP REST API).

ats_ids: site (e.g. "https://www.kbic-nsn.gov"), category (numeric category id).
"""
import html as htmllib

from bs4 import BeautifulSoup

from .common import clean, continuous_from_text, get


def fetch(agency, log=print):
    ids = agency["ats_ids"]
    posts, page = [], 1
    while page <= 10:
        r = get(f"{ids['site'].rstrip('/')}/wp-json/wp/v2/posts",
                params={"categories": ids["category"], "per_page": 100, "page": page, "_fields": "id,date,link,title,content"})
        batch = r.json()
        posts += batch
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    jobs = []
    for p in posts:
        desc = clean(BeautifulSoup((p.get("content") or {}).get("rendered") or "", "html.parser").get_text(" "))
        jobs.append({
            "id": p["id"],
            "title": clean(htmllib.unescape(p["title"]["rendered"])),
            "url": p["link"],
            "city": None, "state": None, "location_raw": "",
            "posted": (p.get("date") or "")[:10] or None,
            "closes": None,
            "continuous": continuous_from_text(desc),
            "description": desc[:3000],
        })
    return jobs
