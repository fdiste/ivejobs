import re
from datetime import date, datetime, timedelta

import requests

# A plain, honest UA; some boards (iCIMS) bot-check requests that claim to be full Chrome.
UA = {"User-Agent": "Mozilla/5.0 (compatible; MI-TitleIVE-JobBoard/1.0)"}
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
session = requests.Session()
session.headers.update(UA)


def get(url, **kw):
    r = session.get(url, timeout=kw.pop("timeout", 45), **kw)
    r.raise_for_status()
    if "charset" not in r.headers.get("Content-Type", "").lower():
        r.encoding = r.apparent_encoding  # avoid mojibake when the server omits the charset
    return r


def post_json(url, body, **kw):
    r = session.post(url, json=body, timeout=45, headers={"Accept": "application/json"}, **kw)
    r.raise_for_status()
    return r.json()


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def iso_date(s):
    """Parse common date formats to YYYY-MM-DD; returns None if unparseable."""
    if not s:
        return None
    s = clean(str(s))
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%d %b %Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        y = int(m.group(3))
        y += 2000 if y < 100 else 0
        try:
            return date(y, int(m.group(1)), int(m.group(2))).isoformat()
        except ValueError:
            return None
    return None


def relative_posted(s):
    """Workday-style 'Posted Today' / 'Posted 3 Days Ago' -> date. '30+ Days Ago' -> None."""
    s = (s or "").lower()
    today = date.today()
    if "today" in s:
        return today.isoformat()
    if "yesterday" in s:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\s+days? ago", s)
    if m and "+" not in s:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    return None


CONTINUOUS_RE = re.compile(
    r"open until filled|until (the )?position is filled|continuous(ly)? (posting|recruitment|open)"
    r"|ongoing recruitment|accepted on an ongoing basis", re.I)


def continuous_from_text(text):
    """True if the text says the posting stays open (until filled / continuous); otherwise None (unknown)."""
    return True if CONTINUOUS_RE.search(text or "") else None


def city_state(loc):
    """'US-MI-Kalamazoo', 'Lansing, MI', 'Grand Rapids, Michigan 49503' -> (city, state)."""
    from ..geo import split_location

    loc = clean(loc)
    m = re.fullmatch(r"US-([A-Z]{2})-(.+)", loc)
    if m:
        return m.group(2), m.group(1)
    return split_location(loc)
