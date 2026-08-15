# DECISIONS

Append-only. Published entries are never edited; correct with a new entry
marked "Supersedes D-NNN".

---

## D-001 — Draft projections come from consensus rank mapped onto a historical points curve, not from extrapolated opportunity metrics

Status: Decided (2026-08-15)

Decision: Derive each player's projected fantasy points by taking his current
expert consensus rank (ECR) within his position, then mapping that rank onto a
points curve built from the 2023-2025 seasons — what the player finishing Nth at
that position actually scored, computed under this league's own scoring rules.
Use last season's opportunity metrics (target share, air yards share,
opportunity share) only as a tiebreaker between adjacent players.

Why: Value-based drafting needs projected points, and no free source provides
them — `load_ff_rankings()` supplies ranks only. Building the curve from history
gives points that are automatically correct for this league's scoring, which a
generic published projection set is not.

Tradeoff: The curve encodes the average shape of a position's scoring
distribution, so it cannot express that a specific player is an outlier for his
rank. It inherits whatever bias the consensus has.

Alternative rejected: Project points directly from last season's opportunity
metrics. Rejected because between seasons players change teams, coaches change,
and rookies are drafted on top of incumbents. Pure historical extrapolation
confidently ranks players whose situation no longer exists. The offseason
adjustment is the hard part of preseason projection, it requires knowledge of
roster moves, and consensus rankings already contain it.

Evidence: `load_ff_rankings()` column list contains no points field, verified by
probe this session (columns: fp_page, page_type, ecr_type, player, id, pos, team,
ecr, sd, best, worst, ...). `load_player_stats(seasons=[2023,2024,2025])` returns
57,048 rows with all raw scoring components, verified by probe this session.

References: D-002.

---

## D-002 — Deliverable is a pre-draft ranking list for Yahoo autopick, not a live draft assistant

Status: Decided (2026-08-15)

Decision: The output of this project is a single ranked list of player names,
ordered by value-based drafting and grouped into tiers, loaded into Yahoo's
pre-draft rankings page. A tiered HTML cheat sheet is a secondary output for use
if the owner attends the draft.

Why: The owner's stated constraint is having no time to manage the team. Yahoo's
autopick follows a custom pre-rank order and fills positional needs from it,
which means the entire draft can be resolved by producing one good list in
advance and not attending.

Tradeoff: Autopick cannot react to how the draft actually unfolds — it cannot
notice a positional run or a value falling further than expected. A live drafter
working from the same tiers would do better.

Alternative rejected: A live draft assistant that tracks picks in real time and
recommends the next selection. Rejected as disproportionate to the constraint:
it requires attendance, which is the thing being avoided, and it is far more work
to build for a gain that only materializes if the owner shows up.

Evidence: Yahoo pre-rank and autopick behaviour per
https://help.yahoo.com/kb/pre-rank-players-prepare-autopick-drafts-sln6163.html,
retrieved this session. Snake draft format is user-stated.

References: D-001.

---

## D-003 — League settings are transcribed by the owner, not read from the Yahoo API

Status: Decided (2026-08-15)

Decision: Take the four values the projection method needs — scoring type,
roster slot counts, number of teams, draft date — from the league's own Settings
page, transcribed by the owner into `docs/STATUS.md`. Do not wait for Yahoo API
access. Keep `probe_league.py` and run it later as a cross-check if the access
application is approved.

Why: The Yahoo Fantasy Sports API is no longer self-serve. Access is gated
behind an application reviewed by a human at Yahoo, with no published turnaround
time, and the API is read-only. Under D-002 the deliverable is entered into
Yahoo's pre-rank page by hand anyway, so the API's entire role in this project
was reading four values that are already visible on screen. Blocking the whole
project on a review queue to avoid two minutes of typing is a bad trade.

Tradeoff: Transcription can be wrong, and nothing catches it. An API read is
exact and re-runnable. A custom stat-modifier table is more error-prone to copy
than a named preset like "full PPR", and a wrong point-per-reception value
shifts every receiver in the rankings. Mitigation: record the settings verbatim
rather than as an interpretation, and re-check against `probe_league.py` output
if access is ever granted.

Alternative rejected: Wait for the Yahoo access application, then run
`probe_league.py`. Rejected because the draft date is likely inside the review
window and no turnaround time is published, so this risks the entire deliverable
to gain exactness on four values. Also rejected: scraping the league settings
page with the owner's session cookie, which is more work than reading the page
and violates the terms the access application is governed by.

Evidence: `developer.yahoo.com/fantasysports/guide/` returns a 308 redirect to
`sports.yahoo.com/developer`, which describes an apply-review-approve flow with
no self-serve option. `sports.yahoo.com/developer/access/` states "Access to the
Yahoo Fantasy Sports API is read-only by default" and "Write access is not
available at this time". Both retrieved 2026-08-15. The app-creation form offers
only OpenID Connect and TW Auction, user-observed the same day.

References: D-001, D-002, L-003.

---

## D-004 — Opportunity signals adjust the consensus by a capped number of ranks, and the flex slots are allocated by projected points

Status: Decided (2026-08-15)

Decision: Keep expert consensus rank as the base order within each position, per
D-001, then move each player by a signal capped at plus or minus 8 ranks. Five
weighted inputs feed the signal: usage share (0.35), touchdown regression
(0.25), the 2026 team's passing efficiency (0.15), draft capital (0.15), and
reception dependence (0.10). Usage share, touchdown regression and reception
dependence apply only when the player is on the same team in 2026 as in 2025.
Touchdown regression is inverted: scoring far above expected moves a player
down, not up. For value-based drafting, fill the base roster slots first, then
allocate the 24 W/R/T flex slots to whichever remaining running backs,
receivers and tight ends project highest, so the flex split falls out of this
league's scoring rather than out of an assumed ratio.

Why: The owner asked for usage share, quarterback quality and draft capital to
influence the board. D-001 permits opportunity metrics only as a tiebreaker,
because between seasons players change teams and rookies are drafted on top of
incumbents. The cap is the reconciliation: it lets a genuinely mispriced player
move, while keeping the consensus as the anchor so this cannot become the
standalone extrapolation D-001 rejected. Touchdown regression is inverted
because touchdowns are the least repeatable component of fantasy scoring, and a
naive reading of the owner's stated criterion would have ranked the most
regression-prone players highest.

Tradeoff: The cap is a judgement, not a derived quantity, and it limits the
model on a player the consensus has badly wrong. Weights are assigned rather
than fitted, because there is no held-out season to fit them against without
building a backtest this project does not need. Separately, replacement level is
computed at the last starting slot, which is standard VBD but overvalues
quarterbacks: a one-QB league lets any owner stream a replacement off waivers,
so QB12 is not the real floor. The observed result put four quarterbacks in the
top 24 with the QB1 seventh overall. The fix, deferred to next session, is a
deeper QB replacement rank.

Alternative rejected: allocating the flex slots by a fixed ratio taken from how
flex is historically filled in 12-team leagues. Rejected because this league's
scoring is not standard, so a ratio observed in standard leagues would bake in
an assumption the projected points can resolve directly. Also rejected:
weighting the opportunity signals without a cap, which is the pure historical
extrapolation D-001 already refused.

Evidence: `build_rankings.py` run this session produced 15 players moved 4 or
more ranks against a cap of 8. Justin Jefferson +8 (third-highest 2025 target
share, 2 touchdowns against 8.55 expected), Jahmyr Gibbs -5 (18 touchdowns
against 10.68 expected). Replacement levels QB 296.6, RB 135.9, WR 134.8,
TE 120.8. Half-PPR point calculation verified against 2025 season totals in
`scoring.py`.

References: D-001, D-002, L-005, L-006.

---

## D-005 — Replacement level is the last player worth a roster slot, with quarterback and tight end pinned by roster shape

Status: Decided (2026-08-15). Supersedes the replacement-level clause of D-004
and closes Q-005.

Decision: Set each position's replacement level at the points of the last
player worth one of the 156 skill slots this league drafts (12 teams x 1 QB +
2 RB + 2 WR + 1 TE + 2 W/R/T + 5 bench), not at the last player filling a
starting slot. Quarterback is pinned at one per team and tight end at two per
team; running back and receiver depth is allocated by value across the
remaining slots, iterated with the resulting levels until the depths stop
moving. The settled depths are QB 12, TE 24, RB 49, WR 70, giving levels
QB 296.6, TE 88.7, RB 85.8, WR 81.7.

Why: D-004 deferred a fix for quarterbacks being overvalued, and named the
wrong lever. Value-based drafting scores a player as points minus replacement,
so moving a position's baseline deeper *lowers* the subtracted number and
*raises* every player at that position. The board only demotes quarterbacks
when the other positions' baselines move deeper relative to theirs. That
happens naturally once the bench is counted, because benches are almost
entirely running backs and receivers: RB and WR baselines fall from roughly the
24th to the 49th and 70th, while the quarterback floor does not move at all.
Pinning quarterback at one per team is the streaming assumption stated
directly — in a one-QB league nobody drafts a backup, so QB13 is always on
waivers.

Tradeoff: The two pins are judgements, not derived quantities, which reopens in
a small way the objection D-004 raised against assumed ratios. Pinning tight
end also removes it from the value allocation, so the flex is no longer split
purely by projected points as D-004 specified. The iteration is a fixed-point
search with no proof of convergence; it settles in two passes on this data and
is capped at 25.

Alternative rejected: Move only the quarterback baseline deeper, to rank 18.
This was the fix D-004 deferred and STATUS prescribed, and it is backwards. Run
this session, it moved the quarterback level from 296.6 to 244.2 and pushed the
top quarterback from 7th overall to 3rd, with four quarterbacks inside the top
12 — the opposite of its stated goal. Also rejected: pinning tight end at one
per team, which is what STATUS recommended in order to protect the tight-end
gap. It does the reverse, dropping the top tight end from 21st to 51st, because
raising his baseline shrinks his measured value. Also rejected: leaving every
position to the value allocation, which is self-consistent but hands tight end
42 roster slots, three and a half per team, which no league drafts.

Evidence: `build_rankings.py` run this session. Console reports depths QB 12,
RB 49, TE 24, WR 70 and levels QB 296.6, RB 85.8, TE 88.7, WR 81.7. Read back
from `out/yahoo_prerank.txt`: 216 names, all unique, no blanks, zero
quarterbacks in the top 12, first quarterback at line 19, first tight end at
line 21, first kicker or defence at line 152. Comparison boards for the
rejected alternatives were produced by scratch probes over a cached copy of the
same projection frame, so only the baseline differed between them.

References: D-001, D-004, L-007.

---

## D-006 — Quarterbacks are not pushed further down the board, because streaming is weekly work this owner has said he will not do

Status: Decided (2026-08-15)

Decision: Keep the quarterback replacement level at QB12, the last starting
slot, as set by D-005. Do not lower it further and do not add a rule forbidding
quarterbacks before a given line of the pre-rank list. The first quarterback
stays at line 19 of `out/yahoo_prerank.txt`.

Why: Every argument for demoting quarterbacks past this point is an argument
about streaming — replacing the quarterback most weeks to play the favourable
matchup. A 12-team league rosters 12 of the 32 starting quarterbacks, so about
20 sit on waivers, and an owner who works the wire really does beat QB12. But
D-002 records that this project exists because the owner has no time to manage
the team and intends not to attend the draft. Streaming costs time every week.
Setting the baseline on the strength of an activity the owner has stated he will
not perform would price the board for a different manager. Asked directly this
session, the owner confirmed set-and-forget.

Tradeoff: If the owner does start working the waiver wire mid-season, the board
will have paid a slightly early pick for a quarterback whose edge over a free
one is smaller than the board assumed. The exposure is one pick and roughly two
points a week, so it does not justify hedging in advance.

Alternative rejected: Lower the assumed value of a free quarterback to QB10 or
QB9, which moves the first quarterback from line 19 to 27 or 33 and shifts every
quarterback down together. Rejected on the streaming argument above, not on the
mechanism, which works and is a one-constant change if the owner's habits ever
change. Also rejected: a hard floor forbidding any quarterback before line N.
Rejected as blunt and unprincipled — it moves only the first quarterback and
leaves the rest bunched, and it has no reasoning behind the chosen N, whereas
the baseline expresses a claim that can be argued with.

Evidence: Scratch probes over the settled projection frame, varying only the
quarterback baseline: free = QB12 puts quarterbacks at lines 19, 40, 47, 59, 74;
QB10 at 27, 54, 59, 72, 87; QB9 at 33, 63, 69, 79, 93; QB6 at 53, 82, 87, 99.
The cost of skipping the quarterback at line 19 for the next player on the board
is 2.3 points across a season, and every other quarterback on the board sits
within 0.3 points of the player directly below him, which is why a floor buys
almost nothing. The position is also risk-free in one direction: 32 teams start
a quarterback and 12 are rostered, so pushing them later can cost quality but
can never leave the roster without one.

References: D-002, D-005.

---

## D-007 — A signal adjusts a player's projected points, not his positional rank, so the cap bounds value instead of position

Status: Decided (2026-08-15). Supersedes the capped-rank clause of D-004 and
closes Q-007.

Decision: Let the expert consensus alone decide which rank is read off the
points curve. Apply the combined signal to the points that lookup returns, as an
addition capped at plus or minus 24 points, scaled at 18 points per unit of
combined signal. Re-rank each position on the adjusted points. The cap on rank
movement is removed entirely: a player may move as many positional ranks as 24
points buys him, which is few at the top of a position and many in the middle.

Why: D-004's cap was applied in rank space and then read through the points
curve, which is not a bound at all. The curve is steepest at the top of a
position and nearly flat in the middle, so the same "capped" 8-rank shift was
worth about 86 points to the best running back and about 20 to a middling one.
No theory says the same evidence should be worth four times as much for one
player as for another purely because of where he sits on a list. The distortion
was an artifact of applying a linear operation in rank space and reading it
through a non-linear map, not a judgement anyone made. Moving the adjustment
into points space removes the map from the path. It also makes the cap a claim
that can be argued with: no single season of usage evidence outweighs the expert
consensus by more than about a point and a half per game.

The brief offered two fixes — cap in points, or apply the shift after the curve
lookup. They are the same fix. Applying the shift after the lookup means the
shift is denominated in points, and denominating it in points means it must be
applied after the lookup. This entry implements both descriptions as one change.

Tradeoff: 24 points is a judgement, not a fitted quantity, exactly as D-004's 8
ranks was. The scale of 18 points per signal unit is chosen so the cap binds at
1.33 standard deviations, which is where D-004's cap bound, so the intent that
an exceptional player reaches the cap and an ordinary one barely moves is
carried over rather than re-derived. Separately, the fix deliberately allows
large rank movement where the curve is flat: Davante Adams moves 8 receiver
ranks on 14.2 points. That is the intended behaviour and the mirror image of the
defect — where a rank is cheap in points, a rank move should be cheap to make.
The cost is that the "shift" column on the cheat sheet no longer reads as a
small tidy integer, which was the property that made the old defect invisible.

Alternative rejected: Keep the adjustment in rank space and vary the rank cap by
position, or by depth within a position, so that a rank is worth roughly the
same points everywhere. Rejected because it approximates in the wrong space: it
would need a per-position, per-depth table of rank-to-point conversions that the
curve already holds exactly, and every future change to the curve would silently
invalidate the table. Also rejected: capping the adjustment as a percentage of
the player's own projected points. Rejected because it reintroduces the same
defect in softer form — 15 per cent of the top back is 53 points and 15 per cent
of a middling one is 15 — and because the signals are z-scores of usage, which
carry no claim that a better player is mispriced by proportionally more.

Evidence: `build_rankings.py` run this session. Jahmyr Gibbs, consensus RB1,
carries the pool's largest touchdown overperformance (18 against 10.68 expected)
and therefore the board's largest downgrade under both methods. Under D-004 that
downgrade was 5 positional ranks, which the RB curve priced at 85.6 points
(354.1 at rank 1, 268.5 at rank 5), and he landed RB5, 8th overall. Under this
entry the same signal is worth minus 14.1 points, he stays RB1, and he lands 1st
overall. Ja'Marr Chase, consensus WR1, moved from 7th to 2nd on the same
mechanism, and shows the defect in its purest form: his own signal was small,
yet he lost 63.1 points. The receiver curve pays 328.6, 294.4, 265.5, 245.9,
239.7 and 227.8 at ranks 1 through 6. CeeDee Lamb rose from WR5 to WR1, worth
88.9 points, and Justin Jefferson from WR6 to WR2, worth 66.6, which displaced
Chase from rank 1 to rank 3 and cost him the difference between 328.6 and 265.5.
A capped rank move is therefore not even bounded for the player who receives it:
it silently repriced a third player who was never adjusted at all. Under this
entry Lamb and Jefferson receive plus 19.0 and plus 21.0 points, which is not
enough to pass him. 31 players are adjusted by 8 points or more against the
24-point cap. The change was isolated from the anchor swap of
D-008 by a scratch run holding the old feed anchor and applying only this fix:
Gibbs 1st and Chase 2nd in that run too, so D-008 contributes nothing to either
case. Zero quarterbacks remain in the top 12, so D-005 and D-006 still hold.

References: D-001, D-004, D-008, L-007.

---

## D-008 — The base consensus order comes from the owner's own FantasyPros export, not from the free feed's whole-league page

Status: Decided (2026-08-15). Narrows the source clause of D-001; the method is
unchanged.

Decision: Read the base order from
`references/FantasyPros_2026_Draft_ALL_Rankings.csv`, the owner's own export in
the scoring he selected. The export carries no player identifier, so the feed's
`redraft-overall` page is still loaded and joined on player name plus position,
purely to recover the FantasyPros id the opportunity signals key on. The export
stays untracked, as a redistributed third-party ranking that is not this
project's data to publish. The two extra columns it carries, season strength of
schedule and ECR against ADP, are deliberately not wired into the model yet.

Why: L-006 established that the free feed publishes exactly one whole-league
redraft page and it is full PPR. This league is half PPR, so that page
systematically over-ranks reception volume, and D-001 anchors the entire board
on it. The owner's export is the scoring he actually selected, which makes it
the closer anchor for the same method. The effect is smaller than it appears,
because only within-position order is consumed: `base_pos_rank` ranks each
player inside his own position, so the anchor never decides a running back
against a receiver. That comparison is made by the points curve and the
replacement level, which are already computed under this league's rules.

Tradeoff: The build now depends on a local untracked file, so it is no longer
reproducible from public data alone, and a fresh clone cannot run it. The export
holds 327 players against the feed's 505, which shortens the board from 216
names to 189; that still covers the 180 players the league drafts, but the slack
is thinner. `[INFERRED, not verified]` The export's scoring flavour is not
recorded anywhere inside the file. It was inferred from the running back and
receiver ordering — Gibbs 1st and Chase 3rd, where the full-PPR page has Chase
1st and Gibbs 3rd — which shows receptions are worth less than full PPR, but
cannot distinguish half PPR from standard. If it is standard rather than half,
this anchor is wrong in the opposite direction to the one it replaced. Recorded
as Q-008.

Alternative rejected: Keep the feed's full-PPR page. Rejected because the league
is half PPR and a full-PPR anchor is a known, directional error in the base
order, which no downstream step corrects. Also rejected: average the export with
the feed's PPR page. This is a real option and would be the better one if the
export turns out to be standard scoring, because the midpoint of standard and
full PPR is half PPR. Rejected for now because it is the right fix to a
different problem: if the export is already half PPR, averaging it back toward
full PPR reintroduces the error. Resolving Q-008 decides between them, and the
averaging option is cheap to build if the answer goes that way.

Evidence: The join was probed before any code changed. Player name plus position
matched 150 of the export's top 150 and 326 of its 327 rows against the feed's
`redraft-overall` page, with zero position disagreements and no row duplication;
the single miss is Noah Whittington at overall rank 326, below any board cut.
`build_rankings.py` now asserts on all three properties and exits if the top-150
match rate falls below 140. The swap's effect was isolated by running the same
code against both anchors: the top 12 is identical in composition, and the
largest moves are Brock Bowers 54th to 24th, De'Zhaun Stribling 127th to 87th,
Jonathon Brooks 99th to 63rd, Jayden Daniels 79th to 47th, Trey McBride 21st to
43rd and Travis Kelce 84th to 104th. Neither Gibbs nor Chase moves at all.

References: D-001, D-007, L-006.

---

## D-009 — No red zone or goal-line signal is added, because neither predicts anything the consensus does not already hold

Status: Decided (2026-08-15)

Decision: Do not add red zone carries, red zone targets, red zone carry or
target share, goal-line touches, goal-line share, or a "red zone premium"
(red zone share minus overall share) to the signal set. Do not revisit without
new evidence of a different kind — a same-season correlation is not that
evidence. Target competition between receivers is likewise not added: a
separate "best other pass catcher's share" term is already absorbed by target
share.

Why: The owner asked for these criteria and the intuition behind them is sound —
touchdowns are worth 6 points and red zone touches are where they happen. The
test disagrees. Measured over 2019-2025, six year-over-year transitions, every
red zone and goal-line variant adds nothing once the current season's fantasy
points are controlled for, which is the information the consensus baseline
already carries. Red zone carries add -0.042, red zone target share -0.004,
goal-line carries -0.106. They score highly against the SAME season only because
they are a component of it. Adding one would import noise and double-count the
touchdown-regression signal that D-004 already weights at 0.25, since heavy
goal-line usage this season is a mild predictor of DECLINE next season, not
growth. See L-008 for the portable form of this trap.

Tradeoff: A same-season fit is what most published fantasy analysis reports, so
this decision will look wrong against any article ranking players by red zone
opportunity. It also rejects a criterion the owner raised directly, which means
the burden is on this entry's evidence rather than on the intuition. The test
controls for last season's realised points as a proxy for the consensus, not the
consensus itself, which is unavailable historically; that proxy is weaker than
the real baseline, so the measured contribution is an UPPER bound. The signals
score at or below zero against an upper bound, which is what makes the rejection
safe rather than marginal.

Alternative rejected: Add red zone share at a small weight anyway, on the
grounds that the intuition is widely held and a small weight cannot do much
harm. Rejected because a signal measured to contribute nothing is not neutral in
this model — every weight is drawn from a fixed budget summing to one, so
carrying a dead term dilutes the terms that work, and L-009 shows the model is
already carrying one share metric with the wrong sign. Also rejected: adding a
receiver target-competition term, which measured -0.027 after target share was
accounted for, because two good receivers splitting the targets IS each man's
target share.

Evidence: Scratch panels built this session from `nfl.load_pbp(2019-2025)`,
regular season only, red zone defined as yardline_100 <= 20 and goal line as
<= 5, joined to league-scored season totals. Running backs, n=260 player-seasons
with 80+ carries: red zone carries same-season +0.724 / added -0.042; red zone
carry share +0.698 / -0.046; goal-line carries +0.650 / -0.106; goal-line share
+0.641 / -0.084; goal-line premium +0.234 / -0.128. Receivers and tight ends,
n=676 with 40+ targets: red zone targets +0.733 / -0.041; red zone target share
+0.695 / -0.004; goal-line targets +0.546 / -0.052; red zone premium -0.046 /
-0.092. Receiver target competition, n=676: -0.151 raw, -0.027 after target
share and team passing EPA. For contrast, in the same panels air yards share
adds +0.103 and age adds -0.228 / -0.215, both currently absent from the model
and both carried forward as Q-009.

References: D-001, D-004, L-008, L-009.

---

## D-010 — The signal budget is cut per position, sized by what each term adds once the others are in, and two of the four criteria Q-009 proposed do not survive their own test

Status: Decided (2026-08-15). Supersedes the weight clause of D-004 and closes
Q-009. Closes Q-008 with the owner's answer, half PPR.

Decision: Replace D-004's single five-weight table with one table per position
group, each summing to one:

| Term | RB | WR/TE | QB |
|---|---|---|---|
| age (inverted) | 0.31 | 0.36 | — |
| share (carry for RB, target for WR/TE) | 0.12 | 0.29 | — |
| rb_receiving (a back's own target share) | 0.25 | — | — |
| snap_share | 0.15 | — | — |
| pass_epa | — | 0.17 | 0.27 |
| td_luck (inverted) | 0.04 | 0.06 | 0.45 |
| draft_capital | 0.13 | 0.12 | 0.28 |

Build the age term for running backs, receivers and tight ends, and the snap
share term for running backs. Do NOT build a running back team-offence quality
term, and do NOT build air yards share as a term of its own. Drop
`reception_dependence` entirely. Keep carry share at a reduced weight. Cut
touchdown regression from 0.25 to 0.04 and 0.06.

Why, term by term:

*Age is built and is the largest weight at every position that was measured.*
It adds -0.188 for running backs and -0.185 for receivers and tight ends,
the strongest results in the set, and it is the only candidate that barely
moves when the other terms are controlled for (-0.183 and -0.197). It is
also the only one measuring something the usage terms cannot see, which is
that a player stops being available at all.

*Snap share is built for running backs only.* It adds +0.162 for backs and
holds +0.093 after carry share. For receivers and tight ends it adds +0.087
alone and -0.006 once target share is in, so for them it is target share
wearing a different name and would take budget from the term that works.

*Running back team-offence quality is NOT built, because it fails the test
D-009 used to reject the red zone metrics.* Every form of it measures at or
below zero for backs once the current season's points are controlled for:
total team EPA -0.039, passing EPA -0.024, rushing EPA -0.054, and team
expected touchdowns -0.039. L-009's 63-point gap between good and bad
offences is a SAME-SEASON comparison — good offences scored more in the
season they were good — which is exactly the evidence L-008 says does not
establish forward value. The same-season correlation of total team EPA with
points is +0.178, and none of it survives. Rejecting red zone usage on a
-0.042 while adopting team quality on a -0.039 would apply two standards to
one kind of evidence.

*Air yards share is NOT built as its own term.* It adds +0.157 alone but only
+0.042 once target share is controlled for, so it is largely target share
restated. Target share is the stronger measurement of the two (+0.214), and
it is already the model's `share` input for receivers, so the budget goes
there instead.

*Carry share is kept, at 0.12 rather than 0.35.* Session 4 recorded it adding
-0.012, which is what put it in doubt. Re-measured against season totals it
adds +0.137, and +0.082 after games and the other terms — modest, positive,
and the weakest of the four running back usage inputs, which is what the new
weight says. L-009's separate finding stands and is not what this reverses:
backs on bottom-third offences do hold the higher carry share (0.475 against
0.408 over 2019-2025), so the metric does carry that contamination. It simply
predicts next season anyway, and the fix L-009 proposed — pairing it with an
absolute team term — is not available, because the absolute team term measures
nothing (above).

*A back's own target share is built at 0.25, filling the slot the team-quality
term was meant to fill.* It adds +0.160 and holds +0.155 after carry share, so
it is the second strongest running back input after age and is close to
independent of the workload term already in the model. It is what actually
separates a back who keeps his value when the offence changes from one who
does not, which is the job the team-quality term was proposed to do.

*Reception dependence is dropped, on both available grounds.* The owner
answered Q-008 this session: the export is half PPR. That removes the
full-PPR anchor the term existed to correct, so it would now double-count a
correction already in the base order. Independently, the term as implemented
is negated, and receptions per game measured against next season's points
adds +0.141 for backs, so the term was contributing -0.141 — it was pointed
the wrong way for running backs regardless of the scoring answer.

*Touchdown regression falls from 0.25 to 0.04 and 0.06.* Inverted as D-004
specifies, it adds +0.032 for backs and +0.087 for receivers, so its direction
is right and its old weight was roughly eight times its measured contribution.
This term was not in Q-009's scope, but the budget cannot be cut on measured
contribution for four terms and left unmeasured on a fifth holding a quarter
of it.

*Per-position tables are what fixes the damping defect.* The old table zeroed
`pass_epa` for running backs inside a budget that still counted it, damping
every back's combined signal by 15% against every receiver's on identical
evidence, and quarterbacks by 45%. Renormalising is the fix; giving backs a
team term they do not deserve is not. A single table also cannot express that
`share` means carry share worth 0.12 to a back and target share worth 0.29 to
a receiver.

Tradeoff: the weights are proportional to measured contribution, which is
better founded than D-004's assignment, but the measurement controls for last
season's realised points as a proxy for the consensus rather than the consensus
itself, so every figure is an UPPER bound (the same caveat D-009 carries). The
consensus already knows how old a player is, so the age term's true marginal
value is smaller than -0.188. Quarterback weights are D-004's renormalised and
were never measured, because the panels cover backs, receivers and tight ends
only; the visible effect is that quarterback adjustments roughly double in
size, which put Josh Allen at board line 24 where he was 25. Separately, this
entry cuts touchdown regression hard enough to reverse the sign of the board's
former largest downgrade: Jahmyr Gibbs moves from -14.1 points to +13.0.

Alternative rejected: build all four criteria at the weights Q-009 implied,
which is what the session was set up to do. Rejected on measurement — two of
them contribute nothing once the terms already in the model are accounted for,
and D-009 rejected other criteria on weaker evidence than that. Also rejected:
keep one weight table and renormalise per player by which terms his position
carries. This is a smaller change and it does fix the damping, but it forces
one number to serve as both the carry-share weight and the target-share weight
when the two differ by a factor of two in measured value. Also rejected:
express age as the four bands STATUS records rather than as a standardised
value. The bands are monotonic and would work, but the contribution was
measured linearly, and a band table adds a lookup that the measurement does not
support.

Evidence: panel rebuilt this session over 2019-2025, six year-over-year
transitions, regular season only, scored under this league's rules, by L-008's
method. Running backs n=314 with 80+ carries, receivers and tight ends n=782
with 40+ targets. Re-run including players with no following season as zero
(n=327 and n=836) moves nothing material: age strengthens to -0.209 and -0.225,
shares soften by about 0.01. The full ADDED table is in the session record
below. `[INFERRED]` Session 4's differing figures are reproduced by measuring
next season's points PER GAME instead of the season total: carry share moves
from +0.137 to +0.026 against its recorded -0.012, and air yards share from
+0.157 to +0.115 against its recorded +0.103. Season total is the outcome this
model must predict, because the points curve and the replacement levels are
both season totals and no separate availability term exists. See L-010.
`build_rankings.py` run after the change: birthdate and pfr_id both resolve
150/150 of the top 150, `out/yahoo_prerank.txt` is 189 names, all unique, no
blanks, first tight end at 19, first quarterback at 24.

References: D-001, D-004, D-005, D-008, D-009, L-008, L-009, L-010.
