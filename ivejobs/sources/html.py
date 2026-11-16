"""Generic scraper for agencies that list jobs on an ordinary web page.

Config keys (in config/agencies.json, under "html"):
  url:        page to read
  scope:      optional CSS selector for the region holding the job list
  item:       CSS selector matching one element per job (its text is the title)
  title:      optional CSS selector inside the item for the title text
  link:       "self" (item is/contains the <a>), "page" (use the page URL), "anchor" (page URL + #item id)
  stop_text:  optional; ignore items that come after an element containing this text
  skip:       optional regex; items whose title matches are ignored (e.g. "application")
  location_label: optional; read "Location: ..." text from the item's following content
  require_body: optional regex; keep an item only if the text after it matches (e.g. "we ARE currently seeking")
  browser_ua: optional true; send a full browser User-Agent (some sites block the default one)
  posted / closes: optional CSS selectors inside the item for the posted / closing date (e.g. table cells).
              A closing date reading "until filled" marks the posting continuous.
"""
import re

from bs4 import BeautifulSoup

from urllib.parse import urljoin

from .common import BROWSER_UA, CONTINUOUS_RE, city_state, clean, continuous_from_text, get, iso_date


def _following_text(el, item_ids, limit=1500):
    """Text that follows el in document order, up to the next job item."""
    parts, n = [], 0
    for nxt in el.next_elements:
        if id(nxt) in item_ids:
            break
        if isinstance(nxt, str) and not _inside(nxt, el):
            parts.append(nxt)
            n += len(nxt)
            if n > limit:
                break
    return clean(" ".join(parts))


def _inside(node, el):
    return any(parent is el for parent in node.parents)


def fetch(agency, log=print):
    cfg = agency["html"]
    url = cfg["url"]
    headers = {"User-Agent": BROWSER_UA} if cfg.get("browser_ua") else None
    soup = BeautifulSoup(get(url, headers=headers).content, "html.parser")
    root = soup.select_one(cfg["scope"]) if cfg.get("scope") else soup
    if root is None:
        raise ValueError(f"scope {cfg['scope']!r} not found; page layout may have changed")
    stop_el = None
    if cfg.get("stop_text"):
        stop_el = root.find(string=re.compile(re.escape(cfg["stop_text"]), re.I))
    skip = re.compile(cfg["skip"], re.I) if cfg.get("skip") else None
    require = re.compile(cfg["require_body"]) if cfg.get("require_body") else None
    jobs = []
    items = root.select(cfg["item"])
    item_ids = {id(i) for i in items}
    for item in items:
        if stop_el is not None and _is_after(item, stop_el):
            break
        t_el = item.select_one(cfg["title"]) if cfg.get("title") else item
        title = clean(t_el.get_text(" ")) if t_el else ""
        if not title or (skip and skip.search(title)):
            continue
        a = item if item.name == "a" else item.find("a", href=True)
        mode = cfg.get("link", "self")
        if mode == "self" and a is not None and a.get("href"):
            link = urljoin(url, a["href"])
        elif mode == "anchor" and item.get("id"):
            link = f"{url}#{item['id']}"
        else:
            link = url
        body = _following_text(item, item_ids) if cfg.get("location_label") or cfg.get("read_body") or require else ""
        if require and not require.search(body):
            continue
        loc = ""
        if cfg.get("location_label"):
            m = re.search(re.escape(cfg["location_label"]) + r"\s*:?\s*([A-Z][A-Za-z.'-]*(?: [A-Z][A-Za-z.'-]*)*?)"
                          r"(?=,|\s+(?:MI|Michigan)\b|\s+[A-Z][a-z]+(?: [A-Z][a-z]+)?\s*:|\s*$)", body)
            loc = clean(m.group(1)) if m else ""
        city, state = city_state(loc) if loc else (None, None)
        posted, closes, continuous = _cell(item, cfg.get("posted")), _cell(item, cfg.get("closes")), continuous_from_text(body)
        if closes and CONTINUOUS_RE.search(closes):
            continuous = True
        jobs.append({
            "id": f"{link}|{title}",
            "title": title, "url": link,
            "city": city, "state": state, "location_raw": loc,
            "county_hint": title,
            "posted": iso_date(posted), "closes": iso_date(closes),
            "continuous": continuous,
            "description": body[:1000],
        })
    return jobs


def _cell(item, selector):
    el = item.select_one(selector) if selector else None
    return clean(el.get_text(" ")) if el else None


def _is_after(el, marker):
    """True if el appears after marker in document order."""
    for prev in el.find_all_previous(string=True):
        if prev is marker:
            return True
    return False
