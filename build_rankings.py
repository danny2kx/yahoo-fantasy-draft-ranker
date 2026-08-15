"""Produce the pre-draft ranking list for Yahoo's pre-rank page.

Method is D-001 and D-003 in docs/DECISIONS.md:

  1. Expert consensus rank sets the base order within each position.
  2. That rank is mapped onto a points curve built from the 2023-2025 seasons,
     scored under this league's own rules, so the points are correct for half
     PPR whatever the consensus was published under.
  3. Five bounded signals then add or subtract points from what the curve
     returned, capped so the consensus always remains the anchor.
  4. Value-based drafting converts points into a single cross-position order.

Run: python build_rankings.py
"""

import csv
import math
from pathlib import Path

import nflreadpy as nfl
import polars as pl

import league
import scoring

HISTORY_SEASONS = [2023, 2024, 2025]
SIGNAL_SEASON = 2025
DRAFT_CLASS = 2026
OUT = Path(__file__).parent / "out"

# The owner's own consensus export, in the scoring his league actually uses.
# Untracked: it is a redistributed third-party ranking, not this project's data.
ANCHOR_CSV = (
    Path(__file__).parent / "references" / "FantasyPros_2026_Draft_ALL_Rankings.csv"
)

# The combined signal adjusts a player's projected points, never his rank. A
# capped rank move is not a capped adjustment: the curve is steepest at the top
# of a position, so the same 8-rank cap was worth 86 points to the best running
# back and 20 to a middling one. Capping the points instead makes the bound mean
# one thing everywhere. The number is a claim that can be argued with: no single
# season of usage evidence outweighs the expert consensus by more than about a
# point and a half per game.
MAX_POINT_SHIFT = 24.0

# Points per unit of combined signal. Set so the cap binds at the same 1.33
# standard deviations it bound at under the rank cap, preserving the intent that
# an exceptional player reaches the cap while an ordinary one barely moves.
POINTS_PER_SIGNAL = 18.0

# Every skill slot the league drafts: starters, flex and bench. Benches are
# almost entirely running backs and receivers, which is why the real free-agent
# running back sits far deeper than the last starting slot.
SKILL_SLOTS = league.TEAMS * (
    league.STARTERS["QB"] + league.STARTERS["RB"] + league.STARTERS["WR"]
    + league.STARTERS["TE"] + league.STARTERS["W/R/T"] + league.BENCH
)

# Players per team at the positions whose roster count is set by roster shape
# rather than by value. Quarterback is one per team: in a one-QB league nobody
# drafts a backup, so the 13th quarterback is always on waivers and the spread
# from QB1 to QB12 is too small to pay an early pick for. Tight end is two per
# team, because leaving it to the value allocation hands it 42 slots, which is
# three and a half tight ends per roster.
PINNED_PER_TEAM = {"QB": 1, "TE": 2}

SIGNAL_WEIGHTS = {
    "share": 0.35,
    "td_luck": 0.25,
    "pass_epa": 0.15,
    "draft_capital": 0.15,
    "reception_dependence": 0.10,
}

# Every source spells the same franchises differently. Normalised to nflverse.
TEAM_ALIASES = {
    "LAR": "LA", "STL": "LA", "RAM": "LA",
    "LVR": "LV", "OAK": "LV", "RAI": "LV",
    "NOR": "NO", "SFO": "SF", "TAM": "TB", "KAN": "KC",
    "GNB": "GB", "NWE": "NE", "SDG": "LAC", "JAC": "JAX",
    "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU",
}


def norm_team(expr: pl.Expr) -> pl.Expr:
    return expr.replace(TEAM_ALIASES)


def zscore(expr: pl.Expr) -> pl.Expr:
    """Standardise within the current group, with a zero fallback.

    A position group where every player has the same value has no signal, and
    dividing by its zero standard deviation would produce nulls that silently
    drop players from the ranking.
    """
    return pl.when(expr.std() > 0).then((expr - expr.mean()) / expr.std()).otherwise(0.0)


# --------------------------------------------------------------------------
# 1. Points curve: what the Nth-best player at a position actually scored.
# --------------------------------------------------------------------------

def points_curve() -> pl.DataFrame:
    stats = nfl.load_player_stats(seasons=HISTORY_SEASONS)
    totals = scoring.season_totals(stats).filter(
        pl.col("position").is_in(["QB", "RB", "WR", "TE"])
    )
    ranked = totals.with_columns(
        pos_rank=pl.col("points")
        .rank("ordinal", descending=True)
        .over("position", "season")
    )
    curve = (
        ranked.group_by("position", "pos_rank")
        .agg(
            curve_points=pl.col("points").mean(),
            seasons=pl.len(),
        )
        .filter(pl.col("seasons") == len(HISTORY_SEASONS))
        .sort("position", "pos_rank")
    )
    return curve


# --------------------------------------------------------------------------
# 2. Signals. Every one is optional: a player missing it scores zero, which
#    means "no evidence", not "bad".
# --------------------------------------------------------------------------

def opportunity_signals() -> pl.DataFrame:
    """2025 usage share and touchdown luck, per player."""
    opp = nfl.load_ff_opportunity(seasons=[SIGNAL_SEASON])
    agg = (
        opp.group_by("player_id")
        .agg(
            signal_team=norm_team(pl.col("posteam")).last(),
            games=pl.len(),
            carries=pl.col("rush_attempt").sum(),
            team_carries=pl.col("rush_attempt_team").sum(),
            targets=pl.col("rec_attempt").sum(),
            team_targets=pl.col("rec_attempt_team").sum(),
            receptions=pl.col("receptions").sum(),
            td=pl.col("total_touchdown").sum(),
            td_exp=pl.col("total_touchdown_exp").sum(),
        )
        .filter(pl.col("games") >= 6)
        .with_columns(
            carry_share=pl.col("carries") / pl.col("team_carries"),
            target_share=pl.col("targets") / pl.col("team_targets"),
            receptions_per_game=pl.col("receptions") / pl.col("games"),
            # Positive means he scored more than his opportunity earned, which
            # is the regression signal, so it is subtracted later.
            td_luck=pl.col("td") - pl.col("td_exp"),
        )
    )
    return agg.select(
        "player_id", "signal_team", "carry_share", "target_share",
        "receptions_per_game", "td_luck",
    )


def team_passing_quality() -> pl.DataFrame:
    """The passing environment a receiver inherits, from 2025 team results."""
    team = nfl.load_team_stats(seasons=[SIGNAL_SEASON]).filter(
        pl.col("season_type") == "REG"
    )
    return (
        team.group_by(norm_team(pl.col("team")).alias("team"))
        .agg(pass_epa=pl.col("passing_epa").sum())
    )


def draft_capital() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Rookie capital, and the threat that capital poses to an incumbent.

    Rookie capital comes from `load_ff_playerids`, keyed on the same FantasyPros
    id the consensus uses. `load_draft_picks` carries the same facts but its
    gsis ids do not match this class (0 of 73 joined), so it is used only for
    the team-level threat, which needs no player identity at all.
    """
    picks = nfl.load_draft_picks(seasons=[DRAFT_CLASS]).with_columns(
        team=norm_team(pl.col("team"))
    )
    skill = picks.filter(pl.col("position").is_in(["RB", "WR", "TE", "QB"]))

    rookie = (
        nfl.load_ff_playerids()
        .filter(pl.col("draft_year") == DRAFT_CLASS)
        .select(
            pl.col("fantasypros_id").cast(pl.Utf8).alias("id"),
            draft_round="draft_round",
            draft_pick="draft_ovr",
        )
        .unique(subset=["id"])
    )

    # Only round-1 capital at the same position is treated as a real threat.
    # Later picks are depth, and scoring them as threats produced obvious false
    # alarms (an established WR1 "threatened" by a third-round tight end).
    threat = (
        skill.filter(pl.col("round") == 1)
        .group_by("team", "position")
        .agg(threat_pick=pl.col("pick").min())
    )
    return rookie, threat


# --------------------------------------------------------------------------
# 3. Assemble.
# --------------------------------------------------------------------------

def anchor_ranks() -> pl.DataFrame:
    """The owner's own consensus export, which sets the base order.

    The free feed publishes one whole-league redraft page and it is full PPR,
    which over-ranks reception volume for this half-PPR league. The export is
    the scoring the owner selected, so it is the closer anchor. It carries no
    player id, which is why the feed is still read below: purely to recover one.

    The stray blank-rank row the export contains is dropped, and the ragged line
    it sits on is why this is parsed with the csv module rather than polars.
    """
    with ANCHOR_CSV.open(encoding="utf-8-sig") as handle:
        rows = [r for r in csv.DictReader(handle) if r["RK"]]
    if not rows:
        raise SystemExit(f"{ANCHOR_CSV} has no ranked rows; check the export")
    return pl.DataFrame(
        {
            "player": [r["PLAYER NAME"] for r in rows],
            "pos": [r["POS"].rstrip("0123456789") for r in rows],
            "team": [r["TEAM"] for r in rows],
            "ecr": [float(r["RK"]) for r in rows],
            "bye": [int(r["BYE WEEK"]) if r["BYE WEEK"] else None for r in rows],
        }
    ).with_columns(team=norm_team(pl.col("team")))


def consensus() -> pl.DataFrame:
    ecr = nfl.load_ff_rankings().filter(pl.col("page_type") == "redraft-overall")
    if ecr.height != ecr["id"].n_unique():
        raise SystemExit("redraft-overall is not one row per player; check the source")

    bridge = (
        nfl.load_ff_playerids()
        .select(
            pl.col("fantasypros_id").cast(pl.Utf8).alias("id"),
            "gsis_id",
            "yahoo_id",
        )
        .unique(subset=["id"])
    )
    # Name and position, not name alone: the feed's whole-league page includes
    # defensive players, so a shared name could otherwise match the wrong one.
    ids = ecr.select(pl.col("id").cast(pl.Utf8), "player", "pos").unique(
        subset=["player", "pos"]
    )

    base = anchor_ranks()
    out = base.join(ids, on=["player", "pos"], how="left").join(
        bridge, on="id", how="left"
    )
    if out.height != base.height:
        raise SystemExit("id join duplicated anchor rows; check for shared names")
    matched = out.filter(pl.col("id").is_not_null() & (pl.col("ecr") <= 150)).height
    if matched < 140:
        raise SystemExit(f"only {matched}/150 of the anchor's top 150 resolved an id")
    return out.rename({"gsis_id": "player_id"})


def build() -> pl.DataFrame:
    base = consensus()
    skill = base.filter(pl.col("pos").is_in(["QB", "RB", "WR", "TE"]))

    opp = opportunity_signals()
    epa = team_passing_quality()
    rookie, threat = draft_capital()

    df = (
        skill.join(opp, on="player_id", how="left")
        .join(epa, on="team", how="left")
        .join(rookie, on="id", how="left")
        .join(
            threat.rename({"team": "threat_team", "position": "threat_pos"}),
            left_on=["team", "pos"],
            right_on=["threat_team", "threat_pos"],
            how="left",
        )
    )

    # Usage share only carries over if the player is on the same team in 2026.
    # Between seasons the line, the coordinator and the depth chart all change,
    # which is exactly why D-001 refused to project from opportunity alone.
    same_team = pl.col("signal_team") == pl.col("team")
    df = df.with_columns(
        share_raw=pl.when(same_team)
        .then(
            pl.when(pl.col("pos") == "RB")
            .then(pl.col("carry_share"))
            .otherwise(pl.col("target_share"))
        )
        .otherwise(None),
        td_luck_raw=pl.when(same_team).then(pl.col("td_luck")).otherwise(None),
        recpg_raw=pl.when(same_team).then(pl.col("receptions_per_game")).otherwise(None),
    )

    df = df.with_columns(
        share=zscore(pl.col("share_raw")).over("pos").fill_null(0.0),
        # Inverted: scoring far above expected is a sell signal, not a buy one.
        td_luck=(-zscore(pl.col("td_luck_raw")).over("pos")).fill_null(0.0),
        pass_epa=pl.when(pl.col("pos").is_in(["WR", "TE", "QB"]))
        .then(zscore(pl.col("pass_epa")))
        .otherwise(0.0)
        .fill_null(0.0),
        # Full-PPR consensus ranks high-reception players slightly too high for
        # a half-PPR league, so reception volume is a mild downgrade here.
        reception_dependence=(-zscore(pl.col("recpg_raw")).over("pos")).fill_null(0.0),
    )

    df = df.with_columns(
        draft_capital=(
            pl.when(pl.col("draft_round") == 1).then(2.5)
            .when(pl.col("draft_round") == 2).then(1.2)
            .otherwise(0.0)
            + pl.when(pl.col("threat_pick").is_not_null() & pl.col("draft_round").is_null())
            .then(-2.0)
            .otherwise(0.0)
        )
    )

    # Weights sum to one, so the combined signal stays on the z-scale of its
    # inputs.
    combined = sum(
        pl.col(name) * weight for name, weight in SIGNAL_WEIGHTS.items()
    )
    df = df.with_columns(signal=combined).with_columns(
        point_shift=(pl.col("signal") * POINTS_PER_SIGNAL)
        .clip(-MAX_POINT_SHIFT, MAX_POINT_SHIFT)
    )

    # The consensus alone decides which rank is read off the curve. The signal
    # is applied to the points that lookup returned, never to the rank feeding
    # it, so the cap bounds value rather than position.
    df = df.with_columns(
        base_pos_rank=pl.col("ecr").rank("ordinal").over("pos").cast(pl.Int64)
    )
    curve = points_curve().rename({"position": "pos", "pos_rank": "base_pos_rank"})
    df = df.join(
        curve.select("pos", "base_pos_rank", "curve_points"),
        on=["pos", "base_pos_rank"],
        how="left",
    )

    # Beyond the curve's last observed rank a player is below every replacement
    # level anyway, so flooring at zero costs nothing and keeps him in the list.
    df = df.with_columns(
        points=pl.when(pl.col("curve_points").is_null())
        .then(0.0)
        .otherwise(
            (pl.col("curve_points") + pl.col("point_shift")).clip(lower_bound=0.0)
        )
    ).with_columns(
        pos_rank=pl.col("points")
        .rank("ordinal", descending=True)
        .over("pos")
        .cast(pl.Int64)
    ).with_columns(
        rank_move=(pl.col("base_pos_rank") - pl.col("pos_rank")).cast(pl.Int64)
    )
    return df


# --------------------------------------------------------------------------
# 4. Value-based drafting.
# --------------------------------------------------------------------------

def replacement_levels(df: pl.DataFrame) -> dict[str, float]:
    """Points of the last player at each position worth a roster slot.

    Not the last player who fills a *starting* slot: a starting-slot baseline
    values a position by how many of it you must start, when what matters is how
    many of it get taken before you would have to settle. Running backs and
    receivers fill the benches, so their real floor is far deeper than the last
    starter, while quarterbacks and tight ends barely touch a bench at all. That
    difference is the whole reason a one-QB league does not draft a quarterback
    early.

    Running back and receiver depth is not assumed. The positions in
    PINNED_PER_TEAM are fixed, every other player competes for the remaining
    slots on value alone, and the two feed each other until the depths stop
    moving, which takes a couple of passes.
    """
    positions = ("QB", "RB", "WR", "TE")
    ranked = {
        pos: df.filter(pl.col("pos") == pos).sort("points", descending=True)
        for pos in positions
    }
    # A position can never be shallower than the slots the league must start.
    floor = {pos: league.TEAMS * league.STARTERS[pos] for pos in positions}
    pinned = {pos: league.TEAMS * n for pos, n in PINNED_PER_TEAM.items()}
    allocated = [pos for pos in positions if pos not in pinned]

    def levels_for(depths: dict[str, int]) -> dict[str, float]:
        return {
            pos: float(ranked[pos].head(n)["points"].min()) if ranked[pos].height else 0.0
            for pos, n in depths.items()
        }

    depths = floor | pinned
    for _ in range(25):
        levels = levels_for(depths)
        drafted = (
            df.with_columns(
                replacement=pl.col("pos").replace_strict(levels, default=0.0)
            )
            .with_columns(vbd=pl.col("points") - pl.col("replacement"))
            .sort("vbd", descending=True)
            .head(SKILL_SLOTS)
        )
        settled = dict(pinned)
        for pos in allocated:
            settled[pos] = max(drafted.filter(pl.col("pos") == pos).height, floor[pos])
        if settled == depths:
            break
        depths = settled

    print("Roster slots each position is worth: " + "  ".join(
        f"{pos} {n}" for pos, n in sorted(depths.items())
    ))
    return levels_for(depths)


def tier_breaks(values: list[float]) -> list[int]:
    """Tier numbers for a descending list of values, cut where it steps down.

    A tier is the set of players close enough in value that taking any of them
    is roughly the same decision. The breaks are the gaps that are large
    relative to the typical gap in that same list.
    """
    gaps = [values[i] - values[i + 1] for i in range(len(values) - 1)]
    if not gaps:
        return [1] * len(values)

    positive = sorted(g for g in gaps if g > 0)
    threshold = positive[int(len(positive) * 0.88)] if positive else math.inf

    tiers, current = [], 1
    for i in range(len(values)):
        tiers.append(current)
        if i < len(gaps) and gaps[i] >= threshold:
            current += 1
    return tiers


def assign_tiers(df: pl.DataFrame) -> pl.DataFrame:
    """Tier the board twice: across every position, and within each one.

    The overall tier answers "who else is this pick worth about the same as",
    which is what matters when any position is still open. The positional tier
    answers "which of these running backs are interchangeable", which is what
    matters once a slot is the thing being filled, and the overall board cannot
    show it because it interleaves positions.
    """
    ordered = df.sort("vbd", descending=True)
    ordered = ordered.with_columns(
        tier=pl.Series("tier", tier_breaks(ordered["vbd"].to_list()))
    )

    parts = []
    for group in ordered.partition_by("pos", maintain_order=True):
        group = group.sort("vbd", descending=True)
        parts.append(
            group.with_columns(
                pos_tier=pl.Series("pos_tier", tier_breaks(group["vbd"].to_list())),
                pos_slot=pl.int_range(1, group.height + 1, eager=True),
            )
        )
    return pl.concat(parts).sort("vbd", descending=True)


def main() -> None:
    df = build()
    levels = replacement_levels(df)

    print("Replacement level (points of the last startable player):")
    for pos, value in sorted(levels.items()):
        print(f"  {pos:>4}: {value:7.1f}")

    df = df.with_columns(
        replacement=pl.col("pos").replace_strict(levels, default=0.0)
    ).with_columns(vbd=pl.col("points") - pl.col("replacement"))

    # Anyone below replacement is not draftable ahead of a kicker or defence.
    board = assign_tiers(df.filter(pl.col("vbd") > 0))

    OUT.mkdir(exist_ok=True)
    write_prerank(board, df)
    write_cheatsheet(board)
    report(board)


def kickers_and_defences() -> pl.DataFrame:
    base = consensus()
    return base.filter(pl.col("pos").is_in(["K", "DST"])).sort("ecr")


def write_prerank(board: pl.DataFrame, df: pl.DataFrame) -> None:
    """One name per line, in draft order, for Yahoo's pre-rank page.

    Kickers and defences are appended last on purpose. Autopick follows this
    order, and with only five bench slots a kicker taken early costs a starter.
    """
    lines = [r["player"] for r in board.iter_rows(named=True)]
    lines += [r["player"] for r in kickers_and_defences().iter_rows(named=True)]
    path = OUT / "yahoo_prerank.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {path}  ({len(lines)} players)")


def write_cheatsheet(board: pl.DataFrame) -> None:
    rows = []
    for tier, group in board.group_by("tier", maintain_order=True):
        rows.append(f'<h2>Tier {tier[0]}</h2><table>')
        rows.append(
            "<tr><th>#</th><th>Player</th><th>Pos</th><th>Pos tier</th><th>Team</th>"
            "<th>Proj</th><th>VBD</th><th>Adj</th><th>Moved</th><th>Bye</th>"
            "<th>Notes</th></tr>"
        )
        for i, r in enumerate(group.iter_rows(named=True), 1):
            notes = []
            if r["draft_round"] is not None:
                notes.append(f"rookie rd{int(r['draft_round'])} -- check RSP")
            if r["threat_pick"] is not None and r["draft_round"] is None:
                notes.append("team spent rd1 pick at his position")
            if r["signal_team"] is not None and r["signal_team"] != r["team"]:
                notes.append("changed teams; usage signal not applied")
            if r["signal_team"] is None:
                notes.append("no 2025 usage data")
            rows.append(
                f"<tr><td>{i}</td><td>{r['player']}</td>"
                f"<td>{r['pos']}{r['pos_slot']}</td>"
                f"<td>{r['pos']} T{r['pos_tier']}</td>"
                f"<td>{r['team']}</td><td>{r['points']:.0f}</td>"
                f"<td>{r['vbd']:.0f}</td><td>{r['point_shift']:+.1f}</td>"
                f"<td>{r['rank_move']:+d}</td>"
                f"<td>{r['bye'] or ''}</td><td>{'; '.join(notes)}</td></tr>"
            )
        rows.append("</table>")

    rows.append("<h1>By position</h1><p>Inside one positional tier the order is "
                "close to a coin flip. Take the bye week or the safer role.</p>")
    for group in board.partition_by("pos", maintain_order=True):
        pos = group["pos"][0]
        rows.append(f"<h2>{pos}</h2>")
        for tier_group in group.sort("vbd", descending=True).partition_by(
            "pos_tier", maintain_order=True
        ):
            names = ", ".join(
                f"{r['player']} ({r['team']}, bye {r['bye'] or '?'})"
                for r in tier_group.iter_rows(named=True)
            )
            lo = tier_group["vbd"].min()
            hi = tier_group["vbd"].max()
            rows.append(
                f"<p class=postier><b>{pos} tier {tier_group['pos_tier'][0]}</b> "
                f"<span class=vbd>vbd {hi:.0f} to {lo:.0f}</span><br>{names}</p>"
            )

    html = f"""<!doctype html>
<meta charset="utf-8"><title>Draft cheat sheet</title>
<style>
 body {{ font: 14px system-ui, sans-serif; margin: 2rem; max-width: 60rem; }}
 h1 {{ margin-bottom: .25rem; }}
 h2 {{ margin-top: 1.75rem; border-bottom: 2px solid #333; padding-bottom: .2rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ text-align: left; padding: .3rem .5rem; border-bottom: 1px solid #ddd; }}
 th {{ background: #f4f4f4; }}
 td:nth-child(11) {{ color: #a33; font-size: 12px; }}
 p.postier {{ margin: .4rem 0 .8rem; padding-left: .6rem;
              border-left: 3px solid #ccc; }}
 span.vbd {{ color: #777; font-size: 12px; }}
</style>
<h1>Draft cheat sheet</h1>
<p>{league.TEAMS} teams, half PPR, two W/R/T flex. Draft {league.DRAFT_TIME}.
Take any player in the same tier; the order inside a tier is close to a
coin flip. Kickers and defences are deliberately absent, take them last.</p>
{''.join(rows)}
"""
    path = OUT / "cheatsheet.html"
    path.write_text(html, encoding="utf-8")
    print(f"Wrote {path}  ({board['tier'].max()} tiers)")


def report(board: pl.DataFrame) -> None:
    print("\nTop 24 of the board -- rounds 1 and 2 of a 12-team snake:")
    print(f"  {'#':>3} {'player':<24}{'pos':<5}{'tm':<5}{'proj':>7}{'vbd':>7}"
          f"{'adj':>7}{'moved':>7}{'tier':>6}")
    for i, r in enumerate(board.head(24).iter_rows(named=True), 1):
        if i in (1, 13):
            print(f"  -- round {1 if i == 1 else 2} --")
        mine = " <== your pick" if i in league.OWNER_PICKS else ""
        print(
            f"  {i:>3} {str(r['player'])[:23]:<24}{r['pos']:<5}{str(r['team']):<5}"
            f"{r['points']:>7.1f}{r['vbd']:>7.1f}{r['point_shift']:>+7.1f}"
            f"{r['rank_move']:>+7d}{r['tier']:>6}{mine}"
        )

    movers = board.filter(pl.col("point_shift").abs() >= 8).sort("point_shift")
    down = movers.filter(pl.col("point_shift") < 0)
    up = movers.filter(pl.col("point_shift") > 0).reverse()
    print(f"\n{movers.height} players adjusted 8+ points (cap {MAX_POINT_SHIFT:.0f}).")
    for label, group in (("Biggest downgrades", down), ("Biggest upgrades", up)):
        print(f"{label} ({group.height}):")
        for r in group.head(8).iter_rows(named=True):
            print(f"  {str(r['player'])[:24]:<26}{r['pos']:<5}"
                  f"{r['point_shift']:>+7.1f} pts{r['rank_move']:>+4d} ranks")

    print("\nTop of each position, with the tier break marked:")
    for group in board.partition_by("pos", maintain_order=True):
        pos = group["pos"][0]
        print(f"  {pos}")
        rows = list(group.sort("vbd", descending=True).head(12).iter_rows(named=True))
        for r in rows:
            print(f"    T{r['pos_tier']} {pos}{r['pos_slot']:<3}"
                  f"{str(r['player'])[:22]:<24}{str(r['team']):<5}"
                  f"vbd {r['vbd']:>6.1f}   board {r['tier']:>2}")

    rookies = board.filter(pl.col("draft_round").is_not_null())
    print(f"\n{rookies.height} rookies on the board -- these need manual RSP review:")
    for r in rookies.sort("vbd", descending=True).head(12).iter_rows(named=True):
        print(
            f"  {str(r['player'])[:24]:<26}{r['pos']:<5}{str(r['team']):<5}"
            f"rd{int(r['draft_round'])} p{int(r['draft_pick'])}  tier {r['tier']}"
        )


if __name__ == "__main__":
    main()
