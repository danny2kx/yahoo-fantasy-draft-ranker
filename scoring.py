"""Fantasy points under this league's scoring, computed from raw stat lines.

Kept separate from the ranking pipeline so the point calculation can be checked
against a known box score without running anything else.
"""

import polars as pl

import league


def offensive_points(stats: pl.DataFrame) -> pl.Expr:
    """Points expression for one row of nflreadpy `load_player_stats` output.

    Every component is coalesced to zero: a receiver's row carries nulls in the
    passing columns, and a single null would otherwise blank the whole sum.
    """
    s = league.OFFENSE

    def col(name: str) -> pl.Expr:
        return pl.col(name).fill_null(0) if name in stats.columns else pl.lit(0)

    two_point = (
        col("passing_2pt_conversions")
        + col("rushing_2pt_conversions")
        + col("receiving_2pt_conversions")
    )
    fumbles_lost = (
        col("rushing_fumbles_lost")
        + col("receiving_fumbles_lost")
        + col("sack_fumbles_lost")
    )

    return (
        col("passing_yards") * s["passing_yards"]
        + col("passing_tds") * s["passing_tds"]
        + col("passing_interceptions") * s["passing_interceptions"]
        + col("rushing_yards") * s["rushing_yards"]
        + col("rushing_tds") * s["rushing_tds"]
        + col("receptions") * s["receptions"]
        + col("receiving_yards") * s["receiving_yards"]
        + col("receiving_tds") * s["receiving_tds"]
        + col("special_teams_tds") * s["return_tds"]
        + two_point * s["two_point_conversions"]
        + fumbles_lost * s["fumbles_lost"]
    )


def ppr_delta(stats: pl.DataFrame) -> pl.Expr:
    """Points a player would gain if the league were full PPR instead of half.

    Used to correct the consensus ordering, which is published on a full-PPR
    basis and therefore ranks high-reception players slightly too high for this
    league.
    """
    receptions = (
        pl.col("receptions").fill_null(0)
        if "receptions" in stats.columns
        else pl.lit(0)
    )
    return receptions * (1.0 - league.OFFENSE["receptions"])


def season_totals(stats: pl.DataFrame) -> pl.DataFrame:
    """Regular-season point totals per player per season.

    Postseason is excluded: fantasy leagues end before it, so playoff production
    would inflate the historical curve with points nobody could have scored for
    a fantasy team.
    """
    return (
        stats.filter(pl.col("season_type") == "REG")
        .with_columns(
            points=offensive_points(stats),
            ppr_gap=ppr_delta(stats),
        )
        .group_by("player_id", "season")
        .agg(
            player=pl.col("player_display_name").first(),
            position=pl.col("position").first(),
            team=pl.col("team").last(),
            games=pl.len(),
            points=pl.col("points").sum(),
            ppr_gap=pl.col("ppr_gap").sum(),
        )
    )
