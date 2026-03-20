# YEL East Midlands Sunday League — Fixture Calendars

Automatically scrapes fixture data from [FA Full-Time](https://fulltime.thefa.com) and generates one `.ics` calendar file per team across all age groups. Updated daily via GitHub Actions.

## Subscribing to a team calendar

1. Find your team's `.ics` file in the `calendars/` folder
2. Click on it in GitHub, then click **Raw** — copy that URL
3. In Google Calendar: **+ Other calendars → From URL** → paste the raw URL

The calendar will auto-refresh (Google typically polls every 12–24 hours).

> **Tip:** The raw URL looks like:
> `https://raw.githubusercontent.com/adamsuk/fulltimeCalendar/main/calendars/eastwood-athletic-atalanta-u10.ics`

## How it works

The scraper fetches all fixtures in a single request from Full-Time's fixtures page (`/fixtures/1/100000.html`), which automatically uses the current season and includes every age group. No manual configuration of seasons or age groups is needed — new teams and divisions appear automatically as Full-Time updates.

Each fixture row provides the date, time, home/away teams, venue, and competition (division) name. The scraper generates a separate `.ics` file per team containing all their home and away fixtures.

## Running locally

```bash
pip install curl-cffi beautifulsoup4
python scraper/scrape.py
# .ics files are written to ./calendars/
```

## Scheduling

The GitHub Actions workflow runs daily at 06:00 UTC. You can also trigger it manually from the **Actions** tab.

## Notes

- Kick-off times default to **10:00** if Full-Time doesn't list a time (common for youth Sunday football)
- Event duration is set to **90 minutes**
- Team names are taken verbatim from Full-Time
- The scraper uses `curl-cffi` with browser impersonation to fetch the page reliably
