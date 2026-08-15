# STATUS

Snapshot of the latest session. Overwritten each handoff.

**As of:** 2026-08-15 (Session 1)

## Goal

Produce one ranked draft list good enough to load into Yahoo's pre-draft
rankings, so the snake draft runs itself without the owner attending.

## Current state

- `[VERIFIED: pip install + import test, this session]` Dependencies install
  and import on Python 3.14.1 in `.venv/`: nflreadpy 0.1.5, polars 1.43.2,
  yahoo_fantasy_api 2.12.3, yahoo-oauth 2.1.1, python-dotenv, requests.
- `[VERIFIED: probe run, this session]` `nflreadpy.load_ff_rankings()` returns
  5849 rows scraped 2026-08-14; the `redraft-overall` slice is 505 players with
  ECR, standard deviation, best/worst, and bye week.
- `[VERIFIED: probe run, this session]` `load_player_stats(2023-2025)` returns
  57,048 rows carrying every raw component needed to compute fantasy points
  under arbitrary league scoring, plus `target_share` and `air_yards_share`.
- `[VERIFIED: probe run, this session]` Joining rankings to `load_ff_playerids()`
  on `fantasypros_id` resolves a Yahoo ID for 133/172 (77%) of the top-180 ECR.
  Misses are 2025 rookies and all DST entries.
- `[VERIFIED: git log, 7b1c60f]` Three commits on `master`. Working tree clean.
- `[VERIFIED: WebFetch of developer.yahoo.com/oauth2/guide/flows_authcode/]`
  `yahoo_auth.py` matches the documented authorization-code flow: correct
  endpoints, HTTP Basic client authentication, `redirect_uri` present on both
  the code exchange and the refresh grant.
- `[ASSUMED: never executed -- requires user credentials]` `probe_league.py`
  parses but has never run against Yahoo. Its JSON traversal of the settings
  and leagues endpoints is written from the API guide's documented shapes, not
  from an observed response. Expect to fix a traversal detail on first run.
- `[VERIFIED: user-stated, this session]` The Yahoo developer app currently
  holds the **TW Auction** permission (Yahoo Taiwan's e-commerce marketplace),
  not Fantasy Sports. No fantasy data is reachable until this is corrected.
  This is the sole blocker.
- `[VERIFIED: user-stated, this session]` The league is a **snake** draft.
- `[VERIFIED: git remote -v]` Repository has **no remote**. All three commits
  exist only on this machine.

## Blocked

Everything downstream of league settings. Scoring rules, roster slots, and
draft date all come from `probe_league.py`, which needs a working token.

## Next actions

1. `[Haiku -- mechanical: form fill, no judgment]` Re-create or edit the Yahoo
   developer app at https://developer.yahoo.com/apps/create/ with:
   Application Type `Installed Application`; Redirect URI
   `https://localhost:8077`; API Permissions **Fantasy Sports** (NOT TW
   Auction). Take Read/Write if offered, else Read. Put the new Client ID and
   Secret in `.env`.
2. `[Haiku -- mechanical: run a script, paste output]` Run
   `python yahoo_auth.py` to print the authorization URL, approve it while
   signed into the Yahoo account that owns the league, then
   `python yahoo_auth.py <code>` to redeem.
3. `[Sonnet -- debug against a documented response shape]` Run
   `python probe_league.py`. Fix the JSON traversal against the real response.
   Record the observed scoring type, roster slots, draft type and draft time.
4. `[Sonnet -- pattern build against a specified method]` Build the rank-to-points
   curve: compute 2023-2025 season fantasy points per player under the league's
   actual scoring, rank within position per season, average across seasons.
5. `[Sonnet -- pattern build against a specified method]` Apply VBD per D-001,
   assign tiers from gaps in the VBD curve, emit a name-ordered list for
   Yahoo's pre-draft ranking page plus a tiered HTML cheat sheet.

## Open questions

```
Q-001: What is the league's scoring type and roster composition?
Blocker: probe_league.py cannot run until the Yahoo app scope is fixed.
Resolution: probe output naming points-per-reception and the roster slot
  counts. Until then VBD cannot be computed correctly, because the
  replacement level depends on league size times starters per position.
```

```
Q-002: When is the draft?
Blocker: same as Q-001; settings.draft_time is unread.
Resolution: probe output. Decides whether there is time for the tiered
  cheat sheet or only the bare ranked list.
```

```
Q-003: Does Yahoo still offer Read/Write scope for Fantasy Sports, or
  Read only?
Blocker: the option list is only visible on the app-creation form.
Resolution: user reports what the Fantasy Sports accordion offers when
  re-creating the app. Read alone is sufficient for all draft work; the
  answer only constrains later in-season lineup automation.
```

```
Q-004: Should this repository get a git remote?
Blocker: creating one publishes the code; requires an explicit decision.
Resolution: user says yes (and names the host) or no. Until then all work
  exists on one machine with no backup.
```
