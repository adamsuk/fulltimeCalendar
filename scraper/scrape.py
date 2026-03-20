"""
YEL East Midlands Sunday League — Full-Time fixture scraper
Generates one .ics file per team across all configured divisions.
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
# Config — add/remove age groups here. To find the age group ID go to
# Full-Time, navigate to the league fixtures page and copy the URL.
#
# How to find age group IDs:
#   1. Go to https://fulltime.thefa.com
#   2. Search for "YEL East Midlands Sunday"
#   3. Browse to an age group's fixture page
#   4. Copy the URL and extract the `selectedFixtureGroupAgeGroup` value
# ---------------------------------------------------------------------------

BASE_URL = "https://fulltime.thefa.com/fixtures.html"

SEASON_ID = "909330396"

# Maximum fixtures to request per age group in a single page
MAX_ITEMS_PER_PAGE = "100000"

# Each entry is (age_group_id, human_label)
# age_group_id 13 = U10s. Add more rows as you find other age group IDs.
AGE_GROUPS: list[tuple[str, str]] = [
    ("13", "U10s"),
    # ("14", "U11s"),  # <-- add more here
]

OUTPUT_DIR = Path(__file__).parent.parent / "calendars"
OUTPUT_DIR.mkdir(exist_ok=True)

# How long to wait between division page requests (be polite to the FA servers)
REQUEST_DELAY_SECONDS = 2

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

def fetch_age_group(age_group_id: str, label: str) -> list[Fixture]:
    params = {
        "selectedSeason": SEASON_ID,
        "selectedFixtureGroupAgeGroup": age_group_id,
        "selectedFixtureGroupKey": "",
        "selectedDateCode": "all",
        "selectedClub": "",
        "selectedTeam": "",
        "selectedRelatedFixtureOption": "1",
        "selectedFixtureDateStatus": "",
        "selectedFixtureStatus": "",
        "previousSelectedFixtureGroupAgeGroup": age_group_id,
        "previousSelectedFixtureGroupKey": "",
        "previousSelectedClub": "",
        "itemsPerPage": MAX_ITEMS_PER_PAGE,
    }

    log.info(f"Fetching {label} ...")

    # Use SOCKS5 proxy if configured (e.g. Tor on 127.0.0.1:9050 in CI)
    proxy = os.environ.get("SOCKS_PROXY")
    proxies = {"https": proxy, "http": proxy} if proxy else None

    last_err: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            with curl_requests.Session(impersonate="chrome", proxies=proxies) as session:
                resp = session.get(BASE_URL, params=params, timeout=HTTP_TIMEOUT)
                resp.raise_for_status()

                return parse_fixtures(resp.text, label)
        except Exception as e:
            last_err = e
            if attempt < HTTP_RETRIES:
                wait = HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                log.warning(
                    f"Attempt {attempt}/{HTTP_RETRIES} for {label} failed: {e} "
                    f"— retrying in {wait}s"
                )
                time.sleep(wait)
            else:
                log.error(f"All {HTTP_RETRIES} attempts for {label} failed: {e}")

    raise last_err  # type: ignore[misc]


def parse_fixtures(html: str, division_label: str) -> list[Fixture]:
    """Parse the Full-Time fixtures table.

    Header columns (7):
      Type | Date / Time | Home Team | Away Team | Venue | Competition | Status
    Data row cells (9) — date/time split + VS column inserted:
      Type | Date | Time | Home Team | VS | Away Team | Venue | Competition | Status

    We anchor on the VS/score cell in each data row to reliably find
    home (before VS) and away (after VS), then grab venue/competition
    from subsequent cells.
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
        log.warning(f"No fixture table found for {division_label} — page structure may have changed.")
        return []

    # Parse data rows (skip header)
    for row in fixture_table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        text = [c.get_text(strip=True) for c in cells]

        if len(text) < 6:
            continue

        # Find the VS / score separator cell
        vs_idx = None
        for i, val in enumerate(text):
            if re.match(r"^(v|vs|\d+-\d+)$", val, re.I):
                vs_idx = i
                break

        if vs_idx is None or vs_idx < 2:
            continue

        home = clean_team_name(text[vs_idx - 1])
        away = clean_team_name(text[vs_idx + 1]) if vs_idx + 1 < len(text) else ""

        if not home or not away:
            continue

        # Cells before home team contain type, date, and optionally time
        pre_cells = text[:vs_idx - 1]

        # Extract date (DD/MM/YY or DD/MM/YYYY) and time (HH:MM) from pre-cells
        date_str = ""
        time_str = ""
        for cell in pre_cells:
            if not date_str:
                dm = re.search(r"(\d{2}/\d{2}/\d{2,4})", cell)
                if dm:
                    date_str = dm.group(1)
            if not time_str:
                tm = re.match(r"^(\d{1,2}:\d{2})$", cell)
                if tm:
                    time_str = tm.group(1)

        # Cells after away team: venue, competition, status
        post_cells = text[vs_idx + 2:]
        venue = post_cells[0] if len(post_cells) > 0 else ""
        competition = post_cells[1] if len(post_cells) > 1 else ""

        label = competition if competition else division_label

        if date_str:
            fixtures.append(Fixture(
                date=date_str,
                time=time_str,
                home_team=home,
                away_team=away,
                venue=venue,
                division_label=label,
            ))

    log.info(f"  Found {len(fixtures)} fixtures in {division_label}")
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
PRODID:-//YEL East Midlands Sunday League//Fixture Scraper//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:{cal_name}
X-WR-CALDESC:Fixtures for {cal_name} — YEL East Midlands Sunday League
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
    all_fixtures: list[Fixture] = []

    for age_group_id, label in AGE_GROUPS:
        try:
            fixtures = fetch_age_group(age_group_id, label)
            all_fixtures.extend(fixtures)
        except Exception as e:
            log.error(f"Failed to fetch {label}: {e}")
        time.sleep(REQUEST_DELAY_SECONDS)

    if not all_fixtures:
        log.warning("No fixtures found — check division config and page structure.")
        return

    # Group by team name (appears as home or away)
    teams: dict[str, list[Fixture]] = {}
    for f in all_fixtures:
        for team in (f.home_team, f.away_team):
            if team:
                teams.setdefault(team, []).append(f)

    log.info(f"\nFound {len(teams)} teams across {len(all_fixtures)} fixtures")

    for team_name, team_fixtures in sorted(teams.items()):
        ics_content = fixtures_to_ics(team_name, team_fixtures)
        filename = OUTPUT_DIR / f"{slug(team_name)}.ics"
        filename.write_text(ics_content, encoding="utf-8")
        log.info(f"  Written {filename.name} ({len(team_fixtures)} fixtures)")

    log.info(f"\nDone — {len(teams)} .ics files written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
