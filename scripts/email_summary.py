#!/usr/bin/env python3
"""Turn out/run.json into the short morning email (subject + HTML body).

Not everything generated in a morning belongs in your inbox. This scores each
new item and sends only what clears the bar, hardest-hitting first. The weights
live in config.json under "email" so they can be tuned without touching code.
"""
import json
import os
import pathlib
import sys
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import lib  # noqa: E402

OUT = lib.ROOT / "out"
SITE = os.environ.get("SITE_URL", "").rstrip("/")

SEC_LABEL = {
    "sponsor_moves": "Sponsor moves",
    "sector_themes": "Sector themes",
    "market_regulatory": "Market / regulatory",
    "tracked_situations": "Tracked situations",
}


def score(item: dict, cfg: dict, today: str) -> tuple[int, list[str]]:
    """Rank an item for inbox-worthiness. Returns (score, reasons)."""
    w = cfg["email"]["weights"]
    pts, why = 0, []

    # 1. his own deals always win. nothing outranks a situation he has worked on.
    if item.get("situations"):
        pts += w["tracked_situation"]
        why.append("tracked situation")

    # 2. the funds he is targeting, in two tiers, including portfolio companies
    flags = item.get("flags", [])
    if "priority_firm" in flags:
        pts += w["priority_firm"]
        why.append("top-tier firm")
    elif "secondary_firm" in flags:
        pts += w["secondary_firm"]
        why.append("second-tier firm")

    # 3. the model's own read on significance
    if item.get("priority") == "high":
        pts += w["high_priority"]
        why.append("high priority")

    # 4. named sponsors he tracks, capped so a long list can't dominate
    hits = sum(1 for f in item.get("firms", []) if f in cfg["watchlist_firms"])
    if hits:
        bump = min(hits * w["watchlist_firm_each"], w["watchlist_firm_cap"])
        pts += bump
        why.append(f"{hits} watchlist firm{'s' if hits > 1 else ''}")

    # 5. a deal outranks a theme, all else equal
    pts += w["section"].get(item.get("section", ""), 0)

    # 6. freshness
    if item.get("date") == today:
        pts += w["same_day"]
    elif item.get("date", "") and item["date"] < today:
        pts += w["prior_day"]

    # 7. corroborated by more than one outlet
    if item.get("sources_n", 1) > 1:
        pts += w["multi_source"]
        why.append("multi-sourced")

    # 8. a story he has already been following moved again
    if item.get("story_size", 1) > 1:
        pts += w["developing_story"]
        why.append("developing story")

    return pts, why


def row(i: dict, sit_label: dict, lead: bool) -> str:
    fl = i.get("flags", [])
    flag = ('<span style="color:#c9761a;font-weight:700">&#9670;</span> '
            if "priority_firm" in fl else
            '<span style="color:#83817a">&#9671;</span> '
            if "secondary_firm" in fl else "")
    ctx = ", ".join([sit_label.get(s, s) for s in i.get("situations", [])]
                    or i.get("firms", [])[:2])
    meta = (f'{SEC_LABEL.get(i["section"], i["section"])}'
            f'{" &middot; " + ctx if ctx else ""} &middot; {i["date"]}')
    size = "15px" if lead else "14px"
    care = (f'<div style="color:#52514e;font-size:13px;margin-top:3px">'
            f'{i["why_you_care"]}</div>') if lead and i.get("why_you_care") else ""
    return (
        f'<li style="margin-bottom:{"13px" if lead else "8px"}">{flag}'
        f'<a href="{i["url"]}" style="color:#1a1a1a;text-decoration:none;'
        f'font-size:{size}"><b>{i["headline"]}</b></a><br>'
        f'<span style="color:#83817a;font-size:11.5px">{meta}</span>{care}</li>'
    )


def main():
    run = json.loads((OUT / "run.json").read_text())
    cfg = lib.load_config()
    ecfg = cfg["email"]
    sit_label = {s["key"]: s["label"] for s in cfg["tracked_situations"]}
    today = run.get("run_date") or date.today().isoformat()

    scored = []
    for i in run["new_items"]:
        pts, why = score(i, cfg, today)
        scored.append((pts, why, i))
    scored.sort(key=lambda x: -x[0])

    kept = [s for s in scored if s[0] >= ecfg["min_score"]][:ecfg["max_items"]]
    dropped = len(scored) - len(kept)

    lead = kept[:ecfg["lead_count"]]
    rest = kept[ecfg["lead_count"]:]

    top = kept[0][2] if kept else None
    subject = (f'Infra Radar — {today} — {top["headline"][:60]}'
               if top else f"Infra Radar — {today} — quiet tape")

    body = []
    note = (run.get("coverage_note") or "").strip()
    if note:
        body.append(f'<p style="margin:0 0 14px;color:#52514e">{note}</p>')

    if lead:
        body.append("<ul style='margin:0 0 16px;padding-left:19px'>"
                    + "".join(row(i, sit_label, True) for _, _, i in lead) + "</ul>")
    if rest:
        body.append('<p style="font-size:11px;letter-spacing:.07em;color:#a8a69e;'
                    'text-transform:uppercase;margin:0 0 6px">Also</p>')
        body.append("<ul style='margin:0;padding-left:19px'>"
                    + "".join(row(i, sit_label, False) for _, _, i in rest) + "</ul>")
    if not kept:
        body.append("<p style='margin:0;color:#52514e'>Nothing cleared the bar this "
                    "window. The site is still up to date.</p>")
    if dropped:
        body.append(f'<p style="color:#a8a69e;font-size:12px;margin:10px 0 0">'
                    f'{dropped} lower-ranked item{"s" if dropped > 1 else ""} went to '
                    f'the site but not this email.</p>')

    cta = (f'<p style="margin:18px 0 6px"><a href="{SITE}/" '
           f'style="background:#2a78d6;color:#fff;padding:9px 15px;border-radius:7px;'
           f'text-decoration:none;font-size:13.5px;display:inline-block">'
           f'Open the timeline</a></p>') if SITE else ""

    html = f"""<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;
font-size:14px;line-height:1.55;color:#1a1a1a;max-width:640px">
{"".join(body)}
{cta}
<p style="color:#a8a69e;font-size:11.5px;margin-top:22px;border-top:1px solid #e9e7e2;
padding-top:10px">Auto-generated from public sources. {run["total"]} items in the archive.
Dates are announcement dates. Verify before relying on any figure.</p>
</div>"""

    # trailing newlines matter: the workflow reads these through a shell heredoc,
    # and a file with no final newline swallows the closing delimiter
    (OUT / "email_subject.txt").write_text(subject.replace("\n", " ").strip() + "\n")
    (OUT / "email.html").write_text(html.rstrip() + "\n")

    print(f"subject: {subject}")
    print(f"ranked {len(scored)} items, sending {len(kept)}, holding back {dropped}")
    for pts, why, i in scored:
        mark = "SEND" if any(i is k[2] for k in kept) else "hold"
        print(f"  {mark} {pts:>4}  {i['headline'][:62]}"
              + (f"   [{', '.join(why)}]" if why else ""))


if __name__ == "__main__":
    main()
