# STATUS

Snapshot of the latest session. Overwritten each handoff.

**As of:** 2026-08-15 (Session 3)

## Goal

Produce one ranked draft list good enough to load into Yahoo's pre-draft
rankings, so the snake draft runs itself without the owner attending.

## Current state

- `[VERIFIED: build_rankings.py run + read back from out/yahoo_prerank.txt,
  this session]` Replacement level is the last player worth one of the league's
  156 skill roster slots, per **D-005**, which supersedes D-004 on this point.
  Settled depths QB 12, TE 24, RB 49, WR 70; levels QB 296.6, TE 88.7, RB 85.8,
  WR 81.7. Board holds **zero quarterbacks in the top 12**. First QB Drake Maye
  at line 19, first TE Trey McBride at 21, first kicker or defence at 152.
  `out/yahoo_prerank.txt` is 216 names, all unique, no blanks.
- `[VERIFIED: build_rankings.py run, this session]` The session-2 handoff
  prescribed moving the QB replacement rank from 12 to 18. **It was applied,
  failed, and was reverted.** It moved the QB level from 296.6 to 244.2 and
  pushed the top QB from 7th overall to 3rd, with four QBs inside the top 12
  against a target of zero. Cause recorded as **L-007**.
- `[VERIFIED: build_rankings.py run + out/cheatsheet.html inspected, this
  session]` Every position is now tiered separately as well as overall.
  `assign_tiers()` runs the same gap-based cut twice and carries `pos_tier` and
  `pos_slot`. The cheat sheet gained a Pos tier column and a **By position**
  section (24 positional tier blocks, each with its value range and bye weeks).
  `out/yahoo_prerank.txt` is unchanged, since Yahoo takes names only.
- `[VERIFIED: build_rankings.py run, this session]` Positional tiers: RB T1
  McCaffrey alone, T2 Bijan/Taylor/Jeanty, T3 Gibbs/Chase Brown/Cook, T4
  Barkley. WR has **no groups at the top** -- WR1 through WR7 are each alone in
  a tier (Lamb 247, Jefferson 213, Chase 184, St. Brown 164, Nacua 158,
  Smith-Njigba 146, London 137); the first real group is T8. QB T1 Maye alone,
  T2 Caleb Williams/Allen/Jackson. TE T1 McBride alone, T2 Warren/Bowers/
  Loveland/Kraft.
- `[VERIFIED: owner transcription of the league Settings page, 2026-08-15]`
  League configuration is in `league.py`. **12 teams, head-to-head, half PPR**
  (0.5 per reception), fractional and negative points enabled. Starters QB 1,
  RB 2, WR 2, TE 1, **W/R/T flex 2**, K 1, DEF 1; bench 5; IR 1; 180 players
  rostered leaguewide. Draft is a **live snake on 2026-09-05 16:00 CDT**.
  Departures from Yahoo defaults: passing TD 5 (default 4), interception -2
  (default -1), every missed FG -1 (default 0), missed PAT -1 (default 0),
  DST sack 1.5 (default 1).
- `[VERIFIED: probe against 2025 season totals, session 2]` `scoring.py`
  computes correct half-PPR points. 2025 leaders: Stafford 396.4, McCaffrey
  365.6, Nacua 310.5, McBride 252.9. Postseason is excluded.
- `[VERIFIED: user-stated, this session]` Owner drafts from **slot 4 of 12**.
  Snake picks are therefore overall 4, 21, 28, 45 in the first four rounds.
- `[VERIFIED: simulation over the settled board, this session]` Taken purely in
  board order with the room drafting on consensus rank, slot 4 yields
  McCaffrey, Barkley, Henry, Javonte Williams -- **four running backs**, leaving
  both WR slots empty. Yahoo autopick applies positional need on top of the
  list, so the literal four-back result will not occur, but the RB lean is real.
  Cheapest break in the run is round 4: Davante Adams costs 27.7 VBD against
  Javonte Williams. `[INFERRED: consensus rank used as an ADP stand-in]` No ADP
  source is available, so the simulated room order is approximate.
- `[VERIFIED: build_rankings.py run, this session]` Nine rookies now reach the
  board (was four), seven of them round-1: Jeremiyah Love (RB ARI p3, tier 14),
  Jadarian Price (RB SEA p32, t17), Carnell Tate (WR TEN p4, t17), Jordyn Tyson
  (WR NO p8, t18), Makai Lemon (WR PHI p20, t18), KC Concepcion (WR CLE p24,
  t19), Omar Cooper Jr. (WR NYJ p30, t19), plus round-2 Denzel Boston (WR CLE
  p39) and De'Zhaun Stribling (WR SF p33).
- `[VERIFIED: id_bridge probe, session 2]` The consensus list joins to gsis ids
  for 180/180 of the top-180 skill players; 168 hit both `load_player_stats` and
  `load_ff_opportunity`. The 12 misses are rookies with no NFL snaps. Yahoo ids
  resolve for only 144/180, which does not matter because the list is entered by
  player name.
- `[VERIFIED: WebFetch + live probe, 2026-08-15]` The Yahoo Fantasy Sports API
  is gated behind an approval queue and is **read-only**. A token from an app
  without the Fantasy Sports permission returns `401` with
  `oauth_problem="additional_authorization_required"` on every endpoint. Access
  application submitted; no response yet. `yahoo_auth.py` works end to end.
  Run scripts with `./.venv/Scripts/python.exe`; plain `python` lacks `dotenv`.
- `[VERIFIED: gh repo view + git status -sb, 2026-08-15]` Published public at
  `github.com/danny2kx/yahoo-fantasy-draft-ranker`, `master` in sync with
  `origin/master`. This URL was cited on the Yahoo access application, so it
  must keep resolving.

## Parked

- `references/FF25.xlsx` -- untracked, 142 KB, owner's own file. **Verdict:
  PARK, keep untracked.** `[VERIFIED: stdlib zipfile/XML read of the workbook,
  this session]` It is the *2025* draft (board top is Chase, Barkley, Tyreek;
  the stat column is `FPPG_2024`), across 7 sheets of which 3 are near-duplicate
  "Copy of Rank" versions that disagree with each other. Defects: Josh Jacobs
  has Position `GB` and Team `RB` (columns swapped), `#N/A` VLOOKUPs in "Copy of
  Rank 1", mojibake names in the `FBG` sheet. No reusable data. Two *concepts*
  in it are genuinely missing from the pipeline and became next action 5:
  `Schedule_Rating` and `Role_Change_Multiplier`. `O_Line_Rank` is not in
  nflreadpy; `Red_Zone_Targets` is already covered by the touchdown-regression
  signal. PII scan clean: 2,100 shared strings, zero manager names, emails or
  league identifiers.

## Blocked

Nothing. The Yahoo API stays gated, but it was only ever a convenience for
reading settings that are now transcribed, and the deliverable is entered into
Yahoo's pre-rank page by hand regardless because write access does not exist.

## Next actions

1. `[Opus+thinking -- cross-system tradeoff with an unbounded interaction]`
   **Fix Q-007.** D-004 caps a signal at 8 positional ranks and treats that as a
   bound on influence. It is not: the curve converts ranks to points
   non-linearly, so the same capped shift is worth ~86 points at the top of a
   position and ~20 in the middle. Two candidate fixes, neither costed: cap in
   points instead of ranks, or apply the shift after the curve lookup rather
   than before. This reopens D-004's method and needs a new D-NNN either way.
   Owner raised it via two concrete cases, both of which must be re-read after
   any fix (see Q-007 for the numbers).
2. `[Sonnet -- judgment against an external source]` Review the round-1 rookies
   against Matt Waldman's Rookie Scouting Portfolio ($21.95, **not purchased**)
   and move them by hand in `out/yahoo_prerank.txt`. The model knows their draft
   capital and landing spot; it cannot evaluate whether they can play, and must
   not pretend to. Jeremiyah Love at line 23 is the only one high enough to cost
   a real pick.
3. `[Owner -- manual: transcribe a list into a web form]` Enter
   `out/yahoo_prerank.txt` into Yahoo's pre-draft rankings page before
   2026-09-05 16:00 CDT. No agent in this project has a browser. Do not re-sort
   the kickers and defences upward; they sit after line 151 deliberately.
4. `[Sonnet -- opportunistic, not on the critical path]` If Yahoo approves the
   API application, put the credentials in `.env`, authorize, and run
   `probe_league.py`. Fix its JSON traversal against the real response and check
   the observed settings against `league.py`.
5. `[Sonnet -- a real gap, cheap to try]` The model has **no strength-of-schedule
   signal**, and no way to say "changed teams, and it is an upgrade" -- the usage
   signal is simply dropped on a team change. Both concepts came from the
   owner's 2025 spreadsheet. Schedule strength is derivable from live data; the
   role-change call is human judgement and probably belongs as a manual override
   column rather than a signal.

## Open questions

```
Q-007: D-004 caps a signal at 8 ranks, but a rank is worth wildly
  different amounts of value depending on where it lands on the points
  curve, so the cap does not bound what a signal can do.
Blocker: fixing it reopens D-004's method. Capping in points instead of
  ranks, or applying the shift after the curve lookup, are both real
  options and neither has been costed.
Evidence, case 1 (owner raised): Jahmyr Gibbs is consensus RB1 (ECR 3,
  base RB rank 1) and lands RB5, 8th on the board. One signal did it --
  18 touchdowns against 10.68 expected, the largest overperformance in
  the RB pool, z -3.81 after inversion, combined signal -0.829, shift -5.
  The RB curve pays 354.1 at rank 1 and 268.5 at rank 5, so a 5-rank
  "capped" move cost him 85.6 points. Christian McCaffrey moved +4 the
  other way on the same signal (3.28 touchdowns BELOW expected) and took
  RB1. The model also holds no injury data, so McCaffrey's history --
  the reason consensus has him 9th -- is invisible to it.
Evidence, case 2: Ja'Marr Chase is consensus WR1 (ECR 2) and lands WR3,
  7th on the board. Justin Jefferson (+8) and CeeDee Lamb (+7) jumped him
  on the same touchdown-regression signal, scoring 6.55 and 4.79 fewer
  touchdowns than expected. That produced 328.6 / 294.4 / 265.5 curve
  points and three separate WR tiers.
Resolution: a new D-NNN choosing one of the two fixes, then re-read both
  cases. Gibbs should be judged against the owner's stated expectation of
  top 3, and Chase against top 4. Not started.
```

```
Q-006: Are the round-1 rookies ranked correctly?
Blocker: the model has draft capital and landing spot but no talent
  evaluation, and the consensus disagrees most on exactly these players
  (Carnell Tate: ECR 65, one analyst has him 45, another 176).
Resolution: Waldman's RSP read, then a manual move. See next action 2.
```

```
Q-005: ANSWERED 2026-08-15 (session 3). Neither option in the question.
  The question assumed the QB baseline was the lever, and it is not: a
  deeper QB baseline raises quarterbacks rather than lowering them
  (L-007). QB stays at rank 12; RB moved to 49 and WR to 70 by counting
  bench slots. See D-005. D-006 then closed the follow-up of pushing
  quarterbacks further down -- owner confirmed set-and-forget, so the
  streaming baseline (free QB = QB9 or QB10, first QB at line 33 or 27)
  and a hard line-number floor were both rejected.
```

```
Q-004: ANSWERED 2026-08-15. Yes, public GitHub. Decided because the Yahoo
  access application requires a valid URL describing the product, and the
  repository was verified clean of secrets and personal data. Done:
  github.com/danny2kx/yahoo-fantasy-draft-ranker, master in sync.
```

```
Q-003: ANSWERED 2026-08-15. Read only. sports.yahoo.com/developer/access/
  states "Access to the Yahoo Fantasy Sports API is read-only by default"
  and "Write access is not available at this time." This rules out later
  in-season lineup automation through the API.
```
