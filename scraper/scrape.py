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
    date: str          # e.g. "Sunday, 19 January 2025"
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

                # Debug: log response info to diagnose CI parsing issues
                html = resp.text
                log.info(f"  Response status: {resp.status_code}, length: {len(html)} chars")
                if len(html) < 5000:
                    log.info(f"  Full response:\n{html}")
                else:
                    log.info(f"  First 2000 chars:\n{html[:2000]}")

                return parse_fixtures(html, label)
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
    soup = BeautifulSoup(html, "html.parser")
    fixtures: list[Fixture] = []

    # Full-Time wraps each fixture date block in a <div class="fixture-date-group">
    # or similar. The actual structure uses a table with alternating date headers
    # and fixture rows. We walk all rows and track the current date.

    current_date = ""
    current_time = ""

    # Debug: log page structure to understand HTML layout
    tables = soup.find_all("table")
    log.info(f"  Tables found: {len(tables)}")
    for i, t in enumerate(tables):
        classes = t.get("class", [])
        tid = t.get("id", "")
        first_text = t.get_text(strip=True)[:150]
        log.info(f"    Table {i}: class={classes} id={tid!r} preview={first_text!r}")

    # Also look for common fixture container patterns
    for selector in ["div.fixtures", "div#fixtures", "[class*=fixture]", "[id*=fixture]"]:
        found = soup.select(selector)
        if found:
            log.info(f"  Selector {selector!r}: {len(found)} matches")
            for f in found[:3]:
                log.info(f"    tag={f.name} class={f.get('class')} text={f.get_text(strip=True)[:200]!r}")

    # Look for "Home Team" text anywhere in the page
    home_team_els = soup.find_all(string=re.compile(r"Home Team", re.I))
    log.info(f"  'Home Team' text occurrences: {len(home_team_els)}")
    for el in home_team_els[:3]:
        parent = el.parent
        log.info(f"    parent tag={parent.name if parent else None} class={parent.get('class') if parent else None}")

    # Find the main fixtures table — it has class "fixture-list" or sits inside
    # div#fixtures-results or similar. We look for any table containing "Home Team".
    fixture_table = None
    for t in tables:
        if t.find(string=re.compile(r"Home Team", re.I)):
            fixture_table = t
            break

    if not fixture_table:
        # Fallback: some Full-Time pages use a list structure
        log.warning(f"No fixture table found for {division_label} — page structure may have changed.")
        return []

    rows = fixture_table.find_all("tr")

    for row in rows:
        cells = row.find_all(["td", "th"])
        text_cells = [c.get_text(strip=True) for c in cells]

        if not text_cells:
            continue

        # Date header rows typically have a single cell with a date pattern
        date_match = re.search(
            r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\d{1,2}\s+\w+\s+\d{4}",
            " ".join(text_cells),
            re.I,
        )
        if date_match:
            current_date = date_match.group(0).strip()
            # Time often appears in the same row, e.g. "10:00"
            time_match = re.search(r"\b(\d{1,2}:\d{2})\b", " ".join(text_cells))
            current_time = time_match.group(1) if time_match else ""
            continue

        # Fixture rows: we expect at least home team, score/vs, away team
        # Typical column order: Date | Time | Home Team | Score | Away Team | Venue
        # Sometimes Date/Time are in the date-header row above, not per-fixture
        if len(text_cells) >= 3:
            # Try to identify home/away from position
            # Full-Time puts: [date?] [time?] [home] [v / score] [away] [venue?]
            # Strip empty cells
            non_empty = [(i, c) for i, c in enumerate(text_cells) if c]

            # Look for a "v" or score separator
            vs_idx = None
            for i, (orig_i, c) in enumerate(non_empty):
                if re.match(r"^(v|vs|\d+-\d+)$", c, re.I):
                    vs_idx = i
                    break

            if vs_idx is not None and vs_idx > 0 and vs_idx < len(non_empty) - 1:
                # Check if first cell is a time
                maybe_time = non_empty[0][1]
                offset = 0
                if re.match(r"^\d{1,2}:\d{2}$", maybe_time):
                    current_time = maybe_time
                    offset = 1

                home = non_empty[vs_idx - 1][1] if vs_idx - 1 >= offset else ""
                away = non_empty[vs_idx + 1][1] if vs_idx + 1 < len(non_empty) else ""
                venue = non_empty[vs_idx + 2][1] if vs_idx + 2 < len(non_empty) else ""

                if home and away and current_date:
                    fixtures.append(Fixture(
                        date=current_date,
                        time=current_time,
                        home_team=clean_team_name(home),
                        away_team=clean_team_name(away),
                        venue=venue,
                        division_label=division_label,
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
    # e.g. "Sunday, 19 January 2025" + "10:00"
    clean = re.sub(r"^[A-Za-z]+,\s*", "", date_str).strip()  # remove weekday
    fmt_date = "%d %B %Y"
    try:
        d = datetime.strptime(clean, fmt_date)
    except ValueError:
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
