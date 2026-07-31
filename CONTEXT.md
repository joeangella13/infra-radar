# Context

This file exists so that any AI session — or any person — can pick this project up
cold and understand what it is, who it is for, and what the rules are. Read this
first, then `archive/README.md` for the news itself.

---

## Who this is for

Joe Angella. Investment banking analyst at Rothschild & Co in New York, in the
Infrastructure, Power & Renewables group. He is moving from infrastructure banking
into infrastructure private equity.

He reads this to:

- source investment ideas
- prepare for PE interviews — walk me through a deal, is this a good investment and
  why, why this fund
- build market context and comps for client pitches
- track what competing sponsors are doing

**Funds he is targeting:** MSIP (Morgan Stanley Infrastructure Partners), Stonepeak,
Greenbriar Equity Group. Items touching these get flagged.

**Deals he has personally worked on** — these are the "tracked situations", and news
on them matters more to him than anything else in the archive:

| Situation | What it is |
|---|---|
| Brightline Florida | Passenger rail; bond restructuring, ridership, commuter rail |
| Hydrostor | Long-duration compressed air energy storage |
| Avangrid / ArcLight | North American wind and solar portfolio transactions |
| FTAI Infrastructure | Transtar, Long Ridge, Jefferson, Repauno |
| McDermott / NMDC | Energy engineering and marine construction |
| Jennmar / Weber Mining | Ground control and mining consumables |
| Odfjell Terminals | Liquids tank terminals, Houston and Charleston |
| Sisu / Miratech | Distributed generation services, gas-to-AI power |
| LOGISTEC / Termont | Canadian port terminal operations |

**Sectors he covers:** power and renewables, energy transition and storage, data
centre and AI power, gas-to-power, nuclear and SMRs, transport and logistics, ports,
rail, midstream, mining services.

---

## What gets written, and how

Every item carries four things:

1. **Headline** — one factual line, no hype
2. **Deal / players** — the hard facts: who, what, how much, what stake, what timing
3. **Why it matters** — the investor read, 2 to 3 sentences
4. **Why you care** — one sentence on why it is useful to *him* specifically: an
   interview it is relevant to, a deal he has worked on, a comp he could use, a
   competitor he tracks

Voice: short, plain English. Say the thing, say why it matters, stop. A smart
colleague explaining something quickly, not a research report.

---

## The accuracy rules

These are not stylistic preferences. They are the point of the archive.

- **Report only what was actually found in a source that was actually opened.**
  If it wasn't read, it doesn't go in.
- **Never invent or estimate a number, date, price, stake, capacity or docket.**
  If a figure wasn't disclosed, say "terms undisclosed". Do not guess a range.
- **Never invent a source, a URL or an outlet name.** Items with no working source
  URL are rejected in code, not just discouraged in the prompt.
- **Preserve deal status exactly.** Rumored, reported, proposed, announced, signed,
  agreed, completed and closed are different things and are not interchangeable.
  "Exploring a sale" is not "selling".
- **Do not blend two stories into one item.**
- **Be exact with financial terms.** Enterprise value, equity value, gross proceeds,
  net proceeds and stake acquired are distinct. Never substitute one for another.
- **A quiet day is a valid answer.** Four well-sourced items beat fifteen padded
  ones. An empty list is always better than one fabricated item.

The commentary is model-generated. Treat it as a research starting point. Check the
source before anything goes into a deck.

---

## How to use this archive in a future session

- `archive/README.md` — index of everything
- `archive/YYYY-MM.md` — every item that month
- `archive/situations/<key>.md` — the full run of one tracked situation, which is
  usually the fastest way to reconstruct how a story developed
- `archive/firms/<name>.md` — everything on one firm, useful before an interview
- `data/index.json` — the same data structured, if you need to compute over it

Useful things to ask for: a summary of what happened on a situation over a period;
firm activity before an interview; comps for a sector; what changed since a date.

---

## Changing it

- **`config.json`** — watchlists, tracked situations, sectors, name aliases, and the
  `reader_profile` block that drives "why you care". Update the profile when the job
  or the target list changes.
- **`scripts/generate.py`** — `build_system()` is the prompt. Voice and accuracy
  rules live there.
- **`.github/workflows/daily.yml`** — schedule.
