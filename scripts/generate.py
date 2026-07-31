#!/usr/bin/env python3
"""Daily brief generation.

Runs on GitHub Actions. Calls the Claude API with server-side web search,
gets back structured items, dedupes them against the existing archive and
writes the result into data/.

Env:
  ANTHROPIC_API_KEY   required
  ANTHROPIC_MODEL     optional, otherwise the newest available model is chosen
  MAX_SEARCHES        optional, default 14
  LOOKBACK_DAYS       optional, default 2 (Monday runs widen automatically)
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import lib  # noqa: E402

try:
    import anthropic
except ImportError:
    sys.exit("pip install anthropic")

ROOT = lib.ROOT
OUT = ROOT / "out"

SUBMIT_TOOL = {
    "name": "submit_brief",
    "description": "Submit the finished brief. Call this exactly once, at the end, "
                   "after all research is complete.",
    "input_schema": {
        "type": "object",
        "properties": {
            "coverage_note": {
                "type": "string",
                "description": "One sentence on the window covered and how the tape read "
                               "(busy, quiet, dominated by one theme).",
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Announcement date, YYYY-MM-DD"},
                        "headline": {"type": "string"},
                        "section": {
                            "type": "string",
                            "enum": ["sponsor_moves", "sector_themes",
                                     "market_regulatory", "tracked_situations"],
                        },
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "url": {"type": "string"},
                                },
                                "required": ["name", "url"],
                            },
                        },
                        "players": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "firms": {"type": "array", "items": {"type": "string"}},
                        "companies": {"type": "array", "items": {"type": "string"}},
                        "situations": {"type": "array", "items": {"type": "string"}},
                        "sectors": {"type": "array", "items": {"type": "string"}},
                        "geo": {"type": "array", "items": {"type": "string"}},
                        "priority": {"type": "string", "enum": ["high", "normal"]},
                    },
                    "required": ["date", "headline", "section", "sources",
                                 "players", "why_it_matters"],
                },
            },
        },
        "required": ["coverage_note", "items"],
    },
}


def build_system(cfg: dict) -> str:
    sits = "\n".join(
        f'  - {s["key"]}: {s["label"]} — {s["note"]}' for s in cfg["tracked_situations"]
    )
    return f"""You are an infrastructure investment research analyst producing a daily brief for an \
infrastructure private equity investor. He came out of infrastructure investment banking \
(power, renewables, transport, logistics, midstream) and reads this to source ideas, track \
competitors and stay current on situations he knows well.

VOICE
Write like a strong investment banking associate: concise, commercial, precise. Lead with the \
fact, then the implication. No filler, no hedging padding, no marketing adjectives, no \
"in today's rapidly evolving landscape". Never use em dashes as a stylistic tic. Be careful \
and exact about deal status: rumored vs announced vs signed vs closed. Be exact about \
enterprise value vs equity value vs proceeds vs stake.

SECTIONS
  sponsor_moves      Fund and sponsor transactions: acquisitions, exits, minority stakes, JVs,
                     platform launches, take-privates, senior hires.
  sector_themes      Developments that change how an infra asset is underwritten: demand data,
                     pricing points, technology milestones, supply constraints, landmark comps.
  market_regulatory  FERC and RTO/ISO actions, policy, permitting, tariffs, fundraising and dry
                     powder, exit and credit market conditions.
  tracked_situations Anything touching the named watchlist below. Always assign the situation key.

PRIORITY FIRMS (flag anything involving them, including their portfolio companies)
  {", ".join(cfg["priority_firms"])}

WATCHLIST FIRMS
  {", ".join(cfg["watchlist_firms"])}

TRACKED SITUATIONS (use these exact keys in the "situations" field)
{sits}

VALID SECTORS (use these exact strings)
  {", ".join(cfg["sectors"])}

PER-ITEM REQUIREMENTS
  headline         One factual line, under 140 characters. No hype.
  sources          1 to 3 real, working URLs you actually opened via search. Prefer primary
                   sources (press releases, company sites, regulator filings), then trade press.
  players          1 to 3 sentences of hard fact: who, what, size, stake, structure, timing.
                   Write "terms undisclosed" when true rather than guessing.
  why_it_matters   3 to 5 sentences for an investor: the cash-flow profile, the value-creation
                   or de-risking lever, what the process or entry basis implies, the read-through
                   to comparable assets, and what to watch next. This is the part he reads.
  priority         "high" only for genuinely significant items.

HARD RULES
  - Never invent a transaction, a number, a date, a docket or a source. Every item must trace to
    something you actually found in search.
  - If the window was quiet, return few items. Five well-sourced items beat fifteen padded ones.
    Returning an empty list is acceptable and preferable to fabrication.
  - Do not re-report a story already in the archive unless there is a genuine new development,
    in which case lead the headline with what changed.
  - Assign the announcement date of the news, not today's date.

Research thoroughly with web search before calling submit_brief. Call submit_brief exactly once."""


def build_prompt(cfg: dict, recent: list[dict], since: str, today: str) -> str:
    seen = "\n".join(f'  - [{i["date"]}] {i["headline"]}' for i in recent[:60]) or "  (archive empty)"
    return f"""Today is {today}. Produce the brief covering roughly {since} through {today}.

Search across all four sections. At minimum run dedicated searches for:
  - each priority firm ({", ".join(cfg["priority_firms"])}) and recent deal activity
  - large-cap infrastructure sponsor transactions announced in this window
  - AI / data center power, gas-to-power, storage, nuclear developments
  - ports, rail, logistics, midstream transactions
  - FERC / RTO regulatory actions and infrastructure fundraising
  - each tracked situation by name

ALREADY IN THE ARCHIVE — do not repeat these unless there is a real new development:
{seen}

Return the brief via submit_brief."""


def pick_model(client) -> str:
    if os.environ.get("ANTHROPIC_MODEL"):
        return os.environ["ANTHROPIC_MODEL"]
    try:
        models = [m.id for m in client.models.list(limit=40).data]
    except Exception:
        return "claude-sonnet-4-5"
    for want in ("opus", "sonnet"):
        for mid in models:
            if want in mid.lower():
                return mid
    return models[0] if models else "claude-sonnet-4-5"


def run():
    cfg = lib.load_config()
    today = date.today()
    lookback = int(os.environ.get("LOOKBACK_DAYS", "2"))
    if today.weekday() == 0:       # Monday picks up the weekend
        lookback = max(lookback, 4)
    since = (today - timedelta(days=lookback)).isoformat()

    archive = lib.load_archive()
    recent = sorted(
        [i for i in archive if i["date"] >= (today - timedelta(days=21)).isoformat()],
        key=lambda x: x["date"], reverse=True,
    )

    client = anthropic.Anthropic()
    model = pick_model(client)
    print(f"model={model}  window={since}..{today}  archive={len(archive)} items")

    messages = [{"role": "user", "content": build_prompt(cfg, recent, since, today.isoformat())}]
    tools = [
        {"type": "web_search_20250305", "name": "web_search",
         "max_uses": int(os.environ.get("MAX_SEARCHES", "14"))},
        SUBMIT_TOOL,
    ]

    payload = None
    for turn in range(6):
        resp = client.messages.create(
            model=model,
            max_tokens=16000,
            system=build_system(cfg),
            tools=tools,
            messages=messages,
        )
        for block in resp.content:
            if getattr(block, "type", "") == "tool_use" and block.name == "submit_brief":
                payload = block.input
                break
        if payload is not None:
            break
        if resp.stop_reason != "tool_use":
            print(f"  turn {turn}: stop_reason={resp.stop_reason}, nudging")
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user",
                             "content": "Call submit_brief now with what you have."})
            continue
        messages.append({"role": "assistant", "content": resp.content})

    if payload is None:
        sys.exit("model never called submit_brief")

    raw_items = payload.get("items", [])
    print(f"  model returned {len(raw_items)} items")

    fresh = []
    for r in raw_items:
        item = lib.normalise(r, cfg)
        if not item:
            continue
        if item["date"] > today.isoformat():          # no future-dated news
            item["date"] = today.isoformat()
        fresh.append(item)

    known = {lib.canon_url(s["url"]) for i in archive for s in i["sources"]}
    known_titles = [lib.tokens(i["headline"]) for i in archive
                    if i["date"] >= (today - timedelta(days=30)).isoformat()]

    new = []
    for item in fresh:
        if any(lib.canon_url(s["url"]) in known for s in item["sources"]):
            continue
        if any(lib.jaccard(lib.tokens(item["headline"]), t) >= 0.6 for t in known_titles):
            continue
        new.append(item)

    print(f"  {len(new)} new after dedupe against archive")

    index = lib.write_archive(archive + new, cfg)

    OUT.mkdir(exist_ok=True)
    (OUT / "run.json").write_text(json.dumps({
        "run_date": today.isoformat(),
        "model": model,
        "window": [since, today.isoformat()],
        "returned": len(raw_items),
        "added": len(new),
        "total": index["total_items"],
        "coverage_note": payload.get("coverage_note", ""),
        "new_items": [{"headline": i["headline"], "section": i["section"],
                       "date": i["date"], "flags": i.get("flags", []),
                       "priority": i["priority"],
                       "firms": i["firms"], "situations": i["situations"],
                       "url": i["sources"][0]["url"]} for i in new],
    }, indent=2))
    print(f"  archive now {index['total_items']} items")


if __name__ == "__main__":
    run()
