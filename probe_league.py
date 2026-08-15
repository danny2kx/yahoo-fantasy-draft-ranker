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


def league_settings(league_key: str) -> tuple[dict, dict]:
    data = api_get(f"league/{league_key}/settings")
    league = data["fantasy_content"]["league"]
    return league[0], league[1]["settings"][0]


def main() -> None:
    game_key = current_game_key()
    league_key = f"{game_key}.l.{LEAGUE_ID}"
    print(f"League key: {league_key}\n")

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
