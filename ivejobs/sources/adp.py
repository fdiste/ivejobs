"""ADP Workforce Now career centers (workforcenow.adp.com/mascsr/.../recruitment.html?cid=...)."""

from bs4 import BeautifulSoup

from .common import clean, continuous_from_text, get

API = "https://workforcenow.adp.com/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions"


def _params(cid, cc_id):
    return {"cid": cid, "ccId": cc_id, "lang": "en_US", "locale": "en_US"}


def fetch(agency, log=print):
    ids = agency["ats_ids"]
    cid, cc_id = ids["cid"], ids.get("ccId", "19000101_000001")
    reqs, skip = [], 0
    while skip < 1000:
        d = get(API, params={**_params(cid, cc_id), "$top": 100, "$skip": skip}, headers={"Accept": "application/json"}).json()
        page = d.get("jobRequisitions") or []
        reqs += page
        skip += 100
        if not page or skip >= ((d.get("meta") or {}).get("totalNumber") or 0):
            break
    jobs = []
    for r in reqs:
        loc = ((r.get("requisitionLocations") or [{}])[0].get("address")) or {}
        ext_id = next((f.get("stringValue") for f in (r.get("customFieldGroup") or {}).get("stringFields", [])
                       if (f.get("nameCode") or {}).get("codeValue") == "ExternalJobID" and f.get("stringValue")), None)
        desc = ""
        try:
            detail = get(f"{API}/{r['itemID']}", params=_params(cid, cc_id), headers={"Accept": "application/json"}).json()
            desc = clean(BeautifulSoup(detail.get("requisitionDescription") or "", "html.parser").get_text(" "))
        except Exception as e:  # noqa: BLE001 - the listing alone is still useful
            log(f"    could not read details for {r.get('requisitionTitle')!r}: {e}")
        jobs.append({
            "id": r["itemID"],
            "title": clean(r.get("requisitionTitle")),
            "url": (f"https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html"
                    f"?cid={cid}&ccId={cc_id}&jobId={ext_id or r['itemID']}&lang=en_US"),
            "city": loc.get("cityName"), "state": (loc.get("countrySubdivisionLevel1") or {}).get("codeValue"),
            "location_raw": clean(((r.get("requisitionLocations") or [{}])[0].get("nameCode") or {}).get("shortName")),
            "posted": (r.get("postDate") or "")[:10] or None,
            "closes": None,
            "continuous": continuous_from_text(desc),
            "description": desc[:3000],
        })
    return jobs
