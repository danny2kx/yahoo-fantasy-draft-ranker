# STATUS

Snapshot of the latest session. Overwritten each handoff.

**As of:** 2026-08-15 (Session 4)

## Goal

Produce one ranked draft list good enough to load into Yahoo's pre-draft
rankings, so the snake draft runs itself without the owner attending.

## Current state

- `[VERIFIED: build_rankings.py run + read back from out/yahoo_prerank.txt,
  this session]` **Q-007 is closed by D-007.** The combined signal now adjusts a
  player's projected POINTS, capped at plus or minus 24 (`MAX_POINT_SHIFT`), at
  18 points per unit of signal (`POINTS_PER_SIGNAL`). The consensus rank alone
  decides which point on the curve is read; the signal is applied after that
  lookup, never to the rank feeding it. `MAX_RANK_SHIFT` is gone.
- `[VERIFIED: scratch run holding the old feed anchor, this session]` Both
  owner cases clear their stated bars, and the fix alone did it. **Jahmyr Gibbs
  8th -> 1st** (RB5 -> RB1); his signal is unchanged in direction and is still
  the board's largest downgrade, but at -14.1 points instead of the 85.6 points
  a 5-rank move cost on the RB curve. **Ja'Marr Chase 7th -> 2nd** (WR3 -> WR1);
  he had lost 63.1 points without being adjusted at all, because Lamb (WR5 ->
  WR1, 88.9 points) and Jefferson (WR6 -> WR2, 66.6 points) displaced him down
  the curve. Neither player was hand-edited.
- `[VERIFIED: build_rankings.py run, this session]` **D-008 swapped the base
  consensus** onto `references/FantasyPros_2026_Draft_ALL_Rankings.csv`, the
  owner's own export, joined to the feed on player name plus position purely to
  recover a player id. The join is asserted in code: 150/150 of the export's top
  150 resolved, 326/327 overall, zero position disagreements, no duplication.
  The swap moved nobody in the top 12; its largest effects are Brock Bowers 54th
  -> 24th, Stribling 127th -> 87th, Brooks 99th -> 63rd, Daniels 79th -> 47th,
  McBride 21st -> 43rd, Kelce 84th -> 104th.
- `[VERIFIED: build_rankings.py run, this session]` Board top 8: Gibbs, Chase,
  McCaffrey, Bijan, Taylor, Smith-Njigba, Cook, Jeanty. Replacement level method
  is unchanged from **D-005**; settled depths moved slightly to QB 12, TE 24,
  RB 51, WR 69, levels QB 291.1, TE 90.0, RB 79.0, WR 83.5. **Zero quarterbacks
  in the top 24** (first is Josh Allen at line 25), first TE Brock Bowers at 24,
  so D-005 and D-006 both still hold. `out/yahoo_prerank.txt` is 189 names, all
  unique, no blanks — shorter than the previous 216 because the export lists 327
  players against the feed's 505. That still covers the 180 the league drafts.
- `[VERIFIED: league.py read back, this session]` `league.py` now derives
  `DRAFT_SLOT = 4`, `ROUNDS = 15` and `OWNER_PICKS`, giving overall picks 4, 21,
  28, 45, 52, 69. Matches the hand-computed values recorded in session 3.
- `[VERIFIED: owner transcription of the league Settings page, 2026-08-15]`
  League configuration is in `league.py`. **12 teams, head-to-head, half PPR**
  (0.5 per reception), fractional and negative points enabled. Starters QB 1,
  RB 2, WR 2, TE 1, **W/R/T flex 2**, K 1, DEF 1; bench 5; IR 1. Draft is a
  **live snake on 2026-09-05 16:00 CDT**. Departures from Yahoo defaults:
  passing TD 5, interception -2, missed FG -1, missed PAT -1, DST sack 1.5.
- `[VERIFIED: probe against 2025 season totals, session 2]` `scoring.py`
  computes correct half-PPR points. Postseason is excluded.
- `[VERIFIED: WebFetch + live probe, 2026-08-15]` The Yahoo Fantasy Sports API
  is gated behind an approval queue and is **read-only**. Access application
  submitted; no response yet. Run scripts with `./.venv/Scripts/python.exe`;
  plain `python` lacks `dotenv`.
- `[VERIFIED: git status -sb, this session]` Published public at
  `github.com/danny2kx/yahoo-fantasy-draft-ranker`. This URL was cited on the
  Yahoo access application, so it must keep resolving.

## Research completed this session, not yet built

`[VERIFIED: scratch panels over nfl.load_pbp + load_player_stats 2019-2025,
this session]` Six candidate criteria were tested predictively — season N's
metric against season N+1's points, after removing what season N's points
already explain. Method and its rationale are **L-008**. Rejections are
**D-009**. Adoptions are **not decided** and are carried as Q-009.

| Candidate | Same-season | ADDED | Verdict |
|---|---|---|---|
| Age, RB (n=260) | -0.045 | **-0.228** | build — strongest tested |
| Age, WR/TE (n=676) | +0.045 | **-0.215** | build |
| RB team offence quality | see below | — | build |
| Air yards share, WR | +0.749 | +0.103 | build — beats target share |
| Snap share | +0.588 | +0.080 to +0.096 | maybe |
| WR running-QB penalty | — | — | small weight |
| Red zone / goal line, all forms | up to +0.724 | -0.004 to -0.128 | **rejected, D-009** |
| WR target competition | -0.151 | -0.027 | **rejected, D-009** |

Age bands, change from this season to next: RB `<=23` +1.3, `24-25` -15.4,
`26-27` -25.9, `28+` -40.7 (monotonic, every band). WR/TE `<=24` +1.0, `25-27`
-15.3, `28-30` -24.9, `31+` -33.3.

RB team quality, 118 lead-back seasons, like-for-like roles: good offences
240.8 points, bad 177.3, a **63-point gap**, with bad-offence backs holding the
HIGHER carry share (0.565 vs 0.548) and roughly half the expected touchdowns
(6.62 vs 12.95). See **L-009**.

`[VERIFIED: build_rankings.py:310 read, this session]` Two defects follow from
this and are **not yet fixed**: `pass_epa` is set to zero for running backs, so
they carry no absolute team term at all, and because the zeroed weight is not
renormalised **every running back's combined signal is damped 15%** against
every receiver's on identical evidence.

`[VERIFIED: board join to load_ff_playerids birthdates, this session]` The
players the age evidence says to fade are the ones the model currently
promotes: McCaffrey 30 (+10.5, board 3), Barkley 29 (+11.9, board 13), Henry 32
(+8.7, board 17). Same pattern as Jeanty, 23, on the league's worst offence
(-2.46 z) receiving +4.2.

## Parked

- `references/` stays **untracked** and holds the owner's own files: `FF25.xlsx`
  (2025 draft, no reusable data, PII scan clean — see session 3) and the
  FantasyPros export D-008 now anchors on. The repository is PUBLIC and the
  export is a redistributed third-party ranking, so it must never be staged.
  **A `.gitignore` entry for `references/` was proposed and not applied**, so
  the protection today is only that nothing runs a directory-wide `git add`.
- `[VERIFIED: user asked directly, this session]` An independent review of the
  D-007/D-008 diff was offered before commit — the change rewrites core ranking
  control flow — and the owner proceeded to handoff without requesting one. The
  code is committed unreviewed by a second party. Recorded so the next session
  inherits a decision rather than an omission.

## Blocked

Nothing. The Yahoo API stays gated, but the deliverable is entered by hand
regardless because write access does not exist.

## Next actions

1. `[Owner — one lookup]` **Answer Q-008.** Confirm which scoring the
   FantasyPros export was downloaded under. The entire base order rests on it
   and the scoring is inferred, not verified. It also decides the fate of the
   `reception_dependence` signal, which is currently either double-counting or
   inverted.
2. `[Opus+thinking — cross-system tradeoff, reweights a decided method]`
   **Build the Q-009 signals.** Age curve for RB and WR/TE, RB team-offence
   quality, air yards share for receivers, and the 15% damping fix. This
   reweights D-004's signal budget, so it needs a new D-NNN and the weights must
   be argued, not assumed. Do NOT add anything D-009 rejected.
3. `[Sonnet — judgment against an external source]` Review the round-1 rookies
   against Matt Waldman's Rookie Scouting Portfolio ($21.95, **not purchased**)
   and move them by hand. 12 rookies now reach the board; Jeremiyah Love at 18
   is the only one high enough to cost a real pick.
4. `[Owner — manual: transcribe a list into a web form]` Enter
   `out/yahoo_prerank.txt` into Yahoo's pre-draft rankings page before
   2026-09-05 16:00 CDT. Do not re-sort the kickers and defences upward.
5. `[Sonnet — cheap, data already in hand]` Wire `SOS SEASON` and
   `ECR VS. ADP` from the D-008 export. Both are parsed and discarded today.
   `ECR VS. ADP` removes the `[INFERRED]` caveat on the slot-4 draft
   simulation, which used consensus rank as an ADP stand-in. **Confirm the sign
   convention before using it.**
6. `[Sonnet — a stated blind spot with a source]` `nfl.load_injuries()` exists
   and is unexplored. The model holds no injury data, which is the live caveat
   on McCaffrey at board 3 and on any age signal built in action 2.

## Open questions

```
Q-009: Which of the four surviving criteria get built, and at what
  weights? Age (RB -0.228, WR -0.215), RB team-offence quality (63-point
  gap), air yards share (+0.103), snap share (+0.080 to +0.096).
Blocker: D-004's weights sum to one and are assigned, not fitted, so
  adding four signals means re-cutting a fixed budget across nine terms.
  No held-out season exists to fit against without building a backtest
  this project does not need. Two existing terms are also in doubt:
  carry share adds -0.012 and reception_dependence is blocked on Q-008.
Evidence: the table and age bands under "Research completed" above.
  Controls are last season's realised points as a proxy for the
  consensus, so every ADDED figure is an UPPER bound.
Resolution: a new D-NNN naming the weights and the reasoning, then a
  rerun with Gibbs, Chase, McCaffrey, Barkley and Henry re-read against
  the board. Not started.
```

```
Q-008: Which scoring was the owner's FantasyPros export downloaded
  under? The file records no scoring anywhere in it, and the whole base
  order now rests on it (D-008).
Blocker: only the owner can see the download settings, or re-export
  under a named scoring.
Evidence: the export ranks Gibbs 1 / Chase 3 where the feed's known
  full-PPR page ranks Chase 1.67 / Gibbs 3.01, so receptions are worth
  less than full PPR in it. That rules out full PPR and cannot separate
  half PPR from standard.
Resolution: if half PPR, D-008 stands as written. If standard, average
  the export with the feed's PPR page instead — the midpoint of standard
  and full PPR is half PPR — which D-008 already costed and parked.
Second consequence: the reception_dependence signal (D-004, weight 0.10)
  exists ONLY to correct a full-PPR anchor, and D-008 removed that
  anchor. If the export is half PPR the signal now double-counts a
  correction already in the base order and should be dropped; if standard
  it points the wrong way and should be inverted. It cannot stay as it is
  under either answer. It currently penalises the highest-reception
  receivers hardest: Nacua -2.85, Chase -2.69, St. Brown -2.10,
  Smith-Njigba -2.05. Not started.
```

```
Q-006: Are the round-1 rookies ranked correctly?
Blocker: the model has draft capital and landing spot but no talent
  evaluation, and the consensus disagrees most on exactly these players
  (Carnell Tate: ECR 65, one analyst has him 45, another 176).
Resolution: Waldman's RSP read, then a manual move. See next action 3.
```

```
Q-007: ANSWERED 2026-08-15 (session 4). Both proposed fixes turned out
  to be the same fix, recorded as D-007. Gibbs 8th -> 1st, Chase 7th ->
  2nd, isolated from D-008 by a scratch run holding the old anchor.
```

```
Q-005: ANSWERED 2026-08-15 (session 3). Neither option in the question.
  A deeper QB baseline raises quarterbacks rather than lowering them
  (L-007). QB stays at rank 12; RB and WR moved by counting bench slots.
  See D-005. D-006 closed the follow-up.
```

```
Q-004: ANSWERED 2026-08-15. Yes, public GitHub. The Yahoo access
  application requires a valid URL, and the repository was verified clean
  of secrets and personal data.
```

```
Q-003: ANSWERED 2026-08-15. Read only. Write access is not available,
  which rules out later in-season lineup automation through the API.
```
