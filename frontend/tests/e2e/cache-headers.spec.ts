import { test, expect } from "@playwright/test";

/**
 * P2-18 — after a redeploy the browser kept running the old JS until a hard refresh.
 *
 * nginx must make the browser revalidate HTML on every load (`no-cache`) so it always
 * picks up the new build's chunk names, while the content-hashed `/_next/static`
 * chunks can be cached forever (`immutable`). Only nginx sets these, so the spec
 * skips when the suite runs against `next dev` instead of the Docker stack.
 */
test.skip(!process.env.PLAYWRIGHT_BASE_URL, "cache headers come from nginx (Docker stack only)");

test("HTML revalidates every load and hashed static chunks are immutable", async ({ request }) => {
  const html = await request.get("/dashboard");
  expect(html.status()).toBe(200);
  const htmlCache = html.headers()["cache-control"] ?? "";
  expect(htmlCache).toMatch(/\bno-cache\b/);
  expect(htmlCache).not.toMatch(/s-maxage|stale-while-revalidate|immutable/);

  const chunk = (await html.text()).match(/\/_next\/static\/[^"']+\.js/)?.[0];
  expect(chunk, "page references a hashed JS chunk").toBeTruthy();
  const js = await request.get(chunk!);
  expect(js.status()).toBe(200);
  expect(js.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
});
