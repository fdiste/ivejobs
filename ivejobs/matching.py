"""Match postings to the Title IV-E eligible positions using config/match_rules.json."""
import json
import re

from .paths import CONFIG_DIR

GENERIC_WORDS = {"worker", "specialist", "services", "service", "and", "of", "the", "level", "advanced", "positions"}


def position_key(p):
    return (p["title"] + (" " + p["detail"] if p.get("detail") else "")).lower().replace("’", "'")


def position_label(p):
    return p["title"] + (f" ({p['detail']})" if p.get("detail") else "")


def _compile(pats):
    return [re.compile(p, re.I) for p in pats or []]


def _auto_rule(p):
    """Fallback for positions newly added to the site with no hand-written rule."""
    title = re.sub(r"\d+(-\d+)?", " ", p["title"])
    words = [w for w in re.findall(r"[A-Za-z']+", title) if w.lower() not in GENERIC_WORDS and len(w) > 2]
    return {"title_any": [r"\b" + r"\b.*\b".join(re.escape(w) for w in words) + r"\b"]} if words else None


class Matcher:
    def __init__(self, eligible, log=print):
        cfg = json.loads((CONFIG_DIR / "match_rules.json").read_text(encoding="utf-8"))
        self.mdhhs_departments = cfg["mdhhs_departments"]
        self.global_exclude = _compile(cfg["global_exclude"])
        self.rules = {"mdhhs": [], "private": [], "tribal": []}
        groups = eligible["groups"]
        for group_key, target in (("mdhhs", "mdhhs"), ("mdhhs_advanced", "mdhhs"), ("private", "private"), ("tribal", "tribal")):
            for p in groups.get(group_key, []):
                # Tribal positions share titles with other groups (e.g. "foster home licensing" is also an MDHHS
                # position), so a "tribal: <position>" rule takes precedence for tribal agencies.
                rule = cfg["rules"].get(f"tribal: {position_key(p)}") if target == "tribal" else None
                rule = rule or cfg["rules"].get(position_key(p))
                if rule is None:
                    rule = _auto_rule(p)
                    log(f"WARNING: no match rule for eligible position {position_label(p)!r}; "
                        f"using auto rule {rule}. Add one to config/match_rules.json.")
                    if rule is None:
                        continue
                # A rule may list alternative ways to match under "or"; each inherits the rule's excludes.
                for alt in [rule] + rule.get("or", []):
                    self.rules[target].append({
                        "label": position_label(p),
                        "classspec": re.compile(alt["classspec"], re.I) if alt.get("classspec") else None,
                        "title_any": _compile(alt.get("title_any")),
                        "text_any": _compile(alt.get("text_any")),
                        "exclude": _compile(rule.get("exclude", []) + alt.get("exclude", []) if alt is not rule else rule.get("exclude")),
                    })

    def match(self, job):
        """Return the list of eligible position labels this posting matches."""
        title = job["title"]
        if any(p.search(title) for p in self.global_exclude):
            return []
        text = title + " " + (job.get("description") or "")
        rules = self.rules[{"MDHHS": "mdhhs", "Tribal": "tribal"}.get(job["employer_type"], "private")]
        hits = []
        for r in rules:
            if r["classspec"] and not r["classspec"].search(job.get("classspec") or ""):
                continue
            if r["title_any"] and not any(p.search(title) for p in r["title_any"]):
                continue
            if r["text_any"] and not any(p.search(text) for p in r["text_any"]):
                continue
            if not r["title_any"] and not r["text_any"] and not r["classspec"]:
                continue
            if any(p.search(title) for p in r["exclude"]):
                continue
            if r["label"] not in hits:
                hits.append(r["label"])
        return hits
