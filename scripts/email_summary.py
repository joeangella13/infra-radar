#!/usr/bin/env python3
"""Turn out/run.json into the short morning email (subject + HTML body)."""
import json
import os
import pathlib
import sys

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


def main():
    run = json.loads((OUT / "run.json").read_text())
    cfg = lib.load_config()
    sit_label = {s["key"]: s["label"] for s in cfg["tracked_situations"]}
    items = run["new_items"]

    day = run["run_date"]
    subject = (f"Infra Radar — {day} — {len(items)} new"
               if items else f"Infra Radar — {day} — quiet tape")

    order = ["tracked_situations", "sponsor_moves", "market_regulatory", "sector_themes"]
    items.sort(key=lambda i: (order.index(i["section"]) if i["section"] in order else 9,
                              0 if i["priority"] == "high" else 1))

    rows = []
    for i in items[:8]:
        flag = ('<span style="color:#c9761a;font-weight:700">&#9670;</span> '
                if i.get("flags") else "")
        ctx = ", ".join(
            [sit_label.get(s, s) for s in i.get("situations", [])] or i.get("firms", [])[:2]
        )
        rows.append(
            f'<li style="margin-bottom:9px">{flag}'
            f'<a href="{i["url"]}" style="color:#1a1a1a;text-decoration:none">'
            f'<b>{i["headline"]}</b></a><br>'
            f'<span style="color:#83817a;font-size:12px">'
            f'{SEC_LABEL.get(i["section"], i["section"])}'
            f'{" &middot; " + ctx if ctx else ""} &middot; {i["date"]}</span></li>'
        )

    more = (f'<p style="color:#83817a;font-size:12.5px;margin:4px 0 0">'
            f'+{len(items) - 8} more on the site</p>') if len(items) > 8 else ""

    body_top = (run.get("coverage_note") or "").strip()
    link = f'{SITE}/' if SITE else "the site"
    cta = (f'<p style="margin:18px 0 6px"><a href="{SITE}/" '
           f'style="background:#2a78d6;color:#fff;padding:9px 15px;border-radius:7px;'
           f'text-decoration:none;font-size:13.5px;display:inline-block">'
           f'Open the timeline</a></p>') if SITE else ""

    html = f"""<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;font-size:14px;
line-height:1.55;color:#1a1a1a;max-width:640px">
<p style="margin:0 0 14px;color:#52514e">{body_top}</p>
{"<ul style='margin:0;padding-left:19px'>" + "".join(rows) + "</ul>" + more
   if rows else
   "<p style='margin:0;color:#52514e'>Nothing new cleared the bar this window. "
   "The archive is unchanged.</p>"}
{cta}
<p style="color:#a8a69e;font-size:11.5px;margin-top:22px;border-top:1px solid #e9e7e2;padding-top:10px">
Auto-generated from public sources. {run["total"]} items in the archive.
Dates are announcement dates, not send dates. Verify before relying on any figure.</p>
</div>"""

    (OUT / "email_subject.txt").write_text(subject)
    (OUT / "email.html").write_text(html)
    print(f"subject: {subject}")
    print(f"items in email: {len(rows)}  link: {link}")


if __name__ == "__main__":
    main()
