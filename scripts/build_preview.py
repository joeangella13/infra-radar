#!/usr/bin/env python3
"""Bundle the site + archive into one self-contained HTML file (offline preview)."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import lib

html = (lib.ROOT / "index.html").read_text()
payload = {
    "index": json.loads((lib.DATA / "index.json").read_text()),
    "months": {p.stem: json.loads(p.read_text()) for p in sorted(lib.ITEMS.glob("*.json"))},
}
blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
out = html.replace("<script>\n/* ====", f"<script>window.__DATA__={blob};</script>\n<script>\n/* ====", 1)
dest = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/infra-radar-preview.html")
dest.write_text(out)
print(f"{dest}  {dest.stat().st_size/1024:.0f} KB")
