export interface ClubAddress {
  line1: string;
  line2: string;
  postcode: string;
}

export interface ClubSocials {
  facebook: string;
  instagram: string;
  twitter: string;
}

export interface AboutItem {
  icon: string;
  title: string;
  text: string;
}

export interface Club {
  name: string;
  tagline: string;
  founded: number;
  email: string;
  address: ClubAddress;
  what3words: string;
  socials: ClubSocials;
  about: AboutItem[];
  history: string[];
}

export interface Team {
  name: string;
  description: string;
  photo?: string;
  manager: string;
  coach: string;
  contact: string;
  managerLabel?: string;
  coachLabel?: string;
}

export interface TeamSection {
  name: string;
  subtitle: string;
  icon: string;
  teams: Team[];
}

export interface TeamsData {
  sections: TeamSection[];
}

export interface CommitteeMember {
  role: string;
  name: string;
  contact: string;
}

export interface CommitteeData {
  committee: CommitteeMember[];
}

export interface RegistrationItem {
  icon: string;
  title: string;
  description: string;
  link: string;
  buttonText: string;
}

export interface NewsItem {
  title: string;
  text: string;
  body?: string;
  link: string;
  linkText: string;
}

export interface GalleryItem {
  src?: string;
  caption: string;
}

export interface MatchdayItem {
  icon: string;
  title: string;
  text: string;
}

export interface Fixture {
  competition: string;
  homeTeam: string;
  awayTeam: string;
  date: string;
  kickoff: string;
  venue: string;
}

export interface FixturesData {
  next: Fixture;
}

export interface BantamsFixture {
  id: string;
  date: string;
  time: string;
  home_team: string;
  away_team: string;
  venue: string;
  division: string;
  league: string;
  team: string;
  home_away: 'home' | 'away';
  opponent: string;
}

export interface BantamsResult {
  id: string;
  date: string;
  time: string;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  venue: string;
  division: string;
  league: string;
  team: string;
  home_away: 'home' | 'away';
  opponent: string;
  goals_for: number | null;
  goals_against: number | null;
}

export interface BantamsFeed {
  club: string;
  generated: string;
  fixtures: BantamsFixture[];
  results: BantamsResult[];
}

export interface AppData {
  club: Club;
  teams: TeamsData;
  committee: CommitteeData;
  registration: RegistrationItem[];
  news: NewsItem[];
  fixtures: FixturesData;
  gallery: GalleryItem[];
  matchday: MatchdayItem[];
  bantamsFeed: BantamsFeed | null;
}
