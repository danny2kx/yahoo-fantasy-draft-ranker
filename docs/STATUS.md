# STATUS

Snapshot of the latest session. Overwritten each handoff.

**As of:** 2026-08-15 (Session 2)

## Goal

Produce one ranked draft list good enough to load into Yahoo's pre-draft
rankings, so the snake draft runs itself without the owner attending.

## Current state

- `[VERIFIED: build_rankings.py run, this session]` The full pipeline runs end
  to end and writes both deliverables: `out/yahoo_prerank.txt` (157 skill
  players in draft order, then every kicker and defence appended last) and
  `out/cheatsheet.html` (the same board in 12 tiers with a notes column).
  `out/` is gitignored, so the outputs are regenerated rather than committed.
- `[VERIFIED: probe against 2025 season totals, this session]` `scoring.py`
  computes correct half-PPR points. 2025 leaders: Stafford 396.4, McCaffrey
  365.6, Nacua 310.5, McBride 252.9. Postseason is excluded.
- `[VERIFIED: owner transcription of the league Settings page, 2026-08-15]`
  League configuration is in `league.py`. **12 teams, head-to-head, half PPR**
  (0.5 per reception), fractional and negative points enabled. Starters QB 1,
  RB 2, WR 2, TE 1, **W/R/T flex 2**, K 1, DEF 1; bench 5; IR 1; 180 players
  rostered leaguewide. Draft is a **live snake on 2026-09-05 16:00 CDT**.
  Departures from Yahoo defaults: passing TD 5 (default 4), interception -2
  (default -1), every missed FG -1 (default 0), missed PAT -1 (default 0),
  DST sack 1.5 (default 1).
- `[VERIFIED: build_rankings.py output, this session]` Replacement levels with
  the flex allocated by projected points: QB 296.6, RB 135.9, WR 134.8,
  TE 120.8.
- `[VERIFIED: build_rankings.py output, this session]` The bounded signals move
  players as designed. Largest upgrades: Justin Jefferson +8 (top-3 target
  share, 2 TDs on 8.6 expected), CeeDee Lamb +7, Drake Maye +7. Largest
  downgrade: Jahmyr Gibbs -5 (18 TDs on 10.7 expected). 15 players moved 4+
  ranks; the cap is 8.
- `[VERIFIED: build_rankings.py output, this session]` Four round-1 rookies
  reached the board and are flagged for manual review: Jeremiyah Love (ARI,
  p3), Carnell Tate (TEN, p4), Jordyn Tyson (NO, p8), Jadarian Price (SEA,
  p32). All land in tier 12.
- `[VERIFIED: id_bridge probe, this session]` The consensus list joins to gsis
  ids for 180/180 of the top-180 skill players; 168 of those hit both
  `load_player_stats` and `load_ff_opportunity`. The 12 misses are rookies with
  no NFL snaps, which is correct. Yahoo ids resolve for only 144/180, which
  does not matter because the list is entered by player name.
- `[VERIFIED: WebFetch + live probe, 2026-08-15]` The Yahoo Fantasy Sports API
  is gated behind an approval queue and is **read-only**. A token from an app
  without the Fantasy Sports permission returns `401` with
  `oauth_problem="additional_authorization_required"` on every endpoint,
  including the trivial `game/nfl`. Access application submitted; no response
  yet. `yahoo_auth.py` itself works end to end (code redeems, token written).
  Run scripts with `./.venv/Scripts/python.exe`; plain `python` lacks `dotenv`.
- `[VERIFIED: WebSearch, 2026-08-15]` Analyst check. Matt Waldman: Footballguys
  senior staff writer since 2009, Rookie Scouting Portfolio since 2006, one of
  two most-purchased independent draft guides by NFL personnel staff; 2026 RSP
  is $21.95. Jacob Gibbs: CBS Sports data analyst, graded eighth-most accurate
  ranker by FantasyPros, and **already inside the consensus this project uses**.
  Joe Orrico: no track record found either way.
- `[VERIFIED: gh repo view + git status -sb, 2026-08-15]` Published public at
  `github.com/danny2kx/yahoo-fantasy-draft-ranker`, `master` in sync with
  `origin/master`. This URL was cited on the Yahoo access application, so it
  must keep resolving.

## Parked

- `references/FF25.xlsx` — untracked, 142 KB, created 2026-08-15 11:28. Not
  written by this session; owner's own file. Left untracked deliberately. **The
  repository is public**, so before this is ever committed it needs a check for
  real manager names or other personal data.

## Blocked

Nothing. The Yahoo API stays gated, but it was only ever a convenience for
reading settings that are now transcribed, and the deliverable is entered into
Yahoo's pre-rank page by hand regardless because write access does not exist.

## Next actions

1. `[Haiku -- mechanical: one-line constant change, then rerun]` Apply the QB
   replacement-level fix in `build_rankings.py`: in `replacement_levels()`, use
   rank 18 instead of `league.TEAMS * league.STARTERS["QB"]` (12) for QB only.
   Rationale is D-004's tradeoff paragraph: quarterbacks are streamable, so
   QB12 is not the true replacement, and the current board puts four QBs in the
   top 24 with Drake Maye 7th overall. Leave TE at 12; the McBride gap is real.
   Then rerun `./.venv/Scripts/python.exe build_rankings.py` and confirm no QB
   sits inside the top 12 of the board.
2. `[Haiku -- mechanical: fix a print-formatting branch]` In
   `build_rankings.py::report()`, the "Biggest downgrades" list prints upgrades
   when fewer than 8 players moved down. Filter each list by sign before
   printing. Console output only; neither output file is affected.
3. `[Sonnet -- judgment against an external source]` Review the four round-1
   rookies against Matt Waldman's Rookie Scouting Portfolio ($21.95, not yet
   purchased) and move them by hand in `out/yahoo_prerank.txt`. The model knows
   their draft capital and landing spot; it cannot evaluate whether they can
   play, and must not pretend to.
4. `[Haiku -- mechanical: transcribe a list into a web form]` Enter
   `out/yahoo_prerank.txt` into Yahoo's pre-draft rankings page before
   2026-09-05 16:00 CDT.
5. `[Sonnet -- opportunistic, not on the critical path]` If Yahoo approves the
   API application, put the credentials in `.env`, authorize, and run
   `probe_league.py`. Fix its JSON traversal against the real response and
   check the observed settings against `league.py`.

## Open questions

```
Q-005: Should the QB replacement level be rank 12 (last starter) or
  deeper (streaming-adjusted)?
Blocker: a method choice. Both are defensible VBD implementations.
Resolution: next action 1 applies rank 18 and the board is re-read. If no
  QB sits in the top 12 afterwards, the question closes. The
  recommendation was given this session and not yet confirmed by the
  owner.
```

```
Q-006: Are the four round-1 rookies ranked correctly?
Blocker: the model has draft capital and landing spot but no talent
  evaluation, and the consensus disagrees most on exactly these players
  (Carnell Tate: ECR 65, one analyst has him 45, another 176).
Resolution: Waldman's RSP read, then a manual move. See next action 3.
```

```
Q-003: ANSWERED 2026-08-15. Read only. sports.yahoo.com/developer/access/
  states "Access to the Yahoo Fantasy Sports API is read-only by default"
  and "Write access is not available at this time." This rules out later
  in-season lineup automation through the API.
```

```
Q-004: ANSWERED 2026-08-15. Yes, public GitHub. Decided because the Yahoo
  access application requires a valid URL describing the product, and the
  repository was verified clean of secrets and personal data. Done:
  github.com/danny2kx/yahoo-fantasy-draft-ranker, master in sync.
```
