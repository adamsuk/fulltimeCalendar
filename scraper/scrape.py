"""
YEL East Midlands — Full-Time fixture scraper
Generates one .ics file per team across all configured leagues/seasons.
"""

import os
import re
import time
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://fulltime.thefa.com/fixtures/1/100000.html"

# Each league is identified by its selectedSeason parameter on Full-Time.
# Update these season IDs at the start of each new season.
LEAGUES: list[tuple[str, str]] = [
    ("909330396", "YEL East Midlands Sunday 25/26"),
    ("161954265", "YEL East Midlands Saturday 25/26"),
]

OUTPUT_DIR = Path(__file__).parent.parent / "calendars"
OUTPUT_DIR.mkdir(exist_ok=True)

# Retry configuration for HTTP requests
HTTP_RETRIES = 5
HTTP_BACKOFF_FACTOR = 2  # waits 2s, 4s, 8s, 16s, 32s between retries
HTTP_TIMEOUT = 90  # seconds


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Fixture(NamedTuple):
    date: str          # e.g. "22/03/26" (DD/MM/YY)
    time: str          # e.g. "10:00" or "" if TBC
    home_team: str
    away_team: str
    venue: str         # home team's ground, if listed
    division_label: str


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def fetch_fixtures(season_id: str, league_name: str) -> list[Fixture]:
    """Fetch all fixtures for a given season/league in a single request."""
    url = f"{BASE_URL}?selectedSeason={season_id}"
    log.info(f"Fetching {league_name} from {url} ...")

    # Use SOCKS5 proxy if configured (e.g. Tor on 127.0.0.1:9050 in CI)
    proxy = os.environ.get("SOCKS_PROXY")
    proxies = {"https": proxy, "http": proxy} if proxy else None

    last_err: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            with curl_requests.Session(impersonate="chrome", proxies=proxies) as session:
                resp = session.get(url, timeout=HTTP_TIMEOUT)
                resp.raise_for_status()

                return parse_fixtures(resp.text)
        except Exception as e:
            last_err = e
            if attempt < HTTP_RETRIES:
                wait = HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                log.warning(
                    f"Attempt {attempt}/{HTTP_RETRIES} failed: {e} "
                    f"— retrying in {wait}s"
                )
                time.sleep(wait)
            else:
                log.error(f"All {HTTP_RETRIES} attempts failed: {e}")

    raise last_err  # type: ignore[misc]


def parse_fixtures(html: str) -> list[Fixture]:
    """Parse the Full-Time fixtures table using CSS classes.

    Each data row has 10 cells:
      [0] type          (class: color-dark-grey bold cell-divider)
      [1] date+time     (class: left cell-divider) — e.g. "22/03/2610:00"
      [2] home team     (class: home-team)
      [3] home logo     (class: team-logo) — empty text
      [4] VS / score    (class: score)
      [5] away logo     (class: team-logo) — empty text
      [6] away team     (class: road-team)
      [7] venue         (class: left cell-divider)
      [8] competition   (class: left cell-divider)
      [9] status        (class: status-notes)
    """
    soup = BeautifulSoup(html, "html.parser")
    fixtures: list[Fixture] = []

    # Find the fixtures table — contains "Home Team" header
    tables = soup.find_all("table")
    fixture_table = None
    for t in tables:
        if t.find(string=re.compile(r"Home Team", re.I)):
            fixture_table = t
            break

    if not fixture_table:
        log.warning("No fixture table found — page structure may have changed.")
        return []

    # Parse data rows (skip header)
    for row in fixture_table.find_all("tr")[1:]:
        home_td = row.find("td", class_="home-team")
        away_td = row.find("td", class_="road-team")
        if not home_td or not away_td:
            continue

        home = clean_team_name(home_td.get_text(strip=True))
        away = clean_team_name(away_td.get_text(strip=True))
        if not home or not away:
            continue

        # Date+time: find the first cell containing a date pattern (DD/MM/YY).
        # Can't use class_="cell-divider" — the first cell-divider is the type
        # cell ("L"), not the date cell. Scanning for the pattern is more robust.
        date_str = ""
        time_str = ""
        for td in row.find_all("td"):
            cell_text = td.get_text(strip=True)
            dm = re.search(r"(\d{2}/\d{2}/\d{2})", cell_text)
            if dm:
                date_str = dm.group(1)
                tm = re.search(r"(\d{1,2}:\d{2})", cell_text)
                if tm:
                    time_str = tm.group(1)
                break

        # Venue and competition: cells after the away team
        venue = ""
        competition = ""
        for td in away_td.find_next_siblings("td"):
            classes = td.get("class", [])
            if "status-notes" in classes:
                break
            text = td.get_text(strip=True)
            if not text:
                continue
            if not venue:
                venue = text
            elif not competition:
                competition = text

        if date_str:
            fixtures.append(Fixture(
                date=date_str,
                time=time_str,
                home_team=home,
                away_team=away,
                venue=venue,
                division_label=competition or "Unknown Division",
            ))

    log.info(f"  Found {len(fixtures)} fixtures")
    return fixtures


def clean_team_name(name: str) -> str:
    """Normalise team names for use as filenames and calendar titles."""
    return re.sub(r"\s+", " ", name).strip()


def slug(name: str) -> str:
    """Convert a team name to a safe filename slug."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ---------------------------------------------------------------------------
# ICS generation
# ---------------------------------------------------------------------------

VCALENDAR_HEADER = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//YEL East Midlands//Fixture Scraper//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:{cal_name}
X-WR-CALDESC:Fixtures for {cal_name} — YEL East Midlands
X-WR-TIMEZONE:Europe/London
"""

VCALENDAR_FOOTER = "END:VCALENDAR\n"

VEVENT_TEMPLATE = """\
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART;TZID=Europe/London:{dtstart}
DTEND;TZID=Europe/London:{dtend}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{location}
END:VEVENT
"""


def parse_dt(date_str: str, time_str: str) -> datetime | None:
    """Parse a Full-Time date string into a datetime. Returns None on failure."""
    # Supports DD/MM/YY and DD/MM/YYYY
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(date_str.strip(), fmt)
            break
        except ValueError:
            continue
    else:
        log.warning(f"Could not parse date: '{date_str}'")
        return None

    if time_str and re.match(r"\d{1,2}:\d{2}", time_str):
        h, m = map(int, time_str.split(":"))
        return d.replace(hour=h, minute=m)
    else:
        # Default to 10:00 KO if no time listed (common for youth Sunday football)
        return d.replace(hour=10, minute=0)


def make_uid(fixture: Fixture) -> str:
    key = f"{fixture.date}|{fixture.home_team}|{fixture.away_team}"
    return hashlib.md5(key.encode()).hexdigest() + "@yel-calendar"


def fixtures_to_ics(team_name: str, fixtures: list[Fixture]) -> str:
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [VCALENDAR_HEADER.format(cal_name=team_name)]

    for f in fixtures:
        dt_start = parse_dt(f.date, f.time)
        if not dt_start:
            continue
        dt_end = dt_start.replace(hour=dt_start.hour + 1, minute=30)  # assume 90min slot
        is_home = f.home_team == team_name
        opponent = f.away_team if is_home else f.home_team
        home_away = "Home" if is_home else "Away"

        summary = f"{'⚽'} {team_name} vs {opponent} ({home_away})"
        description = (
            f"Division: {f.division_label}\\n"
            f"{f.home_team} v {f.away_team}\\n"
            f"KO: {f.time or 'TBC'}"
        )

        event = VEVENT_TEMPLATE.format(
            uid=make_uid(f),
            dtstamp=dtstamp,
            dtstart=dt_start.strftime("%Y%m%dT%H%M%S"),
            dtend=dt_end.strftime("%Y%m%dT%H%M%S"),
            summary=summary,
            description=description,
            location=f.venue or "",
        )
        lines.append(event)

    lines.append(VCALENDAR_FOOTER)
    return "".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    total_teams = 0
    for season_id, league_name in LEAGUES:
        try:
            fixtures = fetch_fixtures(season_id, league_name)
        except Exception as e:
            log.error(f"Failed to fetch {league_name}: {e}")
            continue

        if not fixtures:
            log.warning(f"No fixtures found for {league_name}")
            continue

        # Group by team name (appears as home or away)
        teams: dict[str, list[Fixture]] = {}
        for f in fixtures:
            for team in (f.home_team, f.away_team):
                if team:
                    teams.setdefault(team, []).append(f)

        league_dir = OUTPUT_DIR / slug(league_name)
        league_dir.mkdir(parents=True, exist_ok=True)

        log.info(f"  {len(teams)} teams, writing to {league_dir}/")

        for team_name, team_fixtures in sorted(teams.items()):
            ics_content = fixtures_to_ics(team_name, team_fixtures)
            filename = league_dir / f"{slug(team_name)}.ics"
            filename.write_text(ics_content, encoding="utf-8")
            log.info(f"    {filename.name} ({len(team_fixtures)} fixtures)")

        total_teams += len(teams)

    log.info(f"\nDone — {total_teams} team calendars written across {len(LEAGUES)} leagues")


if __name__ == "__main__":
    main()
