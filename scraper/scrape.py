"""
YEL East Midlands — Full-Time fixture scraper
Generates one .ics file per team and JSON feeds across all configured leagues/seasons.
"""

import json
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

logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format="%(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FIXTURES_URL = "https://fulltime.thefa.com/fixtures/1/100000.html"
RESULTS_URL = "https://fulltime.thefa.com/results/1/100000.html"

# Each league is identified by its selectedSeason parameter on Full-Time.
# Update these season IDs at the start of each new season.
LEAGUES: list[tuple[str, str]] = [
    ("909330396", "YEL East Midlands Sunday 25/26"),
    ("161954265", "YEL East Midlands Saturday 25/26"),
]

OUTPUT_DIR = Path(__file__).parent.parent / "calendars"
OUTPUT_DIR.mkdir(exist_ok=True)

FEEDS_DIR = Path(__file__).parent.parent / "feeds"
FEEDS_DIR.mkdir(exist_ok=True)

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


class Result(NamedTuple):
    date: str
    time: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    venue: str
    division_label: str


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _fetch_page(url: str, label: str) -> str:
    """Fetch a URL with retries and browser impersonation. Returns response text."""
    proxy = os.environ.get("SOCKS_PROXY")
    proxies = {"https": proxy, "http": proxy} if proxy else None

    last_err: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            with curl_requests.Session(impersonate="chrome", proxies=proxies) as session:
                resp = session.get(url, timeout=HTTP_TIMEOUT)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            last_err = e
            if attempt < HTTP_RETRIES:
                wait = HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                log.warning(
                    f"{label} attempt {attempt}/{HTTP_RETRIES} failed: {e} "
                    f"— retrying in {wait}s"
                )
                time.sleep(wait)
            else:
                log.error(f"{label} all {HTTP_RETRIES} attempts failed: {e}")

    raise last_err  # type: ignore[misc]


def fetch_fixtures(season_id: str, league_name: str) -> list[Fixture]:
    """Fetch all upcoming fixtures for a given season/league."""
    url = f"{FIXTURES_URL}?selectedSeason={season_id}&selectedFixtureGroupKey="
    log.info(f"Fetching fixtures for {league_name} ...")
    return parse_fixtures(_fetch_page(url, f"fixtures/{league_name}"))


def _fetch_page_js(url: str, label: str) -> str:
    """Fetch a JavaScript-rendered page using Playwright (headless Chromium).

    Waits for the results table to appear (up to 20 s) before returning the
    fully-rendered HTML.  Falls back to an empty string on any error so that
    callers can degrade gracefully.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
    except ImportError:
        log.error("playwright not installed — cannot fetch JS-rendered results page")
        return ""

    proxy = os.environ.get("SOCKS_PROXY")
    proxy_settings = None
    if proxy:
        # Playwright speaks socks5://, not the curl-style socks5h:// variant
        server = proxy.replace("socks5h://", "socks5://")
        proxy_settings = {"server": server}

    last_err: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    proxy=proxy_settings,
                )
                try:
                    context = browser.new_context()
                    # Pre-accept OneTrust consent as a belt-and-suspenders measure
                    context.add_cookies([
                        {
                            "name": "OptanonAlertBoxClosed",
                            "value": "2024-01-01T00:00:00.000Z",
                            "domain": "fulltime.thefa.com",
                            "path": "/",
                        },
                        {
                            "name": "OptanonConsent",
                            "value": "isGpcEnabled=0&datestamp=Mon+Jan+01+2024&version=202401.1.0&isIABGlobal=false&hosts=&consentId=scraper&interactionCount=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1",
                            "domain": "fulltime.thefa.com",
                            "path": "/",
                        },
                    ])
                    page = context.new_page()

                    # Block OneTrust's script-blocker so no data-loading scripts
                    # are suppressed while consent is being evaluated.
                    page.route("**/*OtAutoBlock*", lambda route: route.abort())
                    page.route("**/*otSDKStub*", lambda route: route.abort())

                    # Log every XHR/fetch request in DEBUG mode so we can see
                    # what data endpoints the page calls.
                    if log.isEnabledFor(logging.DEBUG):
                        def _log_req(req):
                            if req.resource_type in ("xhr", "fetch"):
                                log.debug(f"  XHR/fetch → {req.method} {req.url}")
                        page.on("request", _log_req)

                    page.goto(url, wait_until="networkidle", timeout=HTTP_TIMEOUT * 1000)
                    try:
                        page.wait_for_selector("td.home-team", timeout=30_000)
                    except PWTimeoutError:
                        log.warning(f"{label}: timed out waiting for td.home-team — returning partial HTML")
                    html = page.content()
                finally:
                    browser.close()
            return html
        except Exception as e:
            last_err = e
            if attempt < HTTP_RETRIES:
                wait = HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                log.warning(
                    f"{label} attempt {attempt}/{HTTP_RETRIES} failed: {e} "
                    f"— retrying in {wait}s"
                )
                time.sleep(wait)
            else:
                log.error(f"{label} all {HTTP_RETRIES} attempts failed: {e}")

    return ""


def fetch_results(season_id: str, league_name: str) -> list[Result]:
    """Fetch all results for a given season/league."""
    url = f"{RESULTS_URL}?selectedSeason={season_id}&selectedFixtureGroupKey="
    log.info(f"Fetching results for {league_name} ...")
    html = _fetch_page(url, f"results/{league_name}")
    log.debug(f"Results HTML length: {len(html)}, tables: {html.count('<table')}")
    return parse_results(html)


def _find_fixture_table(soup: BeautifulSoup, context: str) -> object | None:
    """Return the first table containing fixture/result rows.

    Tries two strategies:
    1. A table that has a "Home Team" header (fixtures page).
    2. A table that contains at least one cell with class "home-team" (results
       page may omit the header or use a different label).
    """
    tables = soup.find_all("table")
    # Strategy 1: header text
    for t in tables:
        if t.find(string=re.compile(r"Home Team", re.I)):
            return t
    # Strategy 2: data rows
    for t in tables:
        if t.find("td", class_="home-team"):
            return t
    log.warning(f"No fixture/result table found for {context} — page structure may have changed.")
    return None


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

    fixture_table = _find_fixture_table(soup, "fixtures")
    if not fixture_table:
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


def _parse_score(row) -> tuple[int, int] | None:
    """Extract (home_score, away_score) from a results row.

    Works with both <td> and <div> rows.  Accepts dash, en-dash, em-dash,
    and colon as separators (e.g. "2-1", "2 - 1", "2 : 1").
    Tries the dedicated .score / .score-col element first, then falls back
    to scanning every descendant.
    """
    score_re = re.compile(r"(\d+)\s*[-–—:]\s*(\d+)")

    # Preferred: any element whose class contains "score"
    score_el = row.find(True, class_=re.compile(r"\bscore\b"))
    if score_el:
        m = score_re.search(score_el.get_text(strip=True))
        if m:
            return int(m.group(1)), int(m.group(2))

    # Fallback: scan all descendant elements
    for el in row.find_all(True):
        text = el.get_text(strip=True)
        m = score_re.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))

    return None


def parse_results(html: str) -> list[Result]:
    """Parse the Full-Time results page.

    The results page renders rows as <div> elements with classes like
    "home-team-col" and "road-team-col".  Regex class matching picks up
    all variations (home-team, home-team-col, etc.).
    Header cells (text == "Home Team") are skipped automatically.
    """
    parser = "lxml" if _lxml_available() else "html.parser"
    log.info(f"  Parsing {len(html) // 1024}KB of results HTML with {parser} ...")
    soup = BeautifulSoup(html, parser)

    # Match any element whose class list contains a token starting with "home-team"
    home_cells = soup.find_all(True, class_=re.compile(r"\bhome-team"))
    # Strip header cells — they contain exactly the label text, not a team name
    home_cells = [
        c for c in home_cells
        if c.get_text(strip=True).lower() not in ("home team", "home", "")
    ]
    log.info(f"  home-team* elements (data rows): {len(home_cells)}")

    if not home_cells:
        idx = html.find("home-team")
        context = html[max(0, idx - 100):idx + 100] if idx != -1 else "<not found>"
        log.warning(f"  No home-team data cells found. Raw context: ...{context}...")
        return []

    first = home_cells[0]
    log.info(
        f"  First home cell: <{first.name} class={first.get('class')}> "
        f"parent=<{first.parent.name}> text={first.get_text(strip=True)!r}"
    )

    results: list[Result] = []
    seen: set[str] = set()

    for home_cell in home_cells:
        # Walk up to the nearest ancestor that also contains a road-team element
        row = home_cell.parent
        for _ in range(8):
            if row is None:
                break
            if row.find(True, class_=re.compile(r"\broad-team")):
                break
            row = getattr(row, "parent", None)

        if row is None:
            continue

        away_cell = row.find(True, class_=re.compile(r"\broad-team"))
        if not away_cell:
            continue
        # Skip header cells in away column too
        if away_cell.get_text(strip=True).lower() in ("away team", "road team", "away", ""):
            continue

        home = clean_team_name(home_cell.get_text(strip=True))
        away = clean_team_name(away_cell.get_text(strip=True))
        if not home or not away:
            continue

        score = _parse_score(row)
        if score is None:
            log.debug(f"No score for {home} v {away} — skipping (postponed?)")
            continue
        home_score, away_score = score

        date_str = ""
        time_str = ""
        for el in row.find_all(True):
            text = el.get_text(strip=True)
            dm = re.search(r"(\d{2}/\d{2}/\d{2})", text)
            if dm:
                date_str = dm.group(1)
                tm = re.search(r"(\d{1,2}:\d{2})", text)
                if tm:
                    time_str = tm.group(1)
                break

        venue = ""
        competition = ""
        for el in away_cell.find_next_siblings():
            classes = " ".join(el.get("class", []))
            if "status" in classes:
                break
            text = el.get_text(strip=True)
            if not text:
                continue
            if not venue:
                venue = text
            elif not competition:
                competition = text
                break

        if not date_str:
            continue

        key = f"{date_str}|{home}|{away}"
        if key in seen:
            continue
        seen.add(key)

        results.append(Result(
            date=date_str,
            time=time_str,
            home_team=home,
            away_team=away,
            home_score=home_score,
            away_score=away_score,
            venue=venue,
            division_label=competition or "Unknown Division",
        ))

    log.info(f"  Found {len(results)} results")
    return results


def _lxml_available() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False


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
# JSON feed generation
# ---------------------------------------------------------------------------

def fixture_to_iso_date(date_str: str) -> str:
    """Convert DD/MM/YY or DD/MM/YYYY to ISO 8601 YYYY-MM-DD. Returns raw string on failure."""
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def fixture_to_dict(fixture: Fixture) -> dict:
    """Serialise a Fixture to a plain dict for JSON output."""
    return {
        "id": hashlib.md5(f"{fixture.date}|{fixture.home_team}|{fixture.away_team}".encode()).hexdigest(),
        "date": fixture_to_iso_date(fixture.date),
        "time": fixture.time or "10:00",
        "home_team": fixture.home_team,
        "away_team": fixture.away_team,
        "venue": fixture.venue,
        "division": fixture.division_label,
    }


def result_to_dict(result: Result) -> dict:
    """Serialise a Result to a plain dict for JSON output."""
    return {
        "id": hashlib.md5(f"{result.date}|{result.home_team}|{result.away_team}".encode()).hexdigest(),
        "date": fixture_to_iso_date(result.date),
        "time": result.time or "10:00",
        "home_team": result.home_team,
        "away_team": result.away_team,
        "home_score": result.home_score,
        "away_score": result.away_score,
        "venue": result.venue,
        "division": result.division_label,
    }


def write_league_feed(
    league_name: str,
    league_slug: str,
    fixtures: list[Fixture],
    results: list[Result],
    generated: str,
) -> None:
    """Write fixtures.json and results.json for a league."""
    league_dir = FEEDS_DIR / league_slug
    league_dir.mkdir(parents=True, exist_ok=True)

    fixtures_payload = {
        "league": league_name,
        "generated": generated,
        "fixtures": sorted(
            [fixture_to_dict(f) for f in fixtures],
            key=lambda x: (x["date"], x["time"]),
        ),
    }
    out_f = league_dir / "fixtures.json"
    out_f.write_text(json.dumps(fixtures_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"  Written {out_f} ({len(fixtures)} fixtures)")

    results_payload = {
        "league": league_name,
        "generated": generated,
        "results": sorted(
            [result_to_dict(r) for r in results],
            key=lambda x: (x["date"], x["time"]),
            reverse=True,  # most recent first
        ),
    }
    out_r = league_dir / "results.json"
    out_r.write_text(json.dumps(results_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"  Written {out_r} ({len(results)} results)")


def write_team_feed(
    team_name: str,
    team_slug: str,
    league_name: str,
    league_slug: str,
    fixtures: list[Fixture],
    results: list[Result],
    generated: str,
) -> None:
    """Write a JSON file with fixtures and results relevant to a single team."""
    team_dir = FEEDS_DIR / league_slug / "teams"
    team_dir.mkdir(parents=True, exist_ok=True)

    team_fixtures = []
    for f in fixtures:
        is_home = f.home_team == team_name
        d = fixture_to_dict(f)
        d["home_away"] = "home" if is_home else "away"
        d["opponent"] = f.away_team if is_home else f.home_team
        team_fixtures.append(d)
    team_fixtures.sort(key=lambda x: (x["date"], x["time"]))

    team_results = []
    for r in results:
        is_home = r.home_team == team_name
        d = result_to_dict(r)
        d["home_away"] = "home" if is_home else "away"
        d["opponent"] = r.away_team if is_home else r.home_team
        d["goals_for"] = r.home_score if is_home else r.away_score
        d["goals_against"] = r.away_score if is_home else r.home_score
        team_results.append(d)
    team_results.sort(key=lambda x: (x["date"], x["time"]), reverse=True)

    payload = {
        "team": team_name,
        "league": league_name,
        "generated": generated,
        "fixtures": team_fixtures,
        "results": team_results,
    }
    out = team_dir / f"{team_slug}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def infer_club_name(team_name: str, prefix_counts: dict[str, int]) -> str:
    """Return the inferred club name for a team using pre-computed prefix counts.

    Algorithm: strip the age-group suffix (U7–U21), then find the *shortest*
    word-prefix (≥ 2 words) that is shared by at least 2 teams.  Shortest-first
    prevents over-splitting (e.g. 'Arnold Town Maroon' beats 'Arnold Town').
    If no shared prefix exists, return the stripped name as-is (singleton club).
    """
    stripped = re.sub(r"\s+U\d{1,2}$", "", team_name, flags=re.IGNORECASE).strip()
    words = stripped.split()
    for length in range(2, len(words) + 1):
        prefix = " ".join(words[:length])
        if prefix_counts.get(prefix, 0) >= 2:
            return prefix
    return stripped


def build_prefix_counts(team_names: list[str]) -> dict[str, int]:
    """Count how many team names share each word-prefix (≥ 2 words, age group stripped)."""
    counts: dict[str, int] = {}
    for name in team_names:
        stripped = re.sub(r"\s+U\d{1,2}$", "", name, flags=re.IGNORECASE).strip()
        words = stripped.split()
        for length in range(2, len(words) + 1):
            prefix = " ".join(words[:length])
            counts[prefix] = counts.get(prefix, 0) + 1
    return counts


def write_club_feed(
    club_name: str,
    club_slug: str,
    team_fixtures: list[dict],
    team_results: list[dict],
    generated: str,
) -> None:
    """Write feeds/clubs/<slug>.json aggregating all teams in a club across leagues."""
    clubs_dir = FEEDS_DIR / "clubs"
    clubs_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "club": club_name,
        "generated": generated,
        "fixtures": sorted(team_fixtures, key=lambda x: (x["date"], x["time"])),
        "results": sorted(team_results, key=lambda x: (x["date"], x["time"]), reverse=True),
    }
    out = clubs_dir / f"{club_slug}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_index(league_entries: list[dict], club_entries: list[dict], generated: str) -> None:
    """Write a top-level index.json listing all leagues, teams, and clubs."""
    payload = {
        "generated": generated,
        "leagues": league_entries,
        "clubs": club_entries,
    }
    out = FEEDS_DIR / "index.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"  Written {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_teams = 0
    index_leagues: list[dict] = []

    # Accumulate all team fixture/result dicts across leagues for club-level grouping.
    all_team_fixture_rows: list[dict] = []
    all_team_result_rows: list[dict] = []
    all_team_names: list[str] = []

    for season_id, league_name in LEAGUES:
        try:
            fixtures = fetch_fixtures(season_id, league_name)
        except Exception as e:
            log.error(f"Failed to fetch fixtures for {league_name}: {e}")
            fixtures = []

        try:
            results = fetch_results(season_id, league_name)
        except Exception as e:
            log.error(f"Failed to fetch results for {league_name}: {e}")
            results = []

        if not fixtures and not results:
            log.warning(f"No data found for {league_name}")
            continue

        # Group fixtures/results by team name
        teams_fixtures: dict[str, list[Fixture]] = {}
        for f in fixtures:
            for team in (f.home_team, f.away_team):
                if team:
                    teams_fixtures.setdefault(team, []).append(f)

        teams_results: dict[str, list[Result]] = {}
        for r in results:
            for team in (r.home_team, r.away_team):
                if team:
                    teams_results.setdefault(team, []).append(r)

        all_teams = sorted(set(teams_fixtures) | set(teams_results))

        league_slug_name = slug(league_name)
        league_dir = OUTPUT_DIR / league_slug_name
        league_dir.mkdir(parents=True, exist_ok=True)

        log.info(f"  {len(all_teams)} teams, writing to {league_dir}/")

        # --- ICS calendars (fixtures only) ---
        for team_name in all_teams:
            team_fixtures = teams_fixtures.get(team_name, [])
            if team_fixtures:
                ics_content = fixtures_to_ics(team_name, team_fixtures)
                filename = league_dir / f"{slug(team_name)}.ics"
                filename.write_text(ics_content, encoding="utf-8")
                log.info(f"    {filename.name} ({len(team_fixtures)} fixtures)")

        # --- JSON feeds (league + team level) ---
        write_league_feed(league_name, league_slug_name, fixtures, results, generated)

        team_index_entries: list[dict] = []
        for team_name in all_teams:
            team_slug_name = slug(team_name)
            write_team_feed(
                team_name, team_slug_name, league_name, league_slug_name,
                teams_fixtures.get(team_name, []),
                teams_results.get(team_name, []),
                generated,
            )
            team_index_entries.append({"name": team_name, "slug": team_slug_name})

            # Collect enriched dicts for club-level aggregation
            all_team_names.append(team_name)
            for f in teams_fixtures.get(team_name, []):
                is_home = f.home_team == team_name
                d = fixture_to_dict(f)
                d["league"] = league_name
                d["team"] = team_name
                d["home_away"] = "home" if is_home else "away"
                d["opponent"] = f.away_team if is_home else f.home_team
                all_team_fixture_rows.append(d)

            for r in teams_results.get(team_name, []):
                is_home = r.home_team == team_name
                d = result_to_dict(r)
                d["league"] = league_name
                d["team"] = team_name
                d["home_away"] = "home" if is_home else "away"
                d["opponent"] = r.away_team if is_home else r.home_team
                d["goals_for"] = r.home_score if is_home else r.away_score
                d["goals_against"] = r.away_score if is_home else r.home_score
                all_team_result_rows.append(d)

        index_leagues.append({
            "name": league_name,
            "slug": league_slug_name,
            "teams": team_index_entries,
        })

        total_teams += len(all_teams)

    # --- JSON feeds (club level) ---
    prefix_counts = build_prefix_counts(all_team_names)

    club_fixtures: dict[str, list[dict]] = {}
    for row in all_team_fixture_rows:
        club_name = infer_club_name(row["team"], prefix_counts)
        club_fixtures.setdefault(club_name, []).append(row)

    club_results: dict[str, list[dict]] = {}
    for row in all_team_result_rows:
        club_name = infer_club_name(row["team"], prefix_counts)
        club_results.setdefault(club_name, []).append(row)

    all_clubs = sorted(set(club_fixtures) | set(club_results))

    index_clubs: list[dict] = []
    for club_name in all_clubs:
        club_slug_name = slug(club_name)
        write_club_feed(
            club_name, club_slug_name,
            club_fixtures.get(club_name, []),
            club_results.get(club_name, []),
            generated,
        )
        teams_in_club = sorted(
            {r["team"] for r in club_fixtures.get(club_name, [])}
            | {r["team"] for r in club_results.get(club_name, [])}
        )
        index_clubs.append({
            "name": club_name,
            "slug": club_slug_name,
            "teams": teams_in_club,
        })
        log.info(f"  Club feed: {club_slug_name} ({len(teams_in_club)} teams)")

    write_index(index_leagues, index_clubs, generated)
    log.info(
        f"\nDone — {total_teams} team calendars, {len(index_clubs)} club feeds, "
        f"JSON feeds written across {len(LEAGUES)} leagues"
    )


if __name__ == "__main__":
    main()
