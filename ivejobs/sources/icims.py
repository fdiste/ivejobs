import re

from bs4 import BeautifulSoup

from .common import city_state, clean, get


def fetch(agency, log=print):
    sub = agency["ats_ids"]["subdomain"]
    jobs, page = [], 0
    while page < 20:
        soup = BeautifulSoup(get(f"https://{sub}.icims.com/jobs/search?ss=1&in_iframe=1&pr={page}").content, "html.parser")
        cards = soup.select("li.iCIMS_JobCardItem")
        for c in cards:
            a = c.select_one("div.title a.iCIMS_Anchor")
            loc_el = c.select_one("div.header.left span:not(.sr-only)")
            loc = clean(loc_el.get_text()) if loc_el else ""
            fields = {clean(dt.get_text()): clean(dt.find_next_sibling("dd").get_text()) for dt in c.select("dt")}
            city, state = city_state(loc.split("|")[0]) if loc else (None, None)
            desc = c.select_one("div.description")
            url = a["href"].replace("?in_iframe=1", "")
            jobs.append({
                "id": fields.get("ID") or url,
                "title": clean((a.find("h3") or a).get_text()),
                "url": url,
                "city": city, "state": state, "location_raw": loc,
                "posted": None, "closes": None, "continuous": None,
                "description": clean(desc.get_text()) if desc else "",
            })
        if not cards or not soup.find("a", title=re.compile(r"next page", re.I)):
            break
        page += 1
    return jobs
