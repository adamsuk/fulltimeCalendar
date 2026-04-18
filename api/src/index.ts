import { Hono } from "hono";
import { cors } from "hono/cors";
import { fetchFeed, slugify, NotFoundError, UpstreamError } from "./data";
import type {
  Env,
  Index,
  ClubFeed,
  LeagueFixtureFeed,
  LeagueResultFeed,
  TeamFeed,
  Fixture,
  Result,
} from "./types";

const app = new Hono<{ Bindings: Env }>();

app.use("*", cors());

// ─── Health / info ────────────────────────────────────────────────────────────

app.get("/", async (c) => {
  const index = await fetchFeed<Index>("index.json", c.env, c.executionCtx);
  return c.json({
    api: "fulltimecalendar",
    generated: index.generated,
    leagues: index.leagues.length,
    clubs: index.clubs.length,
  });
});

// ─── Leagues ──────────────────────────────────────────────────────────────────

app.get("/leagues", async (c) => {
  const index = await fetchFeed<Index>("index.json", c.env, c.executionCtx);
  return c.json({
    generated: index.generated,
    data: index.leagues.map(({ name, slug }) => ({ name, slug })),
  });
});

app.get("/leagues/:slug", async (c) => {
  const { slug } = c.req.param();
  const index = await fetchFeed<Index>("index.json", c.env, c.executionCtx);
  const league = index.leagues.find((l) => l.slug === slug);
  if (!league) throw new NotFoundError(`League not found: ${slug}`);
  return c.json({ generated: index.generated, data: league });
});

app.get("/leagues/:slug/teams", async (c) => {
  const { slug } = c.req.param();
  const index = await fetchFeed<Index>("index.json", c.env, c.executionCtx);
  const league = index.leagues.find((l) => l.slug === slug);
  if (!league) throw new NotFoundError(`League not found: ${slug}`);
  return c.json({ generated: index.generated, data: league.teams });
});

app.get("/leagues/:slug/teams/:teamSlug", async (c) => {
  const { slug, teamSlug } = c.req.param();
  const type = c.req.query("type"); // "fixtures" | "results" | undefined (both)

  const feed = await fetchFeed<TeamFeed>(
    `${slug}/teams/${teamSlug}.json`,
    c.env,
    c.executionCtx
  );

  const data: Partial<Pick<TeamFeed, "fixtures" | "results">> & {
    team: string;
    league: string;
  } = { team: feed.team, league: feed.league };

  if (!type || type === "fixtures") data.fixtures = feed.fixtures;
  if (!type || type === "results") data.results = feed.results;

  return c.json({ generated: feed.generated, data });
});

app.get("/leagues/:slug/fixtures", async (c) => {
  const { slug } = c.req.param();
  const teamFilter = c.req.query("team"); // optional team slug to filter by

  const feed = await fetchFeed<LeagueFixtureFeed>(
    `${slug}/fixtures.json`,
    c.env,
    c.executionCtx
  );

  let fixtures: Fixture[] = feed.fixtures;
  if (teamFilter) {
    fixtures = fixtures.filter(
      (f) =>
        slugify(f.home_team) === teamFilter ||
        slugify(f.away_team) === teamFilter
    );
  }

  return c.json({
    league: feed.league,
    generated: feed.generated,
    data: fixtures,
  });
});

app.get("/leagues/:slug/results", async (c) => {
  const { slug } = c.req.param();
  const teamFilter = c.req.query("team");

  const feed = await fetchFeed<LeagueResultFeed>(
    `${slug}/results.json`,
    c.env,
    c.executionCtx
  );

  let results: Result[] = feed.results;
  if (teamFilter) {
    results = results.filter(
      (r) =>
        slugify(r.home_team) === teamFilter ||
        slugify(r.away_team) === teamFilter
    );
  }

  return c.json({
    league: feed.league,
    generated: feed.generated,
    data: results,
  });
});

// ─── Clubs ────────────────────────────────────────────────────────────────────

app.get("/clubs", async (c) => {
  const index = await fetchFeed<Index>("index.json", c.env, c.executionCtx);
  return c.json({
    generated: index.generated,
    data: index.clubs.map(({ name, slug }) => ({ name, slug })),
  });
});

app.get("/clubs/:slug", async (c) => {
  const { slug } = c.req.param();
  const type = c.req.query("type"); // "fixtures" | "results" | undefined (both)

  const feed = await fetchFeed<ClubFeed>(
    `clubs/${slug}.json`,
    c.env,
    c.executionCtx
  );

  const data: Partial<Pick<ClubFeed, "fixtures" | "results">> & {
    club: string;
  } = { club: feed.club };

  if (!type || type === "fixtures") data.fixtures = feed.fixtures;
  if (!type || type === "results") data.results = feed.results;

  return c.json({ generated: feed.generated, data });
});

// ─── Error handling ───────────────────────────────────────────────────────────

app.onError((err, c) => {
  if (err instanceof NotFoundError) {
    return c.json({ error: err.message }, 404);
  }
  if (err instanceof UpstreamError) {
    return c.json({ error: err.message }, err.status as 502);
  }
  console.error(err);
  return c.json({ error: "Internal server error" }, 500);
});

app.notFound((c) => c.json({ error: "Not found" }, 404));

export default app;
