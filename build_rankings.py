"""Produce the pre-draft ranking list for Yahoo's pre-rank page.

Method is D-001 and D-003 in docs/DECISIONS.md:

  1. Expert consensus rank sets the base order within each position.
  2. That rank is mapped onto a points curve built from the 2023-2025 seasons,
     scored under this league's own rules, so the points are correct for half
     PPR whatever the consensus was published under.
  3. Bounded signals then add or subtract points from what the curve returned,
     capped so the consensus always remains the anchor. Which signals apply and
     what they weigh depends on the position (D-010).
  4. Value-based drafting converts points into a single cross-position order.

Run: python build_rankings.py
"""

import csv
import math
from datetime import date
from pathlib import Path

import nflreadpy as nfl
import polars as pl

import league
import scoring

HISTORY_SEASONS = [2023, 2024, 2025]
SIGNAL_SEASON = 2025
DRAFT_CLASS = 2026
OUT = Path(__file__).parent / "out"

# Weeks 1-18 are the regular season; 19-22 are the four playoff rounds.
# `load_ff_opportunity` carries no season-type column, unlike the stats and snap
# sources, so the week number is the only filter available. Postseason rows have
# to go: a player on a deep playoff team otherwise banks four extra games of
# touchdowns in `td_luck`, which does not cancel the way a share ratio does.
REGULAR_SEASON_WEEKS = 18

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

# Age is measured against the season the player turns this age on 1 September.
AGE_ON = date(DRAFT_CLASS, 9, 1)

# The offensive personnel group in the depth chart source. The other three
# groups are the two defensive fronts and special teams.
DEPTH_OFFENCE_GROUP = "3WR 1TE"

# Which teammate is worth showing in the offence depth-chart column. A room-mate
# qualifies on any one of the three: the consensus already ranks him, someone
# spent real draft capital on him, or he already took a tenth of the position's
# work. All three are display thresholds and can be retuned without touching a
# ranking.
BIG_NAME_ECR = 150
BIG_NAME_ROUNDS = (1, 2)
BIG_NAME_SHARE = 0.10

# How many draft classes count as "recent" for the capital criterion. Unbounded,
# every long-tenured starter is a former high pick and the criterion selects
# almost everyone, which is the same as selecting nobody.
RECENT_DRAFT_CLASSES = 3

POSITION_GROUP = {"RB": "RB", "WR": "WR/TE", "TE": "WR/TE", "QB": "QB"}

# Weights per position group, each summing to one (asserted below). One table
# could not serve every position: `share` means carry share for a running back
# and target share for a receiver, and those two contribute very differently, so
# a single number would have to be both 0.12 and 0.29. Summing to one *per
# position* is also what removes the old damping defect — the previous single
# table zeroed 0.15 of a running back's budget and 0.45 of a quarterback's
# without renormalising, so identical evidence produced a smaller signal for
# them than for a receiver.
#
# Sizes are proportional to what each term still adds once the others are in the
# model, measured over 2019-2025 by L-008's method. Draft capital is not on that
# scale: it scores rookies, who have no prior season to measure.
SIGNAL_WEIGHTS = {
    "RB": {
        "age": 0.31,
        "rb_receiving": 0.25,
        "snap_share": 0.15,
        "share": 0.12,
        "td_luck": 0.04,
        "draft_capital": 0.13,
    },
    "WR/TE": {
        "age": 0.36,
        "share": 0.29,
        "pass_epa": 0.17,
        "td_luck": 0.06,
        "draft_capital": 0.12,
    },
    # Never measured: the age and share panels cover running backs, receivers
    # and tight ends only. These are D-004's quarterback weights renormalised,
    # nothing more, so a quarterback's signal is no longer damped 45% by terms
    # that cannot apply to him.
    "QB": {
        "td_luck": 0.45,
        "pass_epa": 0.27,
        "draft_capital": 0.28,
    },
}

SIGNAL_TERMS = (
    "age", "share", "rb_receiving", "snap_share", "pass_epa", "td_luck",
    "draft_capital",
)

for _group, _weights in SIGNAL_WEIGHTS.items():
    if abs(sum(_weights.values()) - 1.0) > 1e-9:
        raise SystemExit(f"{_group} weights sum to {sum(_weights.values())}, not 1")
    if set(_weights) - set(SIGNAL_TERMS):
        raise SystemExit(f"{_group} names a term that is never computed")

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
    """2025 regular-season usage share and touchdown luck, per player."""
    raw = nfl.load_ff_opportunity(seasons=[SIGNAL_SEASON])
    opp = raw.filter(pl.col("week") <= REGULAR_SEASON_WEEKS)
    print(f"  usage: {raw.height - opp.height} postseason rows dropped "
          f"of {raw.height}")
    if opp.height == raw.height:
        raise SystemExit("no postseason rows found; check the week column")
    agg = (
        opp.group_by("player_id")
        .agg(
            signal_team=norm_team(pl.col("posteam")).last(),
            games=pl.len(),
            carries=pl.col("rush_attempt").sum(),
            team_carries=pl.col("rush_attempt_team").sum(),
            targets=pl.col("rec_attempt").sum(),
            team_targets=pl.col("rec_attempt_team").sum(),
            td=pl.col("total_touchdown").sum(),
            td_exp=pl.col("total_touchdown_exp").sum(),
        )
        .filter(pl.col("games") >= 6)
        .with_columns(
            carry_share=pl.col("carries") / pl.col("team_carries"),
            target_share=pl.col("targets") / pl.col("team_targets"),
            # Positive means he scored more than his opportunity earned, which
            # is the regression signal, so it is subtracted later.
            td_luck=pl.col("td") - pl.col("td_exp"),
        )
    )
    return agg.select(
        "player_id", "signal_team", "carry_share", "target_share", "td_luck",
    )


def snap_shares() -> pl.DataFrame:
    """Share of his offence's snaps each player was on the field for, 2025.

    Keyed on the Pro Football Reference id, which is the only id this source
    carries, so it reaches the board through the same bridge table as the rest.
    """
    snaps = nfl.load_snap_counts(seasons=[SIGNAL_SEASON]).filter(
        pl.col("game_type") == "REG"
    )
    return (
        snaps.group_by("pfr_player_id")
        .agg(snap_share=pl.col("offense_pct").mean(), snap_games=pl.len())
        .filter(pl.col("snap_games") >= 6)
        .select(pl.col("pfr_player_id").alias("pfr_id"), "snap_share")
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
# 2b. Who else eats in this player's offence. DISPLAY ONLY.
#
# D-009 rejected a target-competition SIGNAL on measurement: a separate "best
# other pass catcher's share" term added -0.027 once target share was accounted
# for, because two receivers splitting the targets already IS each man's target
# share. Nothing below reaches SIGNAL_WEIGHTS, and turning it into a weighted
# term would need a new decision overturning D-009 on evidence of a different
# kind. It is here because the owner drafts against a room, not against a row.
# --------------------------------------------------------------------------

def depth_chart_offence() -> tuple[pl.DataFrame, str]:
    """The latest 2026 depth chart, offensive skill positions only.

    The source is a series of dated snapshots, roughly one per team per day
    since March, so the latest `dt` per team is taken rather than every row.
    It is keyed on `gsis_id`, which the board carries as `player_id`.

    Returns the chart and the snapshot date, which the cheat sheet prints: a
    mid-August depth chart is provisional, and knowing which day it describes
    is the whole basis for re-checking it after the final roster cuts (Q-010).
    """
    dc = nfl.load_depth_charts(seasons=[DRAFT_CLASS]).filter(
        (pl.col("pos_grp") == DEPTH_OFFENCE_GROUP)
        & pl.col("pos_abb").is_in(["QB", "RB", "WR", "TE"])
        & pl.col("gsis_id").is_not_null()
    )
    if dc.is_empty():
        raise SystemExit("no offensive depth chart rows; check pos_grp naming")

    latest = dc.group_by("team").agg(dt=pl.col("dt").max())
    dc = dc.join(latest, on=["team", "dt"], how="inner").with_columns(
        team=norm_team(pl.col("team"))
    )

    # A player traded between snapshots can still sit on his old team's latest
    # chart. Keep the row where he is ranked highest, which is the room he is
    # actually competing in.
    dc = dc.sort("pos_rank").unique(
        subset=["gsis_id"], keep="first", maintain_order=True
    )
    chart = dc.select(
        pl.col("gsis_id").alias("player_id"),
        "team",
        "player_name",
        pl.col("pos_abb").alias("depth_pos"),
        "pos_rank",
    )
    return chart, latest["dt"].max()


def recent_draft_capital() -> pl.DataFrame:
    """Round and overall pick for the last few classes, keyed on the gsis id.

    `draft_capital()` reads the same table keyed on the FantasyPros id, because
    that is the id the ranking signals join on. This column needs the same facts
    for room-mates who are not in the consensus export at all, and gsis is the
    only id those players share with the depth chart.
    """
    first_class = DRAFT_CLASS - RECENT_DRAFT_CLASSES + 1
    return (
        nfl.load_ff_playerids()
        .filter(
            (pl.col("draft_year") >= first_class) & pl.col("gsis_id").is_not_null()
        )
        .select(
            pl.col("gsis_id").alias("player_id"),
            pl.col("draft_year").alias("dc_year"),
            pl.col("draft_round").alias("dc_round"),
            pl.col("draft_ovr").alias("dc_pick"),
        )
        .unique(subset=["player_id"])
    )


def describe_mate(mate: dict) -> str:
    """One room-mate as a line of the depth-chart cell."""
    bits = [f"{mate['player_name']} {mate['depth_pos']}{mate['pos_rank']}"]
    if mate["ecr"] is not None:
        bits.append(f"ECR {mate['ecr']:.0f}")
    # Capital is shown only when it is high capital. A recent sixth-rounder is
    # in the table because some other criterion put him there, and printing his
    # round says the opposite of what the column is for.
    if mate["dc_round"] in BIG_NAME_ROUNDS:
        bits.append(
            f"rd{int(mate['dc_round'])} p{int(mate['dc_pick'])} {int(mate['dc_year'])}"
        )
    if mate["mate_share"] is not None:
        kind = "car" if mate["depth_pos"] == "RB" else "tgt"
        # A share earned somewhere else is the arrival being flagged, not a
        # claim on this offence, so the old team is named rather than hidden.
        moved = "" if mate["signal_team"] == mate["team"] else f" was {mate['signal_team']}"
        bits.append(f"{kind} {mate['mate_share'] * 100:.0f}%{moved}")
    return " · ".join(bits)


def competition_notes(ecr_by_id: pl.DataFrame, opp: pl.DataFrame) -> pl.DataFrame:
    """Per player, the room-mates at his own position worth knowing about."""
    chart, snapshot = depth_chart_offence()

    people = (
        chart.join(ecr_by_id, on="player_id", how="left")
        .join(
            opp.select("player_id", "signal_team", "carry_share", "target_share"),
            on="player_id",
            how="left",
        )
        .join(recent_draft_capital(), on="player_id", how="left")
        .with_columns(
            # The model's own convention: a back is measured on carries, a pass
            # catcher on targets. A quarterback competes for snaps, not touches,
            # so neither share describes him.
            mate_share=pl.when(pl.col("depth_pos") == "RB")
            .then(pl.col("carry_share"))
            .when(pl.col("depth_pos").is_in(["WR", "TE"]))
            .then(pl.col("target_share"))
            .otherwise(None)
        )
    )

    # Kleene logic: a null on every criterion leaves the whole test null, which
    # is not the same as failing it, so the fill is what excludes the unknowns.
    big_name = (
        (pl.col("ecr") <= BIG_NAME_ECR)
        | pl.col("dc_round").is_in(BIG_NAME_ROUNDS)
        | (pl.col("mate_share") >= BIG_NAME_SHARE)
    ).fill_null(False)

    rooms: dict[tuple[str, str], list[dict]] = {}
    for row in people.filter(big_name).sort("pos_rank").iter_rows(named=True):
        rooms.setdefault((row["team"], row["depth_pos"]), []).append(row)

    notes = []
    for row in chart.iter_rows(named=True):
        mates = [
            m
            for m in rooms.get((row["team"], row["depth_pos"]), [])
            if m["player_id"] != row["player_id"]
        ]
        notes.append(
            {
                "player_id": row["player_id"],
                "competition": [describe_mate(m) for m in mates],
                "depth_slot": f"{row['depth_pos']}{row['pos_rank']}",
                "depth_dt": snapshot,
            }
        )
    return pl.DataFrame(notes)


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
            "pfr_id",
            "birthdate",
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

    # A populated id column is not evidence it joins (L-005), and the age and
    # snap-share signals are worthless if these two arrive mostly null. Both are
    # checked over the top 150, where a missing value actually costs a pick.
    top = out.filter(pl.col("ecr") <= 150)
    for column, floor in (("birthdate", 130), ("pfr_id", 130)):
        resolved = top.filter(pl.col(column).is_not_null()).height
        print(f"  {column} resolved for {resolved}/{top.height} of the top 150")
        if resolved < floor:
            raise SystemExit(f"only {resolved}/150 resolved {column}; check the bridge")
    return out.rename({"gsis_id": "player_id"})


def build() -> pl.DataFrame:
    base = consensus()
    skill = base.filter(pl.col("pos").is_in(["QB", "RB", "WR", "TE"]))

    opp = opportunity_signals()
    epa = team_passing_quality()
    snaps = snap_shares()
    rookie, threat = draft_capital()

    df = (
        skill.join(opp, on="player_id", how="left")
        .join(epa, on="team", how="left")
        .join(snaps, on="pfr_id", how="left")
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
        # A back's receiving role is the part of his workload that survives a
        # change of coach or of goal-line back, and it is measured to be his
        # second strongest input after age.
        rb_receiving_raw=pl.when(same_team & (pl.col("pos") == "RB"))
        .then(pl.col("target_share"))
        .otherwise(None),
        snap_share_raw=pl.when(same_team & (pl.col("pos") == "RB"))
        .then(pl.col("snap_share"))
        .otherwise(None),
        age_years=(
            pl.lit(AGE_ON) - pl.col("birthdate").str.to_date(strict=False)
        ).dt.total_days()
        / 365.25,
    )

    df = df.with_columns(
        share=zscore(pl.col("share_raw")).over("pos").fill_null(0.0),
        # Inverted: scoring far above expected is a sell signal, not a buy one.
        td_luck=(-zscore(pl.col("td_luck_raw")).over("pos")).fill_null(0.0),
        pass_epa=pl.when(pl.col("pos").is_in(["WR", "TE", "QB"]))
        .then(zscore(pl.col("pass_epa")))
        .otherwise(0.0)
        .fill_null(0.0),
        rb_receiving=zscore(pl.col("rb_receiving_raw")).over("pos").fill_null(0.0),
        snap_share=zscore(pl.col("snap_share_raw")).over("pos").fill_null(0.0),
        # Inverted: the older player is the one to fade. Standardised within the
        # position, because a 29-year-old receiver and a 29-year-old back are
        # not at the same point of their curves.
        age=(-zscore(pl.col("age_years")).over("pos")).fill_null(0.0),
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

    # Each position's weights sum to one, so the combined signal stays on the
    # z-scale of its inputs for every position rather than only for receivers.
    # A term a position does not carry is absent from its table, not zeroed
    # inside a budget it still counts against.
    group = pl.col("pos").replace_strict(POSITION_GROUP)
    combined = sum(
        pl.col(term)
        * group.replace_strict(
            {g: w.get(term, 0.0) for g, w in SIGNAL_WEIGHTS.items()},
            return_dtype=pl.Float64,
        )
        for term in SIGNAL_TERMS
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

    # Joined last, after every point and rank is already settled, so the depth
    # chart cannot reach a signal even by accident. See the section header above
    # and D-009 for why it is not one.
    ecr_by_id = (
        base.select("player_id", "ecr")
        .drop_nulls("player_id")
        .unique(subset=["player_id"])
    )
    df = df.join(competition_notes(ecr_by_id, opp), on="player_id", how="left")

    # A populated id column is not evidence it joins (L-005). An unresolved
    # player shows an empty column rather than a wrong one, so this reports
    # rather than guesses.
    top = df.filter(pl.col("ecr") <= BIG_NAME_ECR)
    resolved = top.filter(pl.col("competition").is_not_null()).height
    print(f"  depth chart resolved for {resolved}/{top.height} of the top 150")
    if resolved < 0.8 * top.height:
        raise SystemExit("depth chart resolved for under 80% of the top 150")
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
            "<th>Notes</th><th>Who else eats</th></tr>"
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
            if r["competition"] is None:
                room = "<i>not on the depth chart</i>"
            elif r["competition"]:
                room = (f"<b>{r['depth_slot']}</b><br>"
                        + "<br>".join(r["competition"]))
            else:
                room = f"<b>{r['depth_slot']}</b> &mdash; no other big name"
            rows.append(
                f"<tr><td>{i}</td><td>{r['player']}</td>"
                f"<td>{r['pos']}{r['pos_slot']}</td>"
                f"<td>{r['pos']} T{r['pos_tier']}</td>"
                f"<td>{r['team']}</td><td>{r['points']:.0f}</td>"
                f"<td>{r['vbd']:.0f}</td><td>{r['point_shift']:+.1f}</td>"
                f"<td>{r['rank_move']:+d}</td>"
                f"<td>{r['bye'] or ''}</td><td>{'; '.join(notes)}</td>"
                f"<td>{room}</td></tr>"
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

    snapshot = board["depth_dt"].drop_nulls().max() or "unknown"
    html = f"""<!doctype html>
<meta charset="utf-8"><title>Draft cheat sheet</title>
<style>
 body {{ font: 14px system-ui, sans-serif; margin: 2rem; max-width: 84rem; }}
 h1 {{ margin-bottom: .25rem; }}
 h2 {{ margin-top: 1.75rem; border-bottom: 2px solid #333; padding-bottom: .2rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ text-align: left; padding: .3rem .5rem; border-bottom: 1px solid #ddd;
           vertical-align: top; }}
 th {{ background: #f4f4f4; }}
 td:nth-child(11) {{ color: #a33; font-size: 12px; }}
 td:nth-child(12) {{ color: #444; font-size: 12px; line-height: 1.45;
                     min-width: 20rem; }}
 p.postier {{ margin: .4rem 0 .8rem; padding-left: .6rem;
              border-left: 3px solid #ccc; }}
 span.vbd {{ color: #777; font-size: 12px; }}
 p.legend {{ color: #555; font-size: 12px; max-width: 52rem; }}
</style>
<h1>Draft cheat sheet</h1>
<p>{league.TEAMS} teams, half PPR, two W/R/T flex. Draft {league.DRAFT_TIME}.
Take any player in the same tier; the order inside a tier is close to a
coin flip. Kickers and defences are deliberately absent, take them last.</p>
<p class=legend><b>Who else eats</b> is the offence's own depth chart at this
player's position, snapshot {snapshot}. Bold is his own slot; each line under it
is a room-mate, with his depth slot, his consensus rank, his draft capital if he
went in the first two rounds of the last three classes, and his 2025 share of
the position's work (carries for a back, targets for a pass catcher). A
room-mate is listed if any one of those three is big: consensus top
{BIG_NAME_ECR}, round {BIG_NAME_ROUNDS[0]}-{BIG_NAME_ROUNDS[1]} pick, or
{BIG_NAME_SHARE:.0%}+ share. &ldquo;was DET&rdquo; means the share was earned on
another team last year. This column is <b>information, not a ranking input</b>:
target competition was measured and rejected as a signal (D-009), so nothing
here moved anybody. Preseason charts are provisional &mdash; re-run after the
final roster cuts (Q-010).</p>
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
