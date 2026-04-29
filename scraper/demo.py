"""
Demo FC fixture generator.

Generates fixtures for the following 4 weeks for a fictional Demo FC club,
covering youth teams (U7–U18), Senior Men's, Senior Men's Reserves, and
Senior Women's. Called after the main scraper so demo data is always present
in the feeds/ directory.
"""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FEEDS_DIR = Path(__file__).parent.parent / "feeds"

LEAGUE_NAME = "Demo FC"
LEAGUE_SLUG = "demo-fc"
CLUB_NAME = "Demo FC"
CLUB_SLUG = "demo-fc"
VENUE = "Demo FC Ground"

YOUTH_AGES = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]

# Rotating pools of opponents — one per week per team
_YOUTH_OPPONENTS = [
    "Riverside Rangers",
    "City Athletic",
    "Northgate Youth",
    "Valley United",
    "Castleton Juniors",
    "Westfield Youth",
]

_SENIOR_OPPONENTS = [
    "Westfield United",
    "Northgate Athletic",
    "Castleton Rovers",
    "Valley Town",
    "Riverside Town",
    "Southbrook FC",
]

_RESERVES_OPPONENTS = [
    "Westfield United Reserves",
    "Northgate Athletic Reserves",
    "Castleton Rovers Reserves",
    "Valley Town Reserves",
    "Riverside Town Reserves",
    "Southbrook FC Reserves",
]

_WOMEN_OPPONENTS = [
    "Westfield Women",
    "Northgate Ladies",
    "Castleton Women",
    "Valley Town Women",
    "Riverside Ladies",
    "Southbrook Women",
]


def _fix_id(match_date: str, home: str, away: str) -> str:
    return hashlib.md5(f"{match_date}|{home}|{away}".encode()).hexdigest()


def _next_weekday(ref: date, weekday: int) -> date:
    """Return the next date on or after *ref* that falls on *weekday* (0=Mon … 6=Sun)."""
    days_ahead = (weekday - ref.weekday()) % 7
    return ref + timedelta(days=days_ahead)


def _four_saturdays(ref: date) -> list[date]:
    first = _next_weekday(ref + timedelta(days=1), 5)  # next Saturday after today
    return [first + timedelta(weeks=i) for i in range(4)]


def _four_sundays(ref: date) -> list[date]:
    first = _next_weekday(ref + timedelta(days=1), 6)  # next Sunday after today
    return [first + timedelta(weeks=i) for i in range(4)]


def _build_fixture(
    match_date: date,
    kick_off: str,
    home_team: str,
    away_team: str,
    division: str,
    demo_team: str,
) -> dict:
    date_str = match_date.isoformat()
    is_home = home_team == demo_team
    return {
        "id": _fix_id(date_str, home_team, away_team),
        "date": date_str,
        "time": kick_off,
        "home_team": home_team,
        "away_team": away_team,
        "venue": VENUE if is_home else "",
        "division": division,
        "home_away": "home" if is_home else "away",
        "opponent": away_team if is_home else home_team,
    }


def _generate_team_fixtures(
    team_name: str,
    opponent_pool: list[str],
    match_dates: list[date],
    kick_off: str,
    division: str,
    *,
    start_home: bool = True,
) -> list[dict]:
    fixtures = []
    for i, d in enumerate(match_dates):
        home_this_week = start_home if i % 2 == 0 else not start_home
        opp_name = f"{opponent_pool[i % len(opponent_pool)]} {team_name.split()[-1]}" \
            if "U" in team_name and team_name.split()[-1][0] == "U" \
            else opponent_pool[i % len(opponent_pool)]
        if home_this_week:
            home, away = team_name, opp_name
        else:
            home, away = opp_name, team_name
        fixtures.append(_build_fixture(d, kick_off, home, away, division, team_name))
    return fixtures


def generate(today: date | None = None) -> None:
    today = today or date.today()
    generated_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    saturdays = _four_saturdays(today)
    sundays = _four_sundays(today)

    teams: list[dict] = []  # for index.json

    league_dir = FEEDS_DIR / LEAGUE_SLUG
    teams_dir = league_dir / "teams"
    teams_dir.mkdir(parents=True, exist_ok=True)

    club_fixtures: list[dict] = []

    # ------------------------------------------------------------------ youth
    for age in YOUTH_AGES:
        team_name = f"Demo FC U{age}"
        team_slug = f"demo-fc-u{age}"
        division = f"U{age} Sunday"

        # younger age groups kick off earlier
        if age <= 9:
            kick_off = "10:00"
        elif age <= 13:
            kick_off = "10:30"
        else:
            kick_off = "11:00"

        # alternate start: even ages start home, odd ages start away
        start_home = (age % 2 == 0)

        fixtures = _generate_team_fixtures(
            team_name,
            _YOUTH_OPPONENTS,
            sundays,
            kick_off,
            division,
            start_home=start_home,
        )

        team_feed = {
            "team": team_name,
            "league": LEAGUE_NAME,
            "generated": generated_ts,
            "fixtures": fixtures,
            "results": [],
        }
        (teams_dir / f"{team_slug}.json").write_text(
            json.dumps(team_feed, indent=2) + "\n"
        )

        for fix in fixtures:
            club_fixtures.append({**fix, "league": LEAGUE_NAME, "team": team_name})

        teams.append({"name": team_name, "slug": team_slug})

    # --------------------------------------------------------------- senior men
    senior_name = "Demo FC"
    senior_slug = "demo-fc-seniors"
    senior_fixtures = _generate_team_fixtures(
        senior_name,
        _SENIOR_OPPONENTS,
        saturdays,
        "15:00",
        "Senior Men's League",
        start_home=True,
    )
    team_feed = {
        "team": senior_name,
        "league": LEAGUE_NAME,
        "generated": generated_ts,
        "fixtures": senior_fixtures,
        "results": [],
    }
    (teams_dir / f"{senior_slug}.json").write_text(
        json.dumps(team_feed, indent=2) + "\n"
    )
    for fix in senior_fixtures:
        club_fixtures.append({**fix, "league": LEAGUE_NAME, "team": senior_name})
    teams.append({"name": senior_name, "slug": senior_slug})

    # ----------------------------------------------------------- senior reserves
    reserves_name = "Demo FC Reserves"
    reserves_slug = "demo-fc-reserves"
    reserves_fixtures = _generate_team_fixtures(
        reserves_name,
        _RESERVES_OPPONENTS,
        saturdays,
        "15:00",
        "Senior Men's Reserves League",
        start_home=False,
    )
    team_feed = {
        "team": reserves_name,
        "league": LEAGUE_NAME,
        "generated": generated_ts,
        "fixtures": reserves_fixtures,
        "results": [],
    }
    (teams_dir / f"{reserves_slug}.json").write_text(
        json.dumps(team_feed, indent=2) + "\n"
    )
    for fix in reserves_fixtures:
        club_fixtures.append({**fix, "league": LEAGUE_NAME, "team": reserves_name})
    teams.append({"name": reserves_name, "slug": reserves_slug})

    # ------------------------------------------------------------ senior women
    women_name = "Demo FC Women"
    women_slug = "demo-fc-women"
    women_fixtures = _generate_team_fixtures(
        women_name,
        _WOMEN_OPPONENTS,
        sundays,
        "11:00",
        "Senior Women's League",
        start_home=False,
    )
    team_feed = {
        "team": women_name,
        "league": LEAGUE_NAME,
        "generated": generated_ts,
        "fixtures": women_fixtures,
        "results": [],
    }
    (teams_dir / f"{women_slug}.json").write_text(
        json.dumps(team_feed, indent=2) + "\n"
    )
    for fix in women_fixtures:
        club_fixtures.append({**fix, "league": LEAGUE_NAME, "team": women_name})
    teams.append({"name": women_name, "slug": women_slug})

    # ------------------------------------------------------- club-level feed
    club_feed = {
        "club": CLUB_NAME,
        "generated": generated_ts,
        "fixtures": sorted(club_fixtures, key=lambda f: (f["date"], f["team"])),
        "results": [],
    }
    clubs_dir = FEEDS_DIR / "clubs"
    clubs_dir.mkdir(exist_ok=True)
    (clubs_dir / f"{CLUB_SLUG}.json").write_text(
        json.dumps(club_feed, indent=2) + "\n"
    )

    # ------------------------------------------------------ update index.json
    index_path = FEEDS_DIR / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
    else:
        index = {"generated": generated_ts, "leagues": [], "clubs": []}

    # upsert league entry
    league_entry = {
        "name": LEAGUE_NAME,
        "slug": LEAGUE_SLUG,
        "teams": [{"name": t["name"], "slug": t["slug"]} for t in teams],
    }
    index["leagues"] = [
        lg for lg in index.get("leagues", []) if lg.get("slug") != LEAGUE_SLUG
    ]
    index["leagues"].append(league_entry)

    # upsert club entry
    club_entry = {
        "name": CLUB_NAME,
        "slug": CLUB_SLUG,
        "teams": [t["name"] for t in teams],
    }
    index["clubs"] = [
        cl for cl in index.get("clubs", []) if cl.get("slug") != CLUB_SLUG
    ]
    index["clubs"].append(club_entry)

    index_path.write_text(json.dumps(index, indent=2) + "\n")

    print(f"Demo FC: wrote {len(teams)} team feeds + club feed + updated index.json")


if __name__ == "__main__":
    generate()
