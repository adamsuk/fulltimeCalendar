import type { Env } from "./types";

/**
 * Returns seconds until the next scraper run at 06:00 UTC.
 * This aligns cache expiry with when fresh data becomes available.
 * Minimum 5 minutes to avoid a stampede right around the scrape window.
 */
function ttlUntilNextScrape(): number {
  const now = new Date();
  const next = new Date(now);
  next.setUTCHours(6, 0, 0, 0);
  if (now.getUTCHours() >= 6) {
    next.setUTCDate(next.getUTCDate() + 1);
  }
  const seconds = Math.floor((next.getTime() - now.getTime()) / 1000);
  return Math.max(seconds, 300);
}

export class NotFoundError extends Error {
  constructor(message = "Not found") {
    super(message);
    this.name = "NotFoundError";
  }
}

export class UpstreamError extends Error {
  constructor(
    message = "Failed to fetch upstream data",
    public readonly status = 502
  ) {
    super(message);
    this.name = "UpstreamError";
  }
}

/**
 * Fetches a JSON feed from the GitHub raw content URL.
 * Responses are cached in Cloudflare's Cache API until the next scraper run.
 */
export async function fetchFeed<T>(
  path: string,
  env: Env,
  ctx: ExecutionContext
): Promise<T> {
  const url = `https://raw.githubusercontent.com/${env.GITHUB_REPO}/${env.GITHUB_BRANCH}/feeds/${path}`;
  const cache = caches.default;

  const cached = await cache.match(url);
  if (cached) {
    return cached.json() as Promise<T>;
  }

  const headers: HeadersInit = { Accept: "application/json" };
  if (env.GITHUB_TOKEN) {
    headers["Authorization"] = `Bearer ${env.GITHUB_TOKEN}`;
  }

  const res = await fetch(url, { headers });

  if (res.status === 404) {
    throw new NotFoundError(`Feed not found: ${path}`);
  }
  if (!res.ok) {
    throw new UpstreamError(
      `GitHub returned ${res.status} for ${path}`,
      502
    );
  }

  const data = await res.json();
  const ttl = ttlUntilNextScrape();

  ctx.waitUntil(
    cache.put(
      url,
      new Response(JSON.stringify(data), {
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": `public, max-age=${ttl}`,
        },
      })
    )
  );

  return data as T;
}

/**
 * Converts a team name to the slug format used in the feeds directory.
 * Mirrors the slug() function from the Python scraper.
 */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/[\s_]+/g, "-")
    .replace(/-+/g, "-");
}
