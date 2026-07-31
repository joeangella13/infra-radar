# Infra Radar

A self-updating infrastructure PE news archive. GitHub Actions runs a research job
every weekday morning, Claude writes and tags the items, the results are committed
into `data/`, and GitHub Pages serves a timeline you can scroll back through.

Nothing runs on your machine. If your laptop is shut, the brief still lands.

---

## What it does

- **Timeline** — reverse-chronological, grouped by day, scroll back through the archive
- **Firm pages** — click MSIP (or any firm) for everything the archive has on them, with a
  7d / 30d / 90d / 1y / all-time filter and a monthly mention sparkline
- **Tracked situations** — a dedicated page per situation on the watchlist, so you can see
  a story's whole progression in one place
- **Storylines** — recurring coverage of the same situation is threaded, so "Brightline gets
  another extension" chains to every prior extension
- **Search** — full text across headlines, deal facts and the commentary
- **Morning email** — a short digest with a link, not the full brief

---

## Setup

### Windows

```powershell
winget install --id Git.Git -e
winget install --id GitHub.cli -e
# close and reopen PowerShell, then:
cd $HOME\Downloads\infra-radar
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

### macOS / Linux

```bash
brew install gh
cd ~/Downloads/infra-radar
./setup.sh
```

Either script creates the repo, pushes, sets the secrets, enables Pages and triggers
the first run. It prompts for your Anthropic API key and, optionally, a Gmail app
password. Pass a different repo name with `-RepoName notes` (PowerShell) or
`./setup.sh notes` (bash) — the name becomes your public URL.

Everything below is the same thing done by hand.

---

## Manual setup (about 10 minutes)

### 1. Create the repo and push

```bash
gh repo create infra-radar --public --source=. --push
# or: create it in the GitHub UI, then
#   git init && git add -A && git commit -m "initial" && git push
```

### 2. Turn on Pages

Repo → **Settings → Pages** → Source: **Deploy from a branch** → Branch: `main`, folder `/ (root)` → Save.

Your site appears at `https://<username>.github.io/infra-radar/` within a minute or two.

### 3. Add the API key

Repo → **Settings → Secrets and variables → Actions**

**Secrets** tab:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from https://console.anthropic.com |
| `MAIL_USERNAME` | your Gmail address (optional — skip to disable email) |
| `MAIL_PASSWORD` | a Gmail **app password**, not your login password (optional) |

**Variables** tab:

| Name | Value |
|---|---|
| `SITE_URL` | `https://<username>.github.io/infra-radar` |
| `EMAIL_TO` | where the digest goes |
| `ANTHROPIC_MODEL` | optional — leave unset and the newest available model is picked automatically |

A Gmail app password comes from Google Account → Security → 2-Step Verification → App passwords.
If you skip the two mail secrets, everything else still runs and the email step is silently skipped.

### 4. Run it once by hand

Repo → **Actions → Daily brief → Run workflow**. Check the run summary for what it added.

### Turning the email on later

If you skipped email at setup, add it any time:

```bash
gh secret   set MAIL_USERNAME --repo <you>/<repo> --body "you@gmail.com"
gh secret   set MAIL_PASSWORD --repo <you>/<repo> --body "<16-char app password>"
gh variable set EMAIL_TO      --repo <you>/<repo> --body "you@gmail.com"
```

Or add the same three in **Settings → Secrets and variables → Actions**. The next
run picks them up automatically — no code change.

---

## Cost

One run per weekday: roughly 10–20 web searches plus the writing pass. Expect **$10–20/month**
on the Anthropic API at current pricing. GitHub Actions minutes are free for public repos.

To run less often, edit the cron in `.github/workflows/daily.yml`.

---

## Tuning it

Everything you'd want to change lives in **`config.json`**:

- `priority_firms` — the firms that get the ◆ flag. Currently MSIP, Stonepeak, Greenbriar.
- `watchlist_firms` — the firms the research pass is told to sweep each morning
- `tracked_situations` — the situation watchlist. Each has a `key`, a display `label`, a `note`
  and an `aliases` list; anything matching an alias is auto-tagged to that situation.
  **Add a new situation by adding an entry here** — nothing else needs to change.
- `firm_aliases` — normalises name variants so "Morgan Stanley Infrastructure Partners" and
  "MSIP" are one entity

The editorial voice and section definitions live in `build_system()` in `scripts/generate.py`.
That's the prompt — change it to change how items are written.

### Adding a situation

```json
{
  "key": "new_situation",
  "label": "Display Name",
  "note": "One line of context",
  "sector": "Power & Renewables",
  "aliases": ["Name", "Alternate Name", "Subsidiary"]
}
```

Aliases are matched on word boundaries against headline, deal facts, companies and firms.

---

## Layout

```
CONTEXT.md                    who this is for and the accuracy rules — read this first
index.html                    the whole site — one file, no build step, no dependencies
config.json                   watchlists, aliases, taxonomy, reader profile
data/index.json               entity rollups + a lightweight item index for filtering
data/items/YYYY-MM.json       full items, one shard per month (lazy-loaded)
archive/README.md             plain-text index of everything
archive/YYYY-MM.md            every item that month, readable and greppable
archive/situations/KEY.md     the full run of one tracked situation
archive/firms/NAME.md         everything on one firm
scripts/lib.py                normalisation, dedupe, storyline threading, archive writing
scripts/generate.py           the daily research pass (run with --selftest to check wiring)
scripts/export_markdown.py    regenerates archive/ from data/
scripts/email_summary.py      builds the morning digest
.github/workflows/daily.yml   the cron
```

## The markdown archive

`data/` is what the website reads. `archive/` is the same content as plain markdown,
rewritten on every run and committed to git. It exists so the history is readable
without the site, greppable from anywhere, diffable in git, and usable as context by
a future AI session. Point one at `CONTEXT.md` and then `archive/README.md` and it
has everything it needs.

## Debugging a failed run

```bash
python scripts/generate.py --selftest     # checks config, archive and env, no API call
gh run view --log-failed --repo <you>/<repo>
```

The workflow runs `--selftest` before anything else, so a config mistake fails fast
and loudly instead of halfway through.

## Running locally

```bash
python3 -m http.server 8000     # then open http://localhost:8000
```

Opening `index.html` directly with `file://` will not work — the browser blocks the
`fetch` calls. Serve the folder.

To test a generation run:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/generate.py && python scripts/email_summary.py
```

---

## How dedupe works

Three layers, so the same story doesn't clutter the timeline:

1. **URL match** — canonicalised (protocol, `www.`, tracking params and trailing slash stripped)
2. **Headline similarity** — Jaccard over content words; ≥0.55 within a 5-day span is a duplicate,
   and the richer version wins
3. **Prompt-level** — the last three weeks of headlines are passed to the model each morning with
   instructions not to re-report them unless something actually changed

Storyline threading is deliberately looser (≥0.32 similarity plus a shared company or situation),
because there the goal is to *link* related items, not collapse them.

## A note on the archive

Items are only written if they carry at least one real source URL. Dates are announcement
dates, not the date the item was filed. The commentary is generated, so treat it as a research
starting point rather than a verified fact — check the source before anything goes in a deck.
