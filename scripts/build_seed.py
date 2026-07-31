#!/usr/bin/env python3
"""One-off: turn the raw backfill research into the archive."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import lib  # noqa: E402

cfg = lib.load_config()
raw = json.loads((pathlib.Path(__file__).parent / "raw_seed.json").read_text())

normalised = []
dropped = 0
for r in raw:
    item = lib.normalise(r, cfg)
    if item:
        normalised.append(item)
    else:
        dropped += 1

# keep the window honest: nothing dated in the future, nothing older than 15 months
normalised = [i for i in normalised if "2025-05-01" <= i["date"] <= "2026-07-31"]

index = lib.write_archive(normalised, cfg)

print(f"raw={len(raw)}  normalised={len(normalised)}  dropped={dropped}")
print(f"after dedupe/threading: {index['total_items']} items")
print(f"date range: {index['date_range']}")
print(f"months: {', '.join(index['months'])}")
print(f"\ntop firms:")
for f in index["firms"][:15]:
    star = " *" if f["priority"] else ""
    print(f"   {f['count']:>3}  {f['name']}{star}")
print(f"\ntracked situations:")
for s in index["situations"]:
    print(f"   {s['count']:>3}  {s['label']}")
print(f"\nsections:")
from collections import Counter  # noqa: E402
print("  ", dict(Counter(i["s"] for i in index["items"])))
