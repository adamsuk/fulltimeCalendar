# YEL East Midlands — Fixture Calendars

Automatically scrapes fixture data from [FA Full-Time](https://fulltime.thefa.com) and generates one `.ics` calendar file per team across both Saturday and Sunday leagues. Updated daily via GitHub Actions.

## Subscribing to a team calendar

1. Find your team's `.ics` file in the `calendars/` folder
2. Click on it in GitHub, then click **Raw** — copy that URL
3. In Google Calendar: **+ Other calendars → From URL** → paste the raw URL

The calendar will auto-refresh (Google typically polls every 12–24 hours).

> **Tip:** The raw URL looks like:
> `https://raw.githubusercontent.com/adamsuk/fulltimeCalendar/main/calendars/eastwood-athletic-atalanta-u10.ics`

## How it works

The scraper fetches fixtures from Full-Time for each configured league. Leagues are identified by their `selectedSeason` parameter. All age groups within each league are included automatically.

Currently configured leagues:

| League | Season ID |
|---|---|
| YEL East Midlands Sunday 25/26 | `909330396` |
| YEL East Midlands Saturday 25/26 | `161954265` |

## Updating for a new season

At the start of each season, update the `LEAGUES` list in `scraper/scrape.py` with the new season IDs:

1. Go to [Full-Time](https://fulltime.thefa.com) and navigate to the league's fixture page
2. Copy the `selectedSeason` value from the URL
3. Update the ID in the `LEAGUES` list

## Running locally

```bash
pip install curl-cffi beautifulsoup4
python scraper/scrape.py
# .ics files are written to ./calendars/
```

## Scheduling

The GitHub Actions workflow runs daily at 06:00 UTC. You can also trigger it manually from the **Actions** tab.

## Notes

- Kick-off times default to **10:00** if Full-Time doesn't list a time
- Event duration is set to **90 minutes**
- Team names are taken verbatim from Full-Time
- The scraper uses `curl-cffi` with browser impersonation to fetch the page reliably
- If a team plays in both Saturday and Sunday leagues, all fixtures appear in one calendar
