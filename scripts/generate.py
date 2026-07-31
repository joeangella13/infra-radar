#!/usr/bin/env python3
"""Daily brief generation.

Runs on GitHub Actions. Calls the Claude API with server-side web search, gets
back structured items, dedupes them against the existing archive and writes the
result into data/ and archive/.

Env:
  ANTHROPIC_API_KEY   required
  ANTHROPIC_MODEL     optional, otherwise the newest available model is chosen
  MAX_SEARCHES        optional, default 14
  LOOKBACK_DAYS       optional, default 2 (Monday widens automatically)

Flags:
  --selftest          validate config and wiring without calling the API
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import lib  # noqa: E402

OUT = lib.ROOT / "out"
MAX_TURNS = 8

SUBMIT_TOOL = {
    "name": "submit_brief",
    "description": "Submit the finished brief. Call this exactly once, at the end, "
                   "after all research is complete.",
    "input_schema": {
        "type": "object",
        "properties": {
            "coverage_note": {
                "type": "string",
                "description": "One plain sentence on what the window covered and how "
                               "the tape read. No more than 25 words.",
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
                                "properties": {"name": {"type": "string"},
                                               "url": {"type": "string"}},
                                "required": ["name", "url"],
                            },
                        },
                        "players": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "why_you_care": {"type": "string"},
                        "firms": {"type": "array", "items": {"type": "string"}},
                        "companies": {"type": "array", "items": {"type": "string"}},
                        "situations": {"type": "array", "items": {"type": "string"}},
                        "sectors": {"type": "array", "items": {"type": "string"}},
                        "geo": {"type": "array", "items": {"type": "string"}},
                        "priority": {"type": "string", "enum": ["high", "normal"]},
                    },
                    "required": ["date", "headline", "section", "sources",
                                 "players", "why_it_matters", "why_you_care"],
                },
            },
        },
        "required": ["coverage_note", "items"],
    },
}


# ------------------------------------------------------------------- prompts

def build_system(cfg: dict) -> str:
    p = cfg["reader_profile"]
    sits = "\n".join(f'  {s["key"]}: {s["label"]} - {s["note"]}'
                     for s in cfg["tracked_situations"])
    return f"""You write a daily infrastructure news brief for one reader.

WHO YOU ARE WRITING FOR
{p["who"]}

He uses this to: {"; ".join(p["uses"])}.

Deals he has personally worked on: {", ".join(p["own_deals"])}.
Funds he is targeting: {", ".join(cfg["priority_firms"])}.

HOW TO WRITE
Short, plain English. Say the thing, then say why it matters, then stop. A smart
colleague explaining something quickly, not a research report. Specifically:
  - Prefer common words. "Buys" not "executes an acquisition of". "Long-term
    contract" not "contracted revenue framework". Keep technical terms only where
    a plainer word would lose meaning.
  - Keep every number, name and date that carries information. Cut everything else.
  - No throat-clearing, no restating the headline, no "in an evolving landscape".
  - Never use the same opening construction twice in one brief.

ACCURACY - THIS MATTERS MORE THAN ANYTHING ELSE
  - Report only what you actually found in a search result you opened. If you did
    not read it, it does not go in the brief.
  - Never invent or estimate a number, date, price, stake, capacity or docket. If a
    figure was not disclosed, write "terms undisclosed". Do not guess a range.
  - Never invent a source, a URL, or an outlet name. Every URL must be one you
    actually retrieved.
  - Preserve deal status exactly: rumored, reported, proposed, announced, signed,
    agreed, completed, closed. These are not interchangeable. If the source says a
    company "is exploring" a sale, do not write that it "is selling".
  - Do not blend two stories into one item.
  - Be exact with financial terms: enterprise value, equity value, gross proceeds,
    net proceeds and stake acquired are different things. Do not use one for another.
  - If the window was quiet, return few items. Four well-sourced items beat fifteen
    padded ones. An empty list is a perfectly acceptable answer and is always better
    than one fabricated item.

SECTIONS
  sponsor_moves      Fund and sponsor deals: acquisitions, exits, minority stakes,
                     JVs, platform launches, take-privates, senior hires.
  sector_themes      Things that change how an asset gets valued: demand data,
                     pricing points, technology milestones, supply constraints,
                     landmark comps.
  market_regulatory  FERC and grid-operator actions, policy, permitting, tariffs,
                     fundraising, and exit or credit market conditions.
  tracked_situations Anything touching the watchlist below. Always set the key.

TOP-PRIORITY FIRMS (search these every run, including their portfolio companies)
  {", ".join(cfg["priority_firms"])}

SECOND-PRIORITY FIRMS (search these every run too)
  {", ".join(cfg.get("secondary_firms", []))}

WATCHLIST FIRMS
  {", ".join(cfg["watchlist_firms"])}

TRACKED SITUATIONS (use these exact keys in "situations")
{sits}

VALID SECTORS (use these exact strings)
  {", ".join(cfg["sectors"])}

EACH ITEM
  headline        One factual line under 140 characters. No hype.
  sources         1 to 3 real URLs you actually opened. Primary sources first
                  (company releases, regulator filings), then trade press.
  players         2 to 3 sentences of hard fact: who, what, how much, what stake,
                  what structure, what timing.
  why_it_matters  2 to 3 sentences, 45 to 70 words. What the cash flows look like,
                  what the buyer can actually do to create value, what it says
                  about pricing, and what to watch next.
  why_you_care    ONE sentence, 35 words maximum, saying plainly why this is useful
                  to him specifically. Tie it to an interview he is preparing for, a
                  deal he has worked on, a comp he could use, or a competitor he
                  tracks. Vary the phrasing. If it is only general context, say so
                  plainly rather than forcing a connection.
  priority        "high" only for genuinely significant items.

Research with web search first. Then call submit_brief exactly once."""


def build_prompt(cfg: dict, recent: list[dict], since: str, today: str) -> str:
    seen = "\n".join(f'  [{i["date"]}] {i["headline"]}' for i in recent[:60]) \
        or "  (archive empty)"
    return f"""Today is {today}. Cover roughly {since} through {today}.

Run dedicated searches for, at minimum:
  - each top-priority firm ({", ".join(cfg["priority_firms"])}) and its portfolio companies
  - each second-priority firm ({", ".join(cfg.get("secondary_firms", []))})
  - infrastructure sponsor transactions announced in this window
  - AI and data centre power, gas-to-power, storage, nuclear
  - ports, rail, logistics, midstream deals
  - FERC and grid-operator actions, and infrastructure fundraising
  - each tracked situation by name

ALREADY IN THE ARCHIVE. Do not repeat these unless something genuinely changed, in
which case lead the headline with what changed:
{seen}

Then call submit_brief."""


# --------------------------------------------------------------------- model

def pick_model(client) -> str:
    if os.environ.get("ANTHROPIC_MODEL"):
        return os.environ["ANTHROPIC_MODEL"]
    try:
        models = [m.id for m in client.models.list(limit=40).data]
    except Exception as e:
        print(f"  ! could not list models ({e}); falling back")
        return "claude-sonnet-4-5"
    # Sonnet first, deliberately. Opus costs roughly 2.5x per token and this is a
    # summarisation job with tight rules, not an open reasoning problem. Set the
    # ANTHROPIC_MODEL repo variable to override.
    for want in ("sonnet", "opus"):
        for mid in models:
            if want in mid.lower():
                return mid
    return models[0] if models else "claude-sonnet-4-5"


def call_with_retry(client, **kw):
    """Retry transient API failures. Anything else is raised immediately."""
    last = None
    for attempt in range(4):
        try:
            return client.messages.create(**kw)
        except Exception as e:
            last = e
            transient = any(s in str(e).lower() for s in
                            ("overloaded", "rate_limit", "429", "500", "502",
                             "503", "529", "timeout", "connection"))
            if not transient:
                raise
            wait = 5 * (2 ** attempt)
            print(f"  ! transient API error ({type(e).__name__}); retry in {wait}s")
            time.sleep(wait)
    raise last


def salvage_json(text: str):
    """Last resort: pull an items array out of a plain-text reply."""
    m = re.search(r'\{[\s\S]*"items"[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ----------------------------------------------------------------- self test

def selftest():
    cfg = lib.load_config()
    problems = []
    for key in ("priority_firms", "watchlist_firms", "tracked_situations",
                "sectors", "sections", "reader_profile"):
        if not cfg.get(key):
            problems.append(f"config.json missing '{key}'")
    keys = [s["key"] for s in cfg["tracked_situations"]]
    if len(keys) != len(set(keys)):
        problems.append("duplicate tracked_situation keys")
    archive = lib.load_archive()
    for i in archive:
        if not i.get("sources"):
            problems.append(f"unsourced item in archive: {i.get('id')}")
    try:
        import anthropic  # noqa: F401
    except ImportError:
        problems.append("anthropic package not installed")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        problems.append("ANTHROPIC_API_KEY not set")

    print(f"config: {len(cfg['watchlist_firms'])} firms, "
          f"{len(cfg['tracked_situations'])} situations, {len(cfg['sectors'])} sectors")
    print(f"archive: {len(archive)} items")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("\nall checks passed")


# ----------------------------------------------------------------------- run

def run():
    import anthropic

    cfg = lib.load_config()
    today = date.today()
    lookback = int(os.environ.get("LOOKBACK_DAYS", "2"))
    if today.weekday() == 0:
        lookback = max(lookback, 4)
    since = (today - timedelta(days=lookback)).isoformat()

    archive = lib.load_archive()
    recent = sorted([i for i in archive
                     if i["date"] >= (today - timedelta(days=21)).isoformat()],
                    key=lambda x: x["date"], reverse=True)

    client = anthropic.Anthropic()
    model = pick_model(client)
    print(f"model={model}  window={since}..{today}  archive={len(archive)} items")

    messages = [{"role": "user",
                 "content": build_prompt(cfg, recent, since, today.isoformat())}]
    tools = [
        {"type": "web_search_20250305", "name": "web_search",
         "max_uses": int(os.environ.get("MAX_SEARCHES", "14"))},
        SUBMIT_TOOL,
    ]

    payload = None
    usage = {"input": 0, "output": 0, "searches": 0}
    for turn in range(MAX_TURNS):
        resp = call_with_retry(
            client, model=model, max_tokens=16000,
            system=build_system(cfg), tools=tools, messages=messages,
        )
        usage["input"] += getattr(resp.usage, "input_tokens", 0) or 0
        usage["output"] += getattr(resp.usage, "output_tokens", 0) or 0
        st = getattr(resp.usage, "server_tool_use", None)
        usage["searches"] += getattr(st, "web_search_requests", 0) or 0 if st else 0
        print(f"  turn {turn}: stop_reason={resp.stop_reason} "
              f"in={usage['input']} out={usage['output']} searches={usage['searches']}")

        for block in resp.content:
            if getattr(block, "type", "") == "tool_use" and block.name == "submit_brief":
                payload = block.input
                break
        if payload is not None:
            break

        text = "".join(getattr(b, "text", "") for b in resp.content)
        if resp.stop_reason in ("end_turn", "max_tokens"):
            salvaged = salvage_json(text)
            if salvaged and salvaged.get("items"):
                print("  (recovered items from plain-text reply)")
                payload = salvaged
                break

        messages.append({"role": "assistant", "content": resp.content})
        nudge = ("You have enough. Stop researching and call submit_brief now with "
                 "what you have. If you found nothing that clears the bar, call it "
                 "with an empty items list.")
        if resp.stop_reason == "max_tokens":
            nudge = ("You ran out of room. Call submit_brief immediately with only "
                     "your strongest items. Do not search again.")
        messages.append({"role": "user", "content": nudge})

    if payload is None:
        print("\nERROR: the model never called submit_brief after "
              f"{MAX_TURNS} turns. Nothing was written. The archive is unchanged.")
        sys.exit(1)

    raw_items = payload.get("items", []) or []
    print(f"  model returned {len(raw_items)} items")

    fresh = []
    for r in raw_items:
        item = lib.normalise(r, cfg)
        if not item:
            print(f"  - dropped (no usable source): {str(r.get('headline'))[:70]}")
            continue
        if item["date"] > today.isoformat():
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
        "usage": usage,
        "new_items": [{"id": i["id"], "headline": i["headline"],
                       "section": i["section"], "date": i["date"],
                       "flags": i.get("flags", []), "priority": i["priority"],
                       "firms": i["firms"], "situations": i["situations"],
                       "sectors": i.get("sectors", []),
                       "sources_n": len(i["sources"]),
                       "story_size": i.get("story_size", 1),
                       "why_you_care": i.get("why_you_care", ""),
                       "url": i["sources"][0]["url"]} for i in new],
    }, indent=2))
    print(f"  archive now {index['total_items']} items")
    print(f"  usage: {usage['input']:,} in / {usage['output']:,} out / "
          f"{usage['searches']} searches")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        run()
