"""Preflight probe: prove the Yahoo chain end to end.

Pulls the settings that drive value-based drafting -- league size, scoring
rules, roster slots, draft type and date -- and prints them. Deliberately does
not request the teams endpoint: that returns real managers' names, which have
no place in this repo.

Run: python probe_league.py
"""

import os

from dotenv import load_dotenv

from yahoo_auth import api_get

load_dotenv()

LEAGUE_ID = os.environ.get("YAHOO_LEAGUE_ID", "864440")

# Yahoo wraps every collection in a dict keyed by stringified index alongside a
# "count" key. This walks that shape back into a plain list.
def _items(container: dict) -> list:
    return [container[key] for key in container if key != "count"]


def current_game_key() -> str:
    data = api_get("game/nfl")
    return data["fantasy_content"]["game"][0]["game_key"]


def my_leagues() -> list[dict]:
    """Every NFL league on the authorized account.

    Confirms the token belongs to the account that owns the target league,
    rather than another account that also has fantasy teams.
    """
    data = api_get("users;use_login=1/games;game_keys=nfl/leagues")
    users = data["fantasy_content"]["users"]["0"]["user"]
    games = next(part for part in users if isinstance(part, dict) and "games" in part)
    found = []
    for game in _items(games["games"]):
        for entry in _items(game["game"][1]["leagues"]):
            found.append(entry["league"][0])
    return found


def league_settings(league_key: str) -> tuple[dict, dict]:
    data = api_get(f"league/{league_key}/settings")
    league = data["fantasy_content"]["league"]
    return league[0], league[1]["settings"][0]


def main() -> None:
    print("Leagues visible on the authorized account:")
    visible = my_leagues()
    for league in visible:
        marker = "  <-- target" if str(league.get("league_id")) == LEAGUE_ID else ""
        print(
            f"  [{league.get('league_id')}] {league.get('name')} "
            f"({league.get('num_teams')} teams, {league.get('scoring_type')})"
            f"{marker}"
        )

    if not any(str(x.get("league_id")) == LEAGUE_ID for x in visible):
        raise SystemExit(
            f"\nLeague {LEAGUE_ID} is NOT on this account. The token belongs to a "
            "different Yahoo user.\nDelete tokens/yahoo.json and re-authorize while "
            "signed into the account that owns it."
        )

    game_key = current_game_key()
    league_key = f"{game_key}.l.{LEAGUE_ID}"
    print(f"\nLeague key: {league_key}\n")

    meta, settings = league_settings(league_key)

    print(f"Name          : {meta.get('name')}")
    print(f"Season        : {meta.get('season')}")
    print(f"Teams         : {meta.get('num_teams')}")
    print(f"Scoring type  : {meta.get('scoring_type')}")
    print(f"Draft status  : {meta.get('draft_status')}")
    print(f"Draft type    : {settings.get('draft_type')}")
    print(f"Draft time    : {settings.get('draft_time')}")
    print(f"Playoff start : week {settings.get('playoff_start_week')}")

    print("\nRoster slots:")
    for slot in _items(settings["roster_positions"]):
        position = slot["roster_position"]
        print(f"  {position['position']:>6} x{position.get('count', 1)}")

    print("\nReception scoring (decides PPR vs half vs standard):")
    for stat in _items(settings["stat_modifiers"]["stats"]):
        modifier = stat["stat"]
        if str(modifier.get("stat_id")) == "11":
            print(f"  points per reception: {modifier.get('value')}")


if __name__ == "__main__":
    main()
