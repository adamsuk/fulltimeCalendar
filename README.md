# YEL East Midlands Sunday League — Fixture Calendars

Automatically scrapes fixture data from [FA Full-Time](https://fulltime.thefa.com) and generates one `.ics` calendar file per team. Updated daily via GitHub Actions.

## Subscribing to a team calendar

1. Find your team's `.ics` file in the `calendars/` folder
2. Click on it in GitHub, then click **Raw** — copy that URL
3. In Google Calendar: **+ Other calendars → From URL** → paste the raw URL

The calendar will auto-refresh (Google typically polls every 12–24 hours).

> **Tip:** The raw URL looks like:
> `https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/calendars/elb-u10s-oranges.ics`

---

## Adding more divisions

Edit `scraper/scrape.py` and add entries to the `DIVISIONS` list:

```python
DIVISIONS: list[tuple[str, str, str, str]] = [
    ("13", "275110081", "1_943772434", "U10s Div 1"),
    ("14", "XXXXXXXXX", "1_XXXXXXXXX", "U11s Div 1"),  # add more here
]
```

**To find the parameters for a division:**
1. Go to [Full-Time](https://fulltime.thefa.com) and navigate to the division's fixture page
2. Copy the URL — it will look like:
   ```
   https://fulltime.thefa.com/fixtures.html?league=515215211&selectedSeason=909330396
     &selectedFixtureGroupAgeGroup=XX&selectedDivision=XXXXXXXXX
     &selectedFixtureGroupKey=1_XXXXXXXXX
   ```
3. Extract `selectedFixtureGroupAgeGroup`, `selectedDivision`, and `selectedFixtureGroupKey`

---

## Running locally

```bash
pip install requests beautifulsoup4
python scraper/scrape.py
# .ics files are written to ./calendars/
```

## Scheduling

The GitHub Actions workflow runs daily at 06:00 UTC. You can also trigger it manually from the **Actions** tab in your repo.

---

## Notes

- Kick-off times default to **10:00** if Full-Time doesn't list a time (common for youth Sunday football)
- Event duration is set to **90 minutes** — adjust `dt_end` in `scrape.py` if needed
- Team names are taken verbatim from Full-Time, so they'll match however the league has registered them
