"""Paycor Recruiting (formerly Newton) boards. Handles both the table layout and the grouped-by-department layout."""
import re

from bs4 import BeautifulSoup

from .common import city_state, clean, get


def fetch(agency, log=print):
    cid = agency["ats_ids"]["clientId"]
    soup = BeautifulSoup(get(f"https://recruitingbypaycor.com/career/CareerHome.action?clientId={cid}").content, "html.parser")
    rows = [(td.find("a"), td.find_parent("tr").select_one("td.gnewtonJobLocation")) for td in soup.select("td.gnewtonJobLink")]
    rows += [(div.find("a"), div.find_parent(class_="gnewtonCareerGroupRowClass").select_one(".gnewtonCareerGroupJobDescriptionClass"))
             for div in soup.select(".gnewtonCareerGroupJobTitleClass")]
    jobs = []
    for a, loc_el in rows:
        if a is None:
            continue
        loc = clean(loc_el.get_text()) if loc_el else ""
        city, state = city_state(loc)
        m = re.search(r"[?&]id=([^&]+)", a["href"])
        jobs.append({
            "id": m.group(1) if m else a["href"],
            "title": clean(a.get_text()), "url": a["href"],
            "city": city, "state": state, "location_raw": loc,
            "posted": None, "closes": None, "continuous": None,
        })
    return jobs
