"""Job board fetchers. Each private-agency fetcher takes the agency config dict and returns a list of
job dicts with keys: id, title, url, city (or cities), state, location_raw, posted, closes, continuous, description."""
from . import applicantpro, appone, clearcompany, html, icims, paycom, paycor, paylocity, ukg_ready, ultipro, workday

ATS_FETCHERS = {
    "applicantpro": applicantpro.fetch,
    "appone": appone.fetch,
    "clearcompany": clearcompany.fetch,
    "html": html.fetch,
    "icims": icims.fetch,
    "paycom": paycom.fetch,
    "paycor": paycor.fetch,
    "paylocity": paylocity.fetch,
    "ukg_ready": ukg_ready.fetch,
    "ultipro": ultipro.fetch,
    "workday": workday.fetch,
}
