"""Pull the list of Title IV-E eligible positions from michildwelfare.org/employment.

The site sits behind a Cloudflare browser check, so it is loaded in a real (visible)
Chrome window through Playwright. If that fails, the last good copy saved in
data/eligible_positions.json is used instead.
"""
import json
import re
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .paths import DATA_DIR, BROWSER_PROFILE

EMPLOYMENT_URL = "https://michildwelfare.org/employment/"
CACHE_FILE = DATA_DIR / "eligible_positions.json"

GROUP_HEADINGS = {
    "michigan department of health and human services": "mdhhs",
    "advanced level positions": "mdhhs_advanced",
    "private agencies": "private",
    "tribal agencies": "tribal",
}


def fetch_page_html(url=EMPLOYMENT_URL, timeout_s=45):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(BROWSER_PROFILE),
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--window-position=-2000,0"],
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            deadline = time.time() + timeout_s
            while "Just a moment" in page.title() and time.time() < deadline:
                time.sleep(1)
            page.wait_for_timeout(2000)
            return page.content()
        finally:
            ctx.close()


def parse_positions(html):
    """Return {"mdhhs": [...], "mdhhs_advanced": [...], "private": [...], "tribal": [...]}.

    Each entry is {"title": ..., "detail": ...}. The page is built with Divi, where each
    position is an et_pb_blurb module and each group starts with a text-module heading.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find(id="main-content") or soup.body
    groups = {k: [] for k in GROUP_HEADINGS.values()}
    current = None
    for mod in main.select(".et_pb_module"):
        if mod.find(class_="et_pb_module"):
            continue  # only leaf modules
        text = mod.get_text(" ", strip=True)
        key = GROUP_HEADINGS.get(text.lower().replace("’", "'"))
        if key:
            current = key
            continue
        if text.lower().startswith("where our fellows"):
            break
        if current is None or "et_pb_blurb" not in (mod.get("class") or []):
            continue
        title_el = mod.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        title = title_el.get_text(" ", strip=True) if title_el else text
        detail = text[len(title):].strip(" /") if text.startswith(title) else ""
        if title.lower() in ("advanced level",):
            continue
        entry = {"title": _clean(title), "detail": _clean(detail)}
        if entry not in groups[current]:
            groups[current].append(entry)
    return groups


def _clean(s):
    s = s.replace("’", "'").replace("�", "'")
    return re.sub(r"\s+", " ", s).strip()


def load_eligible_positions(refresh=True, log=print):
    """Fetch and parse the live list; fall back to the cached copy on any failure."""
    cached = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else None
    if refresh:
        try:
            groups = parse_positions(fetch_page_html())
            if sum(len(v) for v in groups.values()) < 5 or not groups["mdhhs"] or not groups["private"]:
                raise ValueError("eligible positions list looks incomplete; page layout may have changed")
            result = {
                "source": EMPLOYMENT_URL,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "groups": groups,
            }
            if cached and cached["groups"] != groups:
                log("NOTE: the eligible positions list on michildwelfare.org changed since last run.")
            CACHE_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result
        except Exception as e:  # noqa: BLE001 - any failure falls back to cache
            log(f"WARNING: could not refresh eligible positions ({e}); using cached copy.")
    if cached is None:
        raise RuntimeError("No eligible positions available (fetch failed and no cache).")
    return cached
