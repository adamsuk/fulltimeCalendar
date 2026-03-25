import type { AppData, BantamsFeed } from './types';

const BASE = 'data/';
const BANTAMS_FEED_URL =
  'https://raw.githubusercontent.com/adamsuk/fulltimeCalendar/main/feeds/clubs/east-leake.json';

async function load<T>(file: string): Promise<T> {
  const res = await fetch(BASE + file);
  if (!res.ok) throw new Error(`Failed to load ${file}: ${res.status}`);
  return res.json() as Promise<T>;
}

async function loadBantamsFeed(): Promise<BantamsFeed | null> {
  try {
    const res = await fetch(BANTAMS_FEED_URL);
    if (!res.ok) return null;
    return res.json() as Promise<BantamsFeed>;
  } catch {
    return null;
  }
}

export async function loadAllData(): Promise<AppData> {
  const [club, teams, committee, registration, news, fixtures, gallery, matchday, bantamsFeed] =
    await Promise.all([
      load('club.json'),
      load('teams.json'),
      load('committee.json'),
      load('registration.json'),
      load('news.json'),
      load('fixtures.json'),
      load('gallery.json'),
      load('matchday.json'),
      loadBantamsFeed(),
    ]);

  return { club, teams, committee, registration, news, fixtures, gallery, matchday, bantamsFeed } as AppData;
}
