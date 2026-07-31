#!/usr/bin/env python3
"""Export the archive to readable markdown.

The JSON in data/ is what the website reads. The markdown in archive/ is what a
person - or a future AI session - reads. Every item, every month, plain text,
diffable in git and greppable from anywhere.

Writes:
  archive/README.md          index: counts, firms, situations, links
  archive/YYYY-MM.md         every item that month, newest first
  archive/situations/KEY.md  the full history of one tracked situation
  archive/firms/NAME.md      the full history of one firm (watchlist only)
"""
from __future__ import annotations

import pathlib
import re
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import lib  # noqa: E402

ARCHIVE = lib.ROOT / "archive"
SEC = {"sponsor_moves": "Sponsor moves", "sector_themes": "Sector themes",
       "market_regulatory": "Market / regulatory", "tracked_situations": "Tracked situations"}


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "unnamed"


def render_item(it: dict, heading: str = "###") -> str:
    flag = "**[watchlist]** " if it.get("flags") else ""
    srcs = ", ".join(f"[{s['name']}]({s['url']})" for s in it["sources"])
    tags = []
    if it["firms"]:
        tags.append("Firms: " + ", ".join(it["firms"]))
    if it["situations"]:
        tags.append("Situations: " + ", ".join(it["situations"]))
    if it["sectors"]:
        tags.append("Sectors: " + ", ".join(it["sectors"]))
    if it.get("geo"):
        tags.append("Geo: " + ", ".join(it["geo"]))

    out = [f"{heading} {flag}{it['headline']}", ""]
    out.append(f"`{it['date']}` · {SEC.get(it['section'], it['section'])} · {srcs}")
    out.append("")
    if it.get("players"):
        out.append(f"**Deal / players.** {it['players']}")
        out.append("")
    if it.get("why_it_matters"):
        out.append(f"**Why it matters.** {it['why_it_matters']}")
        out.append("")
    if it.get("why_you_care"):
        out.append(f"**Why you care.** {it['why_you_care']}")
        out.append("")
    if tags:
        out.append("<sub>" + " · ".join(tags) + f" · id: `{it['id']}`</sub>")
        out.append("")
    return "\n".join(out)


def write(path: pathlib.Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    cfg = lib.load_config()
    items = lib.load_archive()
    if not items:
        print("archive empty, nothing to export")
        return

    items.sort(key=lambda x: x["date"], reverse=True)

    # ---- monthly files
    by_month = defaultdict(list)
    for it in items:
        by_month[it["date"][:7]].append(it)

    for month, group in by_month.items():
        body = [f"# {month}", "",
                f"{len(group)} items. Newest first. "
                f"Generated from `data/items/{month}.json`.", "", "---", ""]
        for it in group:
            body.append(render_item(it))
            body.append("---")
            body.append("")
        write(ARCHIVE / f"{month}.md", "\n".join(body))

    # ---- one file per tracked situation
    sit_meta = {s["key"]: s for s in cfg["tracked_situations"]}
    for key, meta in sit_meta.items():
        group = [i for i in items if key in i["situations"]]
        body = [f"# {meta['label']}", "", meta.get("note", ""), ""]
        if group:
            body += [f"{len(group)} items, {group[-1]['date']} to {group[0]['date']}.",
                     "", "---", ""]
            for it in group:
                body.append(render_item(it))
                body.append("---")
                body.append("")
        else:
            body += ["No items yet.", ""]
        write(ARCHIVE / "situations" / f"{key}.md", "\n".join(body))

    # ---- one file per watchlist firm that actually appears
    firm_items = defaultdict(list)
    for it in items:
        for f in it["firms"]:
            firm_items[f].append(it)

    written_firms = []
    for firm in cfg["watchlist_firms"]:
        group = firm_items.get(firm, [])
        if not group:
            continue
        written_firms.append(firm)
        body = [f"# {firm}", "",
                f"{len(group)} items, {group[-1]['date']} to {group[0]['date']}.",
                "", "---", ""]
        for it in group:
            body.append(render_item(it))
            body.append("---")
            body.append("")
        write(ARCHIVE / "firms" / f"{safe(firm)}.md", "\n".join(body))

    # ---- index
    months = sorted(by_month.keys(), reverse=True)
    idx = [
        "# Archive", "",
        f"{len(items)} items, {items[-1]['date']} to {items[0]['date']}.", "",
        "Plain-text mirror of the JSON the site reads. Every item appears in its",
        "monthly file; items are additionally cross-filed by situation and by firm.", "",
        "## By month", "",
    ]
    idx += [f"- [{m}]({m}.md) — {len(by_month[m])} items" for m in months]

    idx += ["", "## Tracked situations", ""]
    for key, meta in sorted(sit_meta.items(), key=lambda kv: kv[1]["label"]):
        n = sum(1 for i in items if key in i["situations"])
        idx.append(f"- [{meta['label']}](situations/{key}.md) — {n} items")

    idx += ["", "## Firms", ""]
    for firm in sorted(written_firms, key=lambda f: -len(firm_items[f])):
        star = " ◆" if firm in cfg["priority_firms"] else ""
        idx.append(f"- [{firm}](firms/{safe(firm)}.md){star} — {len(firm_items[firm])} items")

    idx += ["", "---", "",
            "Generated by `scripts/export_markdown.py`. Do not edit by hand;",
            "changes are overwritten on the next run.", ""]
    write(ARCHIVE / "README.md", "\n".join(idx))

    print(f"markdown: {len(months)} months, {len(sit_meta)} situations, "
          f"{len(written_firms)} firms, {len(items)} items")


if __name__ == "__main__":
    main()
