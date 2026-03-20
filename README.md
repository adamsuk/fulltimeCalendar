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

## Adding more age groups

Edit `scraper/scrape.py` and add entries to the `AGE_GROUPS` list:

```python
AGE_GROUPS: list[tuple[str, str]] = [
    ("13", "U10s"),
    ("14", "U11s"),  # add more here
]
```

**To find the age group ID:**
1. Go to [Full-Time](https://fulltime.thefa.com) and navigate to an age group's fixture page
2. Copy the URL — it will look like:
   ```
   https://fulltime.thefa.com/fixtures.html?selectedSeason=909330396
     &selectedFixtureGroupAgeGroup=XX&...
   ```
3. Extract the `selectedFixtureGroupAgeGroup` value (e.g. `13` for U10s, `14` for U11s)

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
