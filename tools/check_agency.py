"""Debug helper: fetch one or more agencies and show every posting with its match result.
Usage: py tools/check_agency.py ["Agency name" ...]   (no args = all non-manual agencies)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ivejobs.build import fetch_private, in_michigan  # noqa: E402
from ivejobs.eligible import load_eligible_positions  # noqa: E402
from ivejobs.matching import Matcher  # noqa: E402
from ivejobs.paths import CONFIG_DIR  # noqa: E402

names = sys.argv[1:]
m = Matcher(load_eligible_positions(refresh=False))
for a in json.loads((CONFIG_DIR / "agencies.json").read_text(encoding="utf-8"))["agencies"]:
    if a["ats"] == "manual" or (names and a["name"] not in names):
        continue
    try:
        jobs = fetch_private(a)
    except Exception as e:  # noqa: BLE001
        print(f"== {a['name']}: ERROR {type(e).__name__}: {e}")
        continue
    print(f"== {a['name']}: {len(jobs)} postings")
    for j in jobs:
        roles = m.match(j)
        flag = "MATCH" if roles else "     "
        if not in_michigan(j):
            flag = "NonMI"
        print(f"  {flag} {j['title'][:70]:70} | {j.get('city')},{j.get('state')} | {j.get('posted')} | {'; '.join(r[:25] for r in roles)}")
