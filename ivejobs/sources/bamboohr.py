"""BambooHR career sites (<subdomain>.bamboohr.com/careers). The list has no descriptions, so each job's detail is read too."""

from bs4 import BeautifulSoup

from .common import clean, continuous_from_text, get

STATES = {"michigan": "MI", "indiana": "IN", "ohio": "OH", "wisconsin": "WI", "illinois": "IL"}


def fetch(agency, log=print):
    base = f"https://{agency['ats_ids']['subdomain']}.bamboohr.com/careers"
    listing = get(f"{base}/list", headers={"Accept": "application/json"}).json()["result"]
    jobs = []
    for o in listing:
        loc = o.get("location") or {}
        detail = {}
        try:
            detail = get(f"{base}/{o['id']}/detail", headers={"Accept": "application/json"}).json()["result"]["jobOpening"]
        except Exception as e:  # noqa: BLE001 - the listing alone is still useful
            log(f"    could not read details for {o.get('jobOpeningName')!r}: {e}")
        desc = clean(BeautifulSoup(detail.get("description") or "", "html.parser").get_text(" "))
        state = (loc.get("state") or "").strip()
        jobs.append({
            "id": o["id"],
            "title": clean(o["jobOpeningName"]),
            "url": f"{base}/{o['id']}",
            "city": loc.get("city"), "state": STATES.get(state.lower(), state),
            "location_raw": clean(" ".join(filter(None, [loc.get("city"), state]))),
            "posted": detail.get("datePosted"),
            "closes": None,
            "continuous": continuous_from_text(desc),
            "description": clean(" ".join(filter(None, [o.get("departmentLabel"), desc])))[:3000],
        })
    return jobs
