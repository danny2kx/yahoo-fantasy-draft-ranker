# LESSONS

Append-only. Published entries are never edited; correct with a new entry
marked "Supersedes L-NNN".

---

## L-001 — Read an OAuth2 provider's refresh-grant parameter list separately from its authorization-code list

When: Implementing OAuth2 token refresh against any provider, at the moment the
refresh request body is written.

Do: Look up the provider's documented parameter list for the `refresh_token`
grant specifically, and do not assume it mirrors the `authorization_code` grant.
Yahoo requires `redirect_uri` on both; many providers require it on neither.
Where the provider's own docs list a parameter as required, send it even if the
request appears to succeed without it in a first manual test.

Root cause: The two grants are usually documented on the same page under similar
headings, which invites reading one list and applying it to both. A missing
refresh parameter cannot fail at authorization time — it fails at the first
refresh, typically an hour later and unattended, so it is invisible during the
build-and-test loop that would otherwise catch it.

Evidence: `yahoo_auth.py` initially omitted `redirect_uri` from the refresh
payload. Caught by reading
https://developer.yahoo.com/oauth2/guide/flows_authcode/ this session, which
lists `redirect_uri` as required for the `refresh_token` grant. Fixed in commit
5d2bca2 before any live token existed.

---

## L-002 — After a join, assert on the joined column, because a name collision silently returns the wrong one

When: Joining two dataframes (polars, pandas) where both sides carry a column of
the same name, and the value being read comes from the right-hand side.

Do: Either drop the colliding column from the left frame before joining, or
assert on the result — check the non-null rate of the joined column against what
the join should plausibly produce. A join that "works" but yields near-total
nulls in the column you care about is the signature of this failure, not evidence
that the data is missing.

Root cause: Polars and pandas both resolve a column-name collision by suffixing
the right-hand column (`yahoo_id_right`) and leaving the left-hand name bound to
the original, mostly-empty column. Nothing errors. Every downstream read silently
returns the pre-join values, so the join looks like it failed on the data rather
than on the column reference.

Evidence: Joining `load_ff_rankings()` to `load_ff_playerids()` this session
reported 5 of the top 100 players resolving a Yahoo ID, which prompted a search
for a data problem that did not exist. Both frames carry `yahoo_id`. After
dropping it from the rankings frame first, the true rate was 133/172 (77%) of the
top-180. The wrong number was 15x off and pointed the investigation at the wrong
system entirely.

---

## L-003 — Make the first API call after authorization a "what can I see" listing, not the real request

When: Building any integration against a third-party API where the token's scope
and the account it belongs to are chosen by a human in a web form, outside the
code.

Do: Before calling the endpoint the application actually needs, call whatever
endpoint enumerates the resources the token can reach — the user's leagues,
repositories, accounts, projects. Compare that list against the target resource
and fail with an explicit message naming the fix. Treat scope and account
identity as things to be verified at runtime, never as things the setup
instructions guaranteed.

Root cause: OAuth authorization succeeds and returns a valid token regardless of
which scope was granted or which account approved it. Both mistakes therefore
survive the entire auth flow undetected and surface only at the first real data
call, as a generic permission or not-found error on an endpoint that is in fact
correct. The error message points at the endpoint, which is the one part that was
never wrong.

Evidence: This session's app was registered with the **TW Auction** permission
(Yahoo Taiwan's e-commerce marketplace) instead of Fantasy Sports, chosen from an
adjacent checkbox in the same list. Nothing in the token exchange would have
revealed it. A parallel possibility — approving while signed into a different
Yahoo account than the one owning the league — produces an indistinguishable
failure. `probe_league.py` now lists the authorized account's leagues first and
exits naming the fix when the target is absent (commit 7b1c60f).

---

## L-004 — On a 401, read the WWW-Authenticate header and probe the most trivial endpoint, because the status code alone cannot tell a bad token from an unscoped one

When: Any authenticated API call fails with 401, and the request was built from
credentials that were themselves obtained successfully.

Do: Two things before touching the request code. First, print the
`WWW-Authenticate` response header and the response body, not just the status.
Providers put the actual reason there, and it is the only part that
distinguishes "this token is invalid or expired" from "this token is fine but
the application was never granted this product." Second, call the simplest
endpoint the API offers, one that takes no identifiers. If that also fails, the
problem is the credential's scope, and no amount of fixing the URL, the resource
id, or the account will help.

Root cause: HTTP 401 collapses several unrelated failures into one number. The
natural next move is to suspect the parts that vary, so the request path, the
resource id, and the signed-in account all get investigated first. Those are the
parts that are usually correct. The scope was fixed at application registration
time, days earlier, in a web form, and nothing in the token exchange reports it.
Meanwhile a valid token is returned and looks entirely healthy, which argues
against the true cause.

Evidence: Every Yahoo fantasy endpoint returned 401 with
`oauth_problem="additional_authorization_required"` this session, after a token
exchange that succeeded and issued a 1012-character access token. The trivial
`game/nfl` endpoint, which carries no league id and no user reference, failed
identically to `league/<key>/settings`. That one comparison ruled out the league
id and the signed-in account in a single call and pointed straight at the app
permission, which was the one thing not visible from any code path.

References: L-003, D-003.

---

## L-005 — A populated ID column is not evidence it joins to another table's column of the same name

When: Joining two tables that come from the same data package or vendor, where
both carry an identifier with the same name and neither is documented as the
canonical key.

Do: Measure the join rate before building anything on top of it. Count matched
rows against expected rows and fail loudly at zero. When the rate is zero or
implausibly low, look for the same fact carried on a table that already shares a
key with your left-hand side, rather than debugging the key you started with.
Treat a populated column as evidence the column exists, never as evidence it
refers to the same namespace as its namesake elsewhere.

Root cause: Within one package the same identifier name can be sourced from
different upstream feeds that populate it at different times. A player drafted
but not yet on a roster can hold a provisional id in one table and the real one
in another. Nothing is null, nothing errors, and a left join simply yields
nulls in the new columns, which reads as "this player has no data" rather than
"these two tables do not share a namespace".

Evidence: `nflreadpy.load_draft_picks(2026)` carries `gsis_id` populated for 73
of 80 skill picks, and `load_ff_playerids()` carries `gsis_id` too. Joining them
matched 0 of 73. The rookie draft-capital signal silently scored zero for every
player, and the first pipeline run reported "0 rookies on the board" while
looking otherwise healthy. The same facts live on `load_ff_playerids` as
`draft_year` / `draft_round` / `draft_ovr`, keyed on the FantasyPros id already
in use, which matched immediately.

---

## L-006 — Two columns both called a "rank" are only comparable if they cover the same population

When: Combining, differencing or averaging two ranking columns from the same
source, especially when a short type code rather than a descriptive name
distinguishes them.

Do: Before treating two rankings as the same scale, print the row count, the
distinct positions, and the source identifier for each slice. Two rankings are
comparable only when both cover the same set of entities. When a source exposes
both a terse type code and a descriptive one, trust the descriptive one: the
terse code often groups slices that a human would never combine.

Root cause: A rank is a position within a population, so it carries no meaning
outside that population. Rank 12 among kickers and rank 12 among all players are
different quantities wearing the same label, and arithmetic across them produces
numbers that are well-formed and meaningless. Nothing in the type system objects,
because both columns are just integers.

Evidence: `load_ff_rankings()` exposes `ecr_type` codes (`ro`, `rp`) alongside a
descriptive `page_type`. Averaging the `ro` and `rp` slices to synthesise a
half-PPR rank produced kickers ranked 226th in one and 12th in the other, and
duplicated players whose names appeared in both. Grouping by `page_type` instead
showed the slices are separate populations, that the `ro` set includes defensive
players, and that the only whole-league redraft ranking available comes from a
single PPR page. The intended interpolation was not possible at all, which the
descriptive grouping revealed in one query.

---

## L-007 — In any "value over a baseline" score, lowering one group's baseline promotes that group, so a group can only be demoted by moving the *other* baselines

When: Tuning any metric of the form `score = value - baseline`, where each group
carries its own baseline and the groups are then ranked against each other.
Value-based drafting is one instance; so is scoring against a per-segment
target, a per-cohort benchmark, or a per-category budget.

Do: Before choosing which way to move a baseline, write the subtraction down and
read the sign. A deeper, weaker, or more pessimistic baseline is a *smaller*
number subtracted, which makes the group score *higher*. Then check whether the
lever can reach the goal at all: because every group is ranked on the same
scale, moving one group's baseline alone can only push that group up or down as
a block. Demoting a group relative to the others requires moving the others.
Finally, state the expected direction and magnitude before running the change,
and treat a result in the opposite direction as a defect in the reasoning, not
as a surprising property of the data.

Root cause: The word chosen for the lever usually describes the intent, not the
arithmetic. "Set a deeper replacement level for quarterbacks because they are
easy to replace" reads as a demotion, and the phrase "easy to replace" reinforces
it, but the operation it names is subtracting less, which is a promotion. The
mistake is invisible in review because the sentence is true and the direction is
never checked against the formula. It also survives the first run, because the
board still looks well-formed and correctly ordered — only the position of one
group has moved, in the direction nobody re-read.

Evidence: A prescribed fix moved the quarterback replacement rank from 12 to 18
to push quarterbacks down the draft board. The level fell from 296.6 to 244.2,
so every quarterback's score rose by 52 points. The top quarterback moved from
7th overall to 3rd and four quarterbacks landed inside the top 12, against an
acceptance test of zero. The same error appeared a second time in the same plan,
for tight ends, in the opposite direction: pinning the tight-end baseline
shallow to "protect the tight-end gap" dropped the top tight end from 21st to
51st. What actually worked was leaving the quarterback baseline where it was and
moving running back and receiver from the 24th player to the 49th and 70th.

References: D-005.
