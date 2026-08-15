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
