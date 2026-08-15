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
- `[VERIFIED: git log, this session]` Seven commits on `master`, in sync with `origin/master`.
- `[VERIFIED: WebFetch of developer.yahoo.com/oauth2/guide/flows_authcode/]`
  `yahoo_auth.py` matches the documented authorization-code flow: correct
  endpoints, HTTP Basic client authentication, `redirect_uri` present on both
  the code exchange and the refresh grant.
- `[ASSUMED: still unobserved]` `probe_league.py` has now been executed against
  Yahoo, but it fails at the first HTTP call (401, scope) and never reaches its
  JSON parsing. Its traversal of the settings and leagues shapes is still
  written from the API guide's documented shapes, not from an observed
  response. Expect to fix a traversal detail whenever a scoped token exists.
- `[VERIFIED: WebFetch, 2026-08-15]` **Fantasy Sports is no longer a self-serve
  app permission.** It is not on the app-creation form at all; the form offers
  only OpenID Connect and TW Auction. `developer.yahoo.com/fantasysports/guide/`
  now 308-redirects to `sports.yahoo.com/developer`, which gates access behind
  an application reviewed by the Yahoo Fantasy Sports team. This supersedes the
  prior reading that TW Auction was selected by mistake from an adjacent
  checkbox: Fantasy Sports was never on that list to select.
- `[VERIFIED: WebFetch of sports.yahoo.com/developer/access/, 2026-08-15]`
  The API is **read-only**. "Write access is not available at this time."
  Personal or single-league use is explicitly named as an eligible use case.
  No approval turnaround time is published.
- `[VERIFIED: user-stated, 2026-08-15]` Access application submitted, describing
  personal single-league read-only use. Awaiting review. No response yet.
- `[VERIFIED: live probe with a real token, 2026-08-15]` A token from an app
  without the Fantasy Sports permission **cannot** reach fantasy endpoints.
  Authorization succeeded and a valid 1012-character access token was issued,
  but every endpoint returns `401` with
  `WWW-Authenticate: OAuth oauth_problem="additional_authorization_required"`.
  Tested `game/nfl`, `users;use_login=1/games`,
  `users;use_login=1/games;game_keys=nfl/leagues`, and
  `league/nfl.l.<id>/settings`. The failure is identical on the trivial game
  endpoint, which rules out a bad league id or a wrong account: enforcement is
  at the app-permission level. Approval is the only route to the API.
- `[VERIFIED: owner transcription of the league Settings page, 2026-08-15]`
  League configuration is recorded in `league.py` and verified to parse.
  **12 teams, head-to-head, half PPR** (0.5 per reception), fractional and
  negative points both enabled. Starters per team: QB 1, RB 2, WR 2, TE 1,
  **W/R/T flex 2**, K 1, DEF 1, so 10 starters, 5 bench, 1 IR, and 180 players
  rostered leaguewide. Draft is a **live snake** on **2026-09-05 16:00 CDT**.
  Departures from Yahoo defaults that move whole position groups: passing TD 5
  (default 4), interception -2 (default -1), every missed FG -1 (default 0),
  missed PAT -1 (default 0), DST sack 1.5 (default 1).
- `[VERIFIED: git ls-files + full-history grep, 2026-08-15]` Repository is safe
  to publish: `.env` was never committed, only `.env.example` with empty secret
  fields; no secret-shaped strings and no personal data anywhere in history.
- `[VERIFIED: gh repo view + git status -sb, 2026-08-15]` Published public at
  `github.com/danny2kx/yahoo-fantasy-draft-ranker`. `master` tracks
  `origin/master` and is in sync. This URL was cited on the Yahoo access
  application, so it must keep resolving.
- `[VERIFIED: token exchange, 2026-08-15]` `yahoo_auth.py` works end to end
  against the live endpoints: the authorization URL is accepted, the code
  redeems, and `tokens/yahoo.json` is written. Only the fantasy scope is
  missing. Note the venv is required: plain `python` has no `dotenv`, so run
  `./.venv/Scripts/python.exe`.

## Blocked

Nothing. The Yahoo API remains gated behind an approval queue, but it was only
ever a convenience for reading settings that are visible on the league's own
settings page, and the deliverable (D-002) is entered into Yahoo's pre-rank page
by hand regardless because write access does not exist. Settings are now
transcribed (see `league.py`), so every downstream step can run.

## Next actions

1. `[Sonnet -- pattern build against a specified method]` Build the
   rank-to-points curve: compute 2023-2025 season fantasy points per player
   under the league's actual scoring, rank within position per season, average
   across seasons.
2. `[Sonnet -- pattern build against a specified method]` Apply VBD per D-001,
   assign tiers from gaps in the VBD curve, emit a name-ordered list for
   Yahoo's pre-draft ranking page plus a tiered HTML cheat sheet.
3. `[Sonnet -- opportunistic, not on the critical path]` If Yahoo approves the
   application, put the credentials in `.env`, run `yahoo_auth.py`, then
   `probe_league.py`. Fix its JSON traversal against the real response and
   check the observed settings against the transcribed ones.

## Open questions

```
Q-001: ANSWERED 2026-08-15. 12 teams, head-to-head, half PPR (0.5 per
  reception). Starters QB 1, RB 2, WR 2, TE 1, W/R/T 2, K 1, DEF 1; bench
  5; IR 1. Full scoring table in league.py.
```

```
Q-002: ANSWERED 2026-08-15. Live snake draft, 2026-09-05 16:00 CDT, with
  a 1:15 pick clock. That is 21 days out, so there is time for the tiered
  cheat sheet as well as the bare ranked list.
```

```
Q-003: ANSWERED 2026-08-15. Read only. sports.yahoo.com/developer/access/
  states "Access to the Yahoo Fantasy Sports API is read-only by default"
  and "Write access is not available at this time." Read/Write can be
  requested in the application notes but is not offered as a scope. This
  rules out later in-season lineup automation through the API.
```

```
Q-005: How should the two W/R/T flex slots be allocated when setting the
  VBD replacement level? 24 leaguewide flex slots split among RB, WR and TE
  changes every positional replacement rank, and therefore the whole board.
Blocker: a method choice, not missing data.
Resolution: owner picks the allocation rule.
```

```
Q-004: ANSWERED 2026-08-15. Yes, public GitHub. Decided because the Yahoo
  access application requires a valid URL describing the product, and the
  repository was verified clean of secrets and personal data. Done:
  github.com/danny2kx/yahoo-fantasy-draft-ranker, master in sync.
```
