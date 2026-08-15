"""Produce the pre-draft ranking list for Yahoo's pre-rank page.

Method is D-001 and D-003 in docs/DECISIONS.md:

  1. Expert consensus rank sets the base order within each position.
  2. That rank is mapped onto a points curve built from the 2023-2025 seasons,
     scored under this league's own rules, so the points are correct for half
     PPR whatever the consensus was published under.
  3. Four bounded signals nudge a player up or down within his position, capped
     so the consensus always remains the anchor.
  4. Value-based drafting converts points into a single cross-position order.

Run: python build_rankings.py
"""

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

# No single signal may move a player more than this many ranks within his
# position. The cap is what keeps this an adjustment to the consensus rather
# than the standalone extrapolation D-001 rejected.
MAX_RANK_SHIFT = 8

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
    return (
        ecr.select(
            pl.col("id").cast(pl.Utf8),
            "player",
            "pos",
            team=norm_team(pl.col("team")),
            ecr="ecr",
            sd="sd",
            best="best",
            worst="worst",
            bye="bye",
        )
        .join(bridge, on="id", how="left")
        .rename({"gsis_id": "player_id"})
    )


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
    # inputs. Six ranks per standard deviation puts a genuinely exceptional
    # player at the cap and leaves an ordinary one barely moved.
    combined = sum(
        pl.col(name) * weight for name, weight in SIGNAL_WEIGHTS.items()
    )
    df = df.with_columns(signal=combined).with_columns(
        rank_shift=(pl.col("signal") * 6.0)
        .round(0)
        .clip(-MAX_RANK_SHIFT, MAX_RANK_SHIFT)
    )

    # Re-rank within position: consensus order, moved by the capped shift.
    df = df.with_columns(
        base_pos_rank=pl.col("ecr").rank("ordinal").over("pos")
    ).with_columns(
        adj_key=pl.col("base_pos_rank") - pl.col("rank_shift")
    ).with_columns(
        pos_rank=pl.col("adj_key").rank("ordinal").over("pos").cast(pl.Int64)
    )

    curve = points_curve().rename({"position": "pos"})
    df = df.join(curve.select("pos", "pos_rank", "curve_points"),
                 on=["pos", "pos_rank"], how="left")

    # Beyond the curve's last observed rank a player is below every replacement
    # level anyway, so flooring at zero costs nothing and keeps him in the list.
    df = df.with_columns(points=pl.col("curve_points").fill_null(0.0))
    return df


# --------------------------------------------------------------------------
# 4. Value-based drafting.
# --------------------------------------------------------------------------

def replacement_levels(df: pl.DataFrame) -> dict[str, float]:
    """Points of the last player at each position who fills a starting slot.

    The two W/R/T slots are not assigned by assumption. Base slots are filled
    first, then every remaining running back, receiver and tight end competes
    for the flex slots on projected points alone, so the flex split falls out of
    this league's scoring rather than out of a guess.
    """
    levels: dict[str, float] = {}
    flex_pool = []

    for pos in ("QB", "RB", "WR", "TE"):
        base_slots = league.TEAMS * league.STARTERS[pos]
        ranked = df.filter(pl.col("pos") == pos).sort("points", descending=True)
        starters = ranked.head(base_slots)
        levels[pos] = float(starters["points"].min()) if starters.height else 0.0
        if pos in league.FLEX_ELIGIBLE:
            flex_pool.append(ranked.slice(base_slots))

    flex_slots = league.TEAMS * league.STARTERS["W/R/T"]
    pool = pl.concat(flex_pool).sort("points", descending=True).head(flex_slots)
    for pos in league.FLEX_ELIGIBLE:
        taken = pool.filter(pl.col("pos") == pos)
        if taken.height:
            levels[pos] = float(taken["points"].min())
    return levels


def assign_tiers(df: pl.DataFrame) -> pl.DataFrame:
    """Break the value curve where it steps down hardest.

    A tier is the set of players who are close enough in value that taking any
    of them is roughly the same decision. The breaks are the gaps that are large
    relative to the typical gap, which is what makes a cheat sheet useful during
    a live draft.
    """
    ordered = df.sort("vbd", descending=True)
    values = ordered["vbd"].to_list()
    gaps = [values[i] - values[i + 1] for i in range(len(values) - 1)]
    if not gaps:
        return ordered.with_columns(tier=pl.lit(1))

    positive = sorted(g for g in gaps if g > 0)
    threshold = positive[int(len(positive) * 0.88)] if positive else math.inf

    tiers, current = [], 1
    for i in range(len(values)):
        tiers.append(current)
        if i < len(gaps) and gaps[i] >= threshold:
            current += 1
    return ordered.with_columns(tier=pl.Series("tier", tiers))


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
            "<tr><th>#</th><th>Player</th><th>Pos</th><th>Team</th>"
            "<th>Proj</th><th>VBD</th><th>Shift</th><th>Bye</th><th>Notes</th></tr>"
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
                f"<tr><td>{i}</td><td>{r['player']}</td><td>{r['pos']}</td>"
                f"<td>{r['team']}</td><td>{r['points']:.0f}</td>"
                f"<td>{r['vbd']:.0f}</td><td>{r['rank_shift']:+.0f}</td>"
                f"<td>{r['bye'] or ''}</td><td>{'; '.join(notes)}</td></tr>"
            )
        rows.append("</table>")

    html = f"""<!doctype html>
<meta charset="utf-8"><title>Draft cheat sheet</title>
<style>
 body {{ font: 14px system-ui, sans-serif; margin: 2rem; max-width: 60rem; }}
 h1 {{ margin-bottom: .25rem; }}
 h2 {{ margin-top: 1.75rem; border-bottom: 2px solid #333; padding-bottom: .2rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ text-align: left; padding: .3rem .5rem; border-bottom: 1px solid #ddd; }}
 th {{ background: #f4f4f4; }}
 td:nth-child(9) {{ color: #a33; font-size: 12px; }}
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
    print("\nTop 24 of the board:")
    print(f"  {'#':>3} {'player':<24}{'pos':<5}{'tm':<5}{'proj':>7}{'vbd':>7}{'shift':>7}{'tier':>6}")
    for i, r in enumerate(board.head(24).iter_rows(named=True), 1):
        print(
            f"  {i:>3} {str(r['player'])[:23]:<24}{r['pos']:<5}{str(r['team']):<5}"
            f"{r['points']:>7.1f}{r['vbd']:>7.1f}{r['rank_shift']:>+7.0f}{r['tier']:>6}"
        )

    movers = board.filter(pl.col("rank_shift").abs() >= 4).sort("rank_shift")
    print(f"\nBiggest downgrades ({movers.height} players moved 4+ ranks):")
    for r in movers.head(8).iter_rows(named=True):
        print(f"  {str(r['player'])[:24]:<26}{r['pos']:<5}{r['rank_shift']:>+4.0f}")
    print("Biggest upgrades:")
    for r in movers.tail(8).reverse().iter_rows(named=True):
        print(f"  {str(r['player'])[:24]:<26}{r['pos']:<5}{r['rank_shift']:>+4.0f}")

    rookies = board.filter(pl.col("draft_round").is_not_null())
    print(f"\n{rookies.height} rookies on the board -- these need manual RSP review:")
    for r in rookies.sort("vbd", descending=True).head(12).iter_rows(named=True):
        print(
            f"  {str(r['player'])[:24]:<26}{r['pos']:<5}{str(r['team']):<5}"
            f"rd{int(r['draft_round'])} p{int(r['draft_pick'])}  tier {r['tier']}"
        )


if __name__ == "__main__":
    main()
