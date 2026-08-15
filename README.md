# Yahoo Fantasy Draft Ranker

A personal command-line tool that produces a ranked pre-draft player list for a
single Yahoo fantasy football league. The list is entered by hand into Yahoo's
pre-draft ranking page so that autopick drafts a competent team without the
owner attending the draft.

Single user, single league, not distributed.

## How it works

1. Read the league's own configuration from the Yahoo Fantasy Sports API:
   scoring rules, roster slots, number of teams, draft type and time.
2. Build a rank-to-points curve from the 2023-2025 NFL seasons using public
   play-by-play statistics, scored under this league's actual rules.
3. Map each player's current expert consensus rank onto that curve to get
   projected points.
4. Apply value-based drafting (points above positional replacement level) and
   group the result into tiers.
5. Emit a name-ordered list for Yahoo's pre-draft ranking page.

The reasoning behind steps 2 through 5, including the alternatives that were
rejected, is recorded in [docs/DECISIONS.md](docs/DECISIONS.md).

## Yahoo API usage

Read only. The tool never writes to Yahoo. Rankings are entered manually
through the Yahoo website.

Endpoints used:

- League settings, for scoring rules and roster composition
- League teams and rosters, for the owner's own league
- Player metadata, to match Yahoo player IDs against public statistics sources

## Data sources

- Yahoo Fantasy Sports API: league configuration only
- [nflreadpy](https://github.com/nflverse/nflreadpy): public NFL player
  statistics and expert consensus rankings

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -r requirements.txt
cp .env.example .env        # then fill in the Yahoo app credentials
python yahoo_auth.py        # prints the authorization URL
python yahoo_auth.py <code> # redeems the authorization code
python probe_league.py      # reads and prints the league settings
```

Credentials live in `.env`, which is gitignored and never committed.

## Status

See [docs/STATUS.md](docs/STATUS.md).
