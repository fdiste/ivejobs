"""Paycor Recruiting (formerly Newton) boards. Handles both the table layout and the grouped-by-department layout.

Set "read_details": true in ats_ids to also read each posting's description and deadline (one extra request per job);
useful when titles alone are ambiguous (e.g. "Licensing Specialist" at a tribe may be gaming licensing)."""
import re

from bs4 import BeautifulSoup

from .common import city_state, clean, continuous_from_text, get, iso_date

DEADLINE_RE = re.compile(r"(?:application deadline|posting closes|closing date|deadline)\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", re.I)


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
    if agency["ats_ids"].get("read_details"):
        for j in jobs:
            try:
                page = BeautifulSoup(get(j["url"]).content, "html.parser")
                el = page.select_one("#gnewtonJobDescriptionText")
                text = clean(el.get_text(" ")) if el else ""
            except Exception as e:  # noqa: BLE001 - the listing alone is still useful
                log(f"    could not read details for {j['title']!r}: {e}")
                continue
            m = DEADLINE_RE.search(text)
            j.update(description=text[:3000], closes=iso_date(m.group(1).replace("-", "/")) if m else None,
                     continuous=continuous_from_text(text))
    return jobs
