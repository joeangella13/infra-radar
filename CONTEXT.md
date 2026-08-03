# Context

This file exists so that any AI session — or any person — can pick this project up
cold and understand what it is, who it is for, and what the rules are. Read this
first, then `archive/README.md` for the news itself.

---

## Who this is for

Joe Angella. He joins **Morgan Stanley Infrastructure Partners (MSIP)** on
**10 August 2026** as an investor, moving across from Rothschild & Co's
Infrastructure, Power & Renewables team in New York, where he was an investment
banking analyst.

He is not job hunting and is not interviewing. He has the seat. Nothing in this
archive should be framed as interview preparation.

He reads this to:

- stay current on his own firm's activity, portfolio companies and pipeline
- track competing sponsors and what they are paying
- source and pressure-test investment ideas
- build comps and market context for underwriting

**His firm: MSIP.** Its transactions are his firm's transactions and its portfolio
companies are his portfolio. MSIP news is internal news and gets the ◆ flag.

**Direct competitors:** Stonepeak, I Squared Capital, EQT Infrastructure. These get
a second-tier flag.

**Deals he executed at Rothschild** — the "tracked situations". He knows these better
than almost anyone, they remain live, and several are credible sourcing angles to
bring to MSIP:

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
4. **Why you care** — one sentence on why it matters to *him* specifically. Framed
   by type: an MSIP item is his own firm; a Stonepeak, I Squared or EQT item is a
   competitor's move; a tracked situation is a deal he executed and still knows
   cold; a sector or policy item is a comp, a pricing point or an underwriting risk.
   Never framed as interview preparation — he has the job

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
- `archive/firms/<name>.md` — everything on one firm, including MSIP itself
- `data/index.json` — the same data structured, if you need to compute over it

Useful things to ask for: a summary of what happened on a situation over a period;
what a competitor has been buying; comps for a sector; what MSIP has done this
quarter; what changed since a given date.

---

## Changing it

- **`config.json`** — watchlists, tracked situations, sectors, name aliases, and the
  `reader_profile` block that drives "why you care". Update the profile when the job
  or the target list changes.
- **`scripts/generate.py`** — `build_system()` is the prompt. Voice and accuracy
  rules live there.
- **`.github/workflows/daily.yml`** — schedule.
