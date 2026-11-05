"""UKG Pro / UltiPro Recruiting job boards (recruiting*.ultipro.com)."""
from .common import clean, post_json


def _body(skip, top):
    return {
        "opportunitySearch": {
            "Top": top, "Skip": skip, "QueryString": "",
            "OrderBy": [{"Value": "postedDateDesc", "PropertyName": "PostedDate", "Ascending": False}],
            "Filters": [{"t": "TermsSearchFilterDto", "fieldName": n, "extra": None, "values": []} for n in (4, 5, 6)],
        },
        "matchCriteria": {"PreferredJobs": [], "Educations": [], "LicenseAndCertifications": [], "Skills": [],
                          "hasNoLicenses": False, "SkippedSkills": []},
    }


def fetch(agency, log=print):
    ids = agency["ats_ids"]
    board = f"https://{ids.get('host', 'recruiting.ultipro.com')}/{ids['tenant']}/JobBoard/{ids['board_id']}"
    opps, skip, top = [], 0, 100
    while skip < 2000:
        page = post_json(f"{board}/JobBoardView/LoadSearchResults", _body(skip, top)).get("opportunities", [])
        opps += page
        if len(page) < top:
            break
        skip += top
    jobs = []
    for o in opps:
        locs = [loc.get("Address") or {} for loc in o.get("Locations") or []]
        mi = [a for a in locs if ((a.get("State") or {}).get("Code") or "") == "MI"]
        use = mi or locs
        jobs.append({
            "id": o["Id"],
            "title": clean(o["Title"]),
            "url": f"{board}/OpportunityDetail?opportunityId={o['Id']}",
            "cities": [a.get("City") for a in use if a.get("City")],
            "state": "MI" if mi else ((use[0].get("State") or {}).get("Code") if use else None),
            "location_raw": "; ".join(clean(loc.get("LocalizedDescription")) for loc in o.get("Locations") or []),
            "posted": (o.get("PostedDate") or "")[:10] or None,
            "closes": None, "continuous": None,
            "description": clean(o.get("BriefDescription")),
        })
    return jobs
