# STATUS

Snapshot of the latest session. Overwritten each handoff.

**As of:** 2026-08-15 (Session 3)

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
- `[VERIFIED: build_rankings.py output + read back from out/yahoo_prerank.txt,
  2026-08-15 session 3]` Replacement level is now the last player worth one of
  the league's 156 skill roster slots, per **D-005**, which supersedes D-004 on
  this point and closes Q-005. Settled depths QB 12, TE 24, RB 49, WR 70; levels
  QB 296.6, TE 88.7, RB 85.8, WR 81.7. The board holds **zero quarterbacks in
  the top 12**; first QB is Drake Maye at 19, first TE Trey McBride at 21, first
  kicker or defence at 152. `out/yahoo_prerank.txt` is 216 names, all unique, no
  blanks. **The prescribed fix in the session-2 handoff (QB rank 18) was wrong
  in direction and was not applied** — see D-005's rejected alternatives and
  L-007. **D-006** then closed the follow-up question of pushing quarterbacks
  further down: the owner confirmed set-and-forget, so the streaming baseline
  (free QB = QB9 or QB10, first QB at line 33 or 27) and a hard line-number
  floor were both rejected. The mechanism for the streaming baseline is a
  one-constant change if his habits ever change.
- `[VERIFIED: build_rankings.py output, this session]` The bounded signals move
  players as designed. Largest upgrades: Justin Jefferson +8 (top-3 target
  share, 2 TDs on 8.6 expected), CeeDee Lamb +7, Drake Maye +7. Largest
  downgrade: Jahmyr Gibbs -5 (18 TDs on 10.7 expected). 15 players moved 4+
  ranks; the cap is 8.
- `[VERIFIED: build_rankings.py output, 2026-08-15 session 3]` The deeper
  baselines lengthened the board, so **nine** rookies now reach it rather than
  four, seven of them round-1: Jeremiyah Love (RB ARI p3, tier 14), Jadarian
  Price (RB SEA p32, tier 17), Carnell Tate (WR TEN p4, tier 17), Jordyn Tyson
  (WR NO p8, tier 18), Makai Lemon (WR PHI p20, tier 18), KC Concepcion (WR CLE
  p24, tier 19), Omar Cooper Jr. (WR NYJ p30, tier 19), plus round-2 Denzel
  Boston (WR CLE p39) and De'Zhaun Stribling (WR SF p33). All still need the
  manual review of Q-006; only Love is high enough on the board to matter much.
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

- `references/FF25.xlsx` — untracked, 142 KB, owner's own file. **Assessed
  2026-08-15 (session 3): keep untracked, no reusable data.** It is the *2025*
  draft (top of board Chase, Barkley, Tyreek; the stat column is `FPPG_2024`),
  across 7 sheets of which 3 are near-duplicate "Copy of Rank" versions that
  disagree with each other. It also carries real defects: Josh Jacobs has
  Position `GB` and Team `RB` (columns swapped), `#N/A` VLOOKUPs in "Copy of
  Rank 1", and mojibake names in the `FBG` sheet. Two *concepts* in it are
  genuinely missing from the pipeline and became next action 4:
  `Schedule_Rating` and `Role_Change_Multiplier`. `O_Line_Rank` is not in
  nflreadpy and `Red_Zone_Targets` is already covered by the touchdown-regression
  signal. PII scan clean: 2,100 shared strings, zero manager names, emails or
  league identifiers — only player names and analysis text.

## Blocked

Nothing. The Yahoo API stays gated, but it was only ever a convenience for
reading settings that are now transcribed, and the deliverable is entered into
Yahoo's pre-rank page by hand regardless because write access does not exist.

## Next actions

Session-2 next actions 1 and 2 are DONE — 1 by a different and opposite fix
(D-005), 2 as written.

1. `[Owner -- judgment against an external source]` Review the round-1 rookies
   against Matt Waldman's Rookie Scouting Portfolio ($21.95, **not purchased**)
   and move them by hand in `out/yahoo_prerank.txt`. The model knows their draft
   capital and landing spot; it cannot evaluate whether they can play, and must
   not pretend to. **Not attempted in session 3** because the source does not
   exist on disk. Jeremiyah Love at line 23 is the only one high enough to cost
   a real pick; the rest sit in tiers 17-19 where an error is cheap.
2. `[Owner -- manual: transcribe a list into a web form]` Enter
   `out/yahoo_prerank.txt` into Yahoo's pre-draft rankings page before
   2026-09-05 16:00 CDT. No agent in this project has a browser, so this is the
   owner's action.
3. `[Sonnet -- opportunistic, not on the critical path]` If Yahoo approves the
   API application, put the credentials in `.env`, authorize, and run
   `probe_league.py`. Fix its JSON traversal against the real response and
   check the observed settings against `league.py`.
4. `[Sonnet -- a real gap, cheap to try]` The model has **no strength-of-schedule
   signal**, and no way to say "changed teams, and it is an upgrade" — the usage
   signal is simply dropped on a team change. Both concepts came out of the
   owner's own 2025 spreadsheet (see Parked). Schedule strength is derivable
   from live data; the role-change call is human judgement and probably belongs
   as a manual override column rather than a signal.

## Open questions

```
Q-005: ANSWERED 2026-08-15 (session 3). Neither. The question assumed the
  QB baseline was the lever, and it is not: a deeper QB baseline raises
  quarterbacks rather than lowering them (L-007). QB stays at rank 12;
  what moved was RB to 49 and WR to 70, by counting bench slots. Owner
  confirmed the method and asked for quarterbacks lower still, which the
  QB pin delivers. See D-005.
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
