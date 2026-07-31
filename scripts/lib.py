#!/usr/bin/env python3
"""Shared normalisation, dedupe and archive-writing helpers.

Used by both build_seed.py (one-off backfill) and generate.py (daily cron).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ITEMS = DATA / "items"

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "at", "by", "with",
    "from", "as", "is", "are", "its", "it", "into", "over", "after", "amid", "about",
    "new", "up", "out", "that", "this", "will", "has", "have", "be", "been", "was",
}


# ---------------------------------------------------------------- config

def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text())


# ---------------------------------------------------------------- text utils

def slug(text: str, maxlen: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:maxlen].strip("-")


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def canon_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    url = re.sub(r"^https?://", "", url, flags=re.I)
    url = re.sub(r"^www\.", "", url, flags=re.I)
    url = url.split("#")[0]
    url = re.sub(r"[?&](utm_[^&]+|source=gmail|ust=[^&]*|sa=E)(?=&|$)", "", url)
    url = url.rstrip("?&/")
    return url.lower()


def parse_date(value: str) -> str | None:
    if not value:
        return None
    value = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- normalise

def canon_firm(name: str, cfg: dict) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    aliases = cfg["firm_aliases"]
    if name in aliases:
        return aliases[name]
    lowered = {k.lower(): v for k, v in aliases.items()}
    if name.lower() in lowered:
        return lowered[name.lower()]
    known = {f.lower(): f for f in cfg["watchlist_firms"]}
    if name.lower() in known:
        return known[name.lower()]
    return name


def detect_situations(item: dict, cfg: dict) -> list[str]:
    """Tag an item against the tracked-situation registry using alias matching."""
    haystack = " ".join([
        item.get("headline", ""),
        item.get("players", ""),
        " ".join(item.get("companies", []) or []),
        " ".join(item.get("firms", []) or []),
    ]).lower()

    found = set(item.get("situations") or [])
    valid = {s["key"] for s in cfg["tracked_situations"]}
    found = {f for f in found if f in valid}

    for sit in cfg["tracked_situations"]:
        for alias in sit["aliases"]:
            if re.search(r"\b" + re.escape(alias.lower()) + r"\b", haystack):
                found.add(sit["key"])
                break
    return sorted(found)


def normalise(raw: dict, cfg: dict) -> dict | None:
    date = parse_date(raw.get("date"))
    headline = (raw.get("headline") or "").strip()
    if not date or not headline:
        return None

    sources = []
    seen_urls = set()
    for s in raw.get("sources") or []:
        if not isinstance(s, dict):
            continue
        url = (s.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        cu = canon_url(url)
        if cu in seen_urls:
            continue
        seen_urls.add(cu)
        sources.append({"name": (s.get("name") or "Source").strip(), "url": url})
    if not sources:
        return None  # unsourced items never enter the archive

    valid_sections = {s["key"] for s in cfg["sections"]}
    section = raw.get("section") if raw.get("section") in valid_sections else "sector_themes"

    valid_sectors = set(cfg["sectors"])
    sectors = [s for s in (raw.get("sectors") or []) if s in valid_sectors]

    firms = []
    for f in raw.get("firms") or []:
        c = canon_firm(f, cfg)
        if c and c not in firms:
            firms.append(c)

    companies = [c.strip() for c in (raw.get("companies") or []) if str(c).strip()]

    item = {
        "date": date,
        "headline": headline,
        "section": section,
        "sources": sources,
        "players": (raw.get("players") or "").strip(),
        "why_it_matters": (raw.get("why_it_matters") or "").strip(),
        "why_you_care": (raw.get("why_you_care") or "").strip(),
        "firms": firms,
        "companies": companies[:8],
        "sectors": sectors,
        "geo": [g.strip() for g in (raw.get("geo") or []) if str(g).strip()][:4],
        "priority": "high" if str(raw.get("priority", "")).lower() == "high" else "normal",
    }
    item["situations"] = detect_situations({**item, **raw}, cfg)
    if item["situations"]:
        item["section"] = "tracked_situations"

    # two tiers of firm interest, used for the site marker and the email ranking
    flags = []
    if any(f in cfg["priority_firms"] for f in item["firms"]):
        flags.append("priority_firm")
    if any(f in cfg.get("secondary_firms", []) for f in item["firms"]):
        flags.append("secondary_firm")
    item["flags"] = flags

    item["id"] = f"{date}-{slug(headline, 48)}-{hashlib.sha1(canon_url(sources[0]['url']).encode()).hexdigest()[:6]}"
    return item


# ---------------------------------------------------------------- dedupe

def _bulk(x: dict) -> int:
    return len(x.get("players", "")) + len(x.get("why_it_matters", ""))


def merge(a: dict, b: dict) -> dict:
    """Merge b into a.

    The prose fields are taken as a UNIT from whichever record is richer, never
    cherry-picked field by field. Picking the longest headline from one record
    and the longest commentary from another means a single false-positive match
    stitches two unrelated stories into one incoherent item.
    """
    rich = b if _bulk(b) > _bulk(a) else a
    out = dict(a)
    out["headline"] = rich["headline"]
    out["players"] = rich["players"]
    out["why_it_matters"] = rich["why_it_matters"]
    out["why_you_care"] = (rich.get("why_you_care") or a.get("why_you_care")
                           or b.get("why_you_care") or "")

    seen = {canon_url(s["url"]) for s in out["sources"]}
    for s in b.get("sources", []):
        if canon_url(s["url"]) not in seen:
            out["sources"].append(s)
            seen.add(canon_url(s["url"]))
    out["sources"] = out["sources"][:4]

    for key in ("firms", "companies", "sectors", "situations", "geo", "flags"):
        merged = list(out.get(key, []))
        for v in b.get(key, []):
            if v not in merged:
                merged.append(v)
        out[key] = merged

    if b.get("priority") == "high":
        out["priority"] = "high"
    if b.get("section") == "tracked_situations":
        out["section"] = "tracked_situations"
    out["date"] = min(out["date"], b["date"])
    return out


def dedupe(items: list[dict]) -> list[dict]:
    """Collapse the same transaction reported by several agents or outlets."""
    kept: list[dict] = []
    url_index: dict[str, int] = {}

    for item in sorted(items, key=lambda x: (x["date"], -len(x.get("why_it_matters", "")))):
        urls = {canon_url(s["url"]) for s in item["sources"]}
        hit = None

        for u in urls:
            if u in url_index:
                hit = url_index[u]
                break

        if hit is None:
            it_tok = tokens(item["headline"])
            for idx, existing in enumerate(kept):
                if abs((datetime.strptime(item["date"], "%Y-%m-%d")
                        - datetime.strptime(existing["date"], "%Y-%m-%d")).days) > 5:
                    continue
                # a similar headline alone is not enough: two records must also
                # name a company, situation or firm in common before they merge
                shared = (set(item["companies"]) & set(existing["companies"])) \
                    or (set(item["situations"]) & set(existing["situations"])) \
                    or (set(item["firms"]) & set(existing["firms"]))
                if shared and jaccard(it_tok, tokens(existing["headline"])) >= 0.6:
                    hit = idx
                    break

        if hit is None:
            kept.append(item)
            for u in urls:
                url_index[u] = len(kept) - 1
        else:
            kept[hit] = merge(kept[hit], item)
            for u in urls:
                url_index.setdefault(u, hit)

    return kept


def thread_stories(items: list[dict]) -> list[dict]:
    """Link recurring coverage of the same situation into a storyline."""
    items = sorted(items, key=lambda x: x["date"])
    story_of: dict[str, str] = {}
    members: dict[str, list[dict]] = defaultdict(list)

    for item in items:
        it_tok = tokens(item["headline"])
        anchor = set(item.get("companies", [])) | set(item.get("situations", []))
        match = None
        for sid, group in members.items():
            for other in group[-4:]:
                shared = anchor & (set(other.get("companies", [])) | set(other.get("situations", [])))
                if not shared:
                    continue
                if jaccard(it_tok, tokens(other["headline"])) >= 0.32:
                    match = sid
                    break
            if match:
                break
        sid = match or f"story-{slug(item['headline'], 40)}"
        story_of[item["id"]] = sid
        members[sid].append(item)

    for item in items:
        sid = story_of[item["id"]]
        item["story_id"] = sid
        item["story_size"] = len(members[sid])
    return items


# ---------------------------------------------------------------- write

def write_archive(items: list[dict], cfg: dict) -> dict:
    ITEMS.mkdir(parents=True, exist_ok=True)
    items = thread_stories(dedupe(items))

    by_month: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_month[item["date"][:7]].append(item)

    for month, group in by_month.items():
        group.sort(key=lambda x: (x["date"], 0 if x["priority"] == "high" else 1), reverse=True)
        (ITEMS / f"{month}.json").write_text(json.dumps(group, indent=1, ensure_ascii=False))

    # ---- entity rollups
    firm_stats: dict[str, dict] = {}
    sit_stats: dict[str, dict] = {}
    sector_stats: dict[str, dict] = {}

    def bump(store, key, item, extra=None):
        rec = store.setdefault(key, {"count": 0, "first_seen": item["date"], "last_seen": item["date"]})
        rec["count"] += 1
        rec["first_seen"] = min(rec["first_seen"], item["date"])
        rec["last_seen"] = max(rec["last_seen"], item["date"])
        if extra:
            rec.update(extra)

    for item in items:
        for f in item["firms"]:
            bump(firm_stats, f, item)
        for s in item["situations"]:
            bump(sit_stats, s, item)
        for s in item["sectors"]:
            bump(sector_stats, s, item)

    sit_meta = {s["key"]: s for s in cfg["tracked_situations"]}
    situations = [{
        "key": k,
        "label": sit_meta.get(k, {}).get("label", k),
        "note": sit_meta.get(k, {}).get("note", ""),
        **v,
    } for k, v in sit_stats.items()]
    for s in cfg["tracked_situations"]:
        if s["key"] not in sit_stats:
            situations.append({"key": s["key"], "label": s["label"], "note": s["note"],
                               "count": 0, "first_seen": None, "last_seen": None})
    situations.sort(key=lambda x: (-x["count"], x["label"]))

    firms = [{"name": k, "watchlist": k in cfg["watchlist_firms"],
              "priority": k in cfg["priority_firms"], **v} for k, v in firm_stats.items()]
    firms.sort(key=lambda x: (-x["count"], x["name"]))

    sectors = [{"name": k, **v} for k, v in sector_stats.items()]
    sectors.sort(key=lambda x: -x["count"])

    lite = [{
        "id": i["id"], "d": i["date"], "h": i["headline"], "s": i["section"],
        "f": i["firms"], "u": i["situations"], "c": i["sectors"], "p": i["priority"],
        "m": i["date"][:7], "t": i["story_id"], "x": 1 if i.get("flags") else 0,
    } for i in sorted(items, key=lambda x: x["date"], reverse=True)]

    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "site_title": cfg["site_title"],
        "site_tagline": cfg["site_tagline"],
        "sections": cfg["sections"],
        "total_items": len(items),
        "months": sorted(by_month.keys(), reverse=True),
        "date_range": [min(i["date"] for i in items), max(i["date"] for i in items)] if items else [],
        "firms": firms,
        "situations": situations,
        "sectors": sectors,
        "items": lite,
    }
    (DATA / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False))
    return index


def load_archive() -> list[dict]:
    out = []
    if not ITEMS.exists():
        return out
    for path in sorted(ITEMS.glob("*.json")):
        try:
            out.extend(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return out
