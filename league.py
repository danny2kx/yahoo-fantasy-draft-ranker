"""League configuration, transcribed from the Yahoo league Settings page.

Source of truth for scoring and roster shape. Transcribed by hand rather than
read from the API, because Yahoo gated the Fantasy Sports API behind an
approval queue (see docs/DECISIONS.md D-003). If access is ever granted,
probe_league.py should be run against this file as a cross-check.

Transcribed 2026-08-15.
"""

TEAMS = 12

# Live snake draft. Times are US Central.
DRAFT_TIME = "2026-09-05 16:00 CDT"

# Yahoo labels these W/R/T; RB, WR and TE are all eligible.
FLEX_ELIGIBLE = ("RB", "WR", "TE")

STARTERS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "W/R/T": 2,
    "K": 1,
    "DEF": 1,
}

BENCH = 5
IR = 1

# The owner's position in the draft order, user-stated. The injured-reserve slot
# is not drafted, so it does not add a round.
DRAFT_SLOT = 4
ROUNDS = sum(STARTERS.values()) + BENCH

# Overall pick numbers the owner holds. A snake reverses every other round, so
# an early slot pays for its round-1 pick with a late one in round 2.
OWNER_PICKS = tuple(
    (rnd - 1) * TEAMS + (DRAFT_SLOT if rnd % 2 else TEAMS - DRAFT_SLOT + 1)
    for rnd in range(1, ROUNDS + 1)
)

# Scoring is fractional and allows negatives, so no rounding or flooring
# anywhere in the points calculation.
FRACTIONAL_POINTS = True
NEGATIVE_POINTS = True

# Yardage settings are given on the Yahoo page as "N yards per point"; stored
# here already inverted to points per yard.
OFFENSE = {
    "passing_yards": 1 / 25,
    "passing_tds": 5,
    "passing_interceptions": -2,
    "rushing_yards": 1 / 10,
    "rushing_tds": 6,
    "receptions": 0.5,
    "receiving_yards": 1 / 10,
    "receiving_tds": 6,
    "return_tds": 6,
    "two_point_conversions": 2,
    "fumbles_lost": -2,
    "offensive_fumble_return_tds": 6,
}

KICKING = {
    "fg_made_0_19": 3,
    "fg_made_20_29": 3,
    "fg_made_30_39": 3,
    "fg_made_40_49": 4,
    "fg_made_50_plus": 5,
    "fg_missed_0_19": -1,
    "fg_missed_20_29": -1,
    "fg_missed_30_39": -1,
    "fg_missed_40_49": -1,
    "fg_missed_50_plus": -1,
    "pat_made": 1,
    "pat_missed": -1,
}

DEFENSE = {
    "sacks": 1.5,
    "interceptions": 2,
    "fumble_recoveries": 2,
    "touchdowns": 6,
    "safeties": 2,
    "blocked_kicks": 2,
    "return_tds": 6,
    "extra_points_returned": 2,
}

# Upper bound of points allowed -> points scored. Evaluated lowest bound first.
DEFENSE_POINTS_ALLOWED = (
    (0, 10),
    (6, 7),
    (13, 4),
    (20, 1),
    (27, 0),
    (34, -1),
    (float("inf"), -4),
)

# Yahoo's own defaults, kept only to document where this league departs from
# them. Each departure moves a whole position group, so they drive tie-breaks
# in the rankings rather than being trivia.
DEPARTURES_FROM_YAHOO_DEFAULT = {
    "passing_tds": (5, 4),
    "passing_interceptions": (-2, -1),
    "fg_missed_all_ranges": (-1, 0),
    "pat_missed": (-1, 0),
    "defense_sacks": (1.5, 1),
}
