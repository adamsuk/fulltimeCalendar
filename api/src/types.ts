// Matches the structure of feeds/index.json

export interface TeamRef {
  name: string;
  slug: string;
}

export interface LeagueRef {
  name: string;
  slug: string;
  teams: TeamRef[];
}

export interface ClubRef {
  name: string;
  slug: string;
  teams: string[]; // raw team names (not slugged)
}

export interface Index {
  generated: string;
  leagues: LeagueRef[];
  clubs: ClubRef[];
}

// Matches feeds/:league/fixtures.json and results.json

export interface Fixture {
  id: string;
  date: string;       // ISO date YYYY-MM-DD
  time: string;       // HH:MM
  home_team: string;
  away_team: string;
  venue: string;
  division: string;
}

export interface Result extends Fixture {
  home_score: number | null;
  away_score: number | null;
}

export interface LeagueFixtureFeed {
  league: string;
  generated: string;
  fixtures: Fixture[];
}

export interface LeagueResultFeed {
  league: string;
  generated: string;
  results: Result[];
}

// Matches feeds/:league/teams/:team.json

export interface TeamFixture extends Fixture {
  home_away: "home" | "away";
  opponent: string;
}

export interface TeamResult extends Result {
  home_away: "home" | "away";
  opponent: string;
  goals_for: number | null;
  goals_against: number | null;
}

export interface TeamFeed {
  team: string;
  league: string;
  generated: string;
  fixtures: TeamFixture[];
  results: TeamResult[];
}

// Matches feeds/clubs/:club.json

export interface ClubFixture extends Fixture {
  league: string;
  team: string;
  home_away: "home" | "away";
  opponent: string;
}

export interface ClubResult extends Result {
  league: string;
  team: string;
  home_away: "home" | "away";
  opponent: string;
  goals_for: number | null;
  goals_against: number | null;
}

export interface ClubFeed {
  club: string;
  generated: string;
  fixtures: ClubFixture[];
  results: ClubResult[];
}

// Cloudflare Worker bindings

export interface Env {
  GITHUB_REPO: string;
  GITHUB_BRANCH: string;
  GITHUB_TOKEN?: string;
}
