// Serves the static export (out/) and answers /api/* from recorded fixtures, so the Playwright
// smoke tests run without the backend (Phase 69 item 6: the CI job no longer depends on live
// Yahoo/FRED/World Bank answers or a cold Docker stack).
//
//   node tests/e2e/mock-server.mjs                          # mock: /api from tests/e2e/fixtures/api
//   node tests/e2e/mock-server.mjs --record http://localhost # record: proxy /api to a live stack, save
//
// No dependencies: node:http, node:fs, node:zlib, node:crypto only.
import http from "node:http";
import { createHash } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { gunzipSync, gzipSync } from "node:zlib";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const OUT = join(HERE, "..", "..", "out");
const FIXTURES = join(HERE, "fixtures", "api");
const PORT = Number(process.env.MOCK_PORT ?? 4100);
// Requests with no fixture are listed here; tests/e2e/mock-teardown.mjs fails the run on any.
export const MISSING_LOG = join(HERE, "..", "..", "test-results", "missing-fixtures.log");
const recordIdx = process.argv.indexOf("--record");
const RECORD_FROM = recordIdx > 0 ? process.argv[recordIdx + 1] : null;

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
  ".woff2": "font/woff2", ".txt": "text/plain",
};

/**
 * Fixture key for a request: method + path + sorted query, with today-dependent values
 * (ISO dates, years) replaced so a fixture recorded today still matches next month or next year.
 * POST bodies are part of the key (hashed), with the same replacement.
 */
export function fixtureKey(method, url, body = "") {
  const u = new URL(url, "http://x");
  const norm = (v) => v.replace(/\b\d{4}-\d{2}-\d{2}\b/g, "{date}").replace(/^(19|20)\d{2}$/, "{year}");
  const query = [...u.searchParams.entries()]
    .map(([k, v]) => [k, norm(v)])
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join("&");
  const bodyPart = body ? `#${createHash("sha1").update(norm(body)).digest("hex").slice(0, 10)}` : "";
  const raw = `${method} ${u.pathname.replace(/^\/api/, "")}${query ? `?${query}` : ""}${bodyPart}`;
  const safe = raw.replace(/[^A-Za-z0-9._=-]+/g, "_").slice(0, 120);
  return `${safe}-${createHash("sha1").update(raw).digest("hex").slice(0, 8)}`;
}

function readBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
  });
}

async function handleApi(req, res) {
  const body = req.method === "GET" || req.method === "HEAD" ? "" : await readBody(req);
  const key = fixtureKey(req.method, req.url, body);
  const file = join(FIXTURES, `${key}.json.gz`);
  if (RECORD_FROM) {
    const upstream = await fetch(new URL(req.url, RECORD_FROM), {
      method: req.method,
      headers: { "content-type": req.headers["content-type"] ?? "application/json" },
      body: body || undefined,
    }).catch((e) => ({ ok: false, status: 502, text: async () => JSON.stringify({ detail: String(e) }) }));
    const text = await upstream.text();
    // Only answers worth replaying are kept: a timeout or 5xx while recording is not a fixture.
    if (upstream.status < 500) {
      mkdirSync(FIXTURES, { recursive: true });
      writeFileSync(file, gzipSync(JSON.stringify({ key: `${req.method} ${req.url}`, status: upstream.status, body: text })));
    }
    res.writeHead(upstream.status, { "content-type": "application/json" });
    res.end(text);
    return;
  }
  if (!existsSync(file)) {
    console.error(`MISSING FIXTURE ${req.method} ${req.url} -> ${key}`);
    mkdirSync(join(MISSING_LOG, ".."), { recursive: true });
    appendFileSync(MISSING_LOG, `${req.method} ${req.url} -> ${key}\n`);
    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ detail: `no recorded fixture for ${req.method} ${req.url}` }));
    return;
  }
  const { status, body: text } = JSON.parse(gunzipSync(readFileSync(file)).toString("utf8"));
  res.writeHead(status, { "content-type": "application/json" });
  res.end(text);
}

function handleStatic(req, res) {
  const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const base = normalize(join(OUT, path));
  if (!base.startsWith(OUT)) { res.writeHead(403); res.end(); return; }
  const candidates = [base, `${base}.html`, join(base, "index.html")];
  const hit = candidates.find((c) => existsSync(c) && statSync(c).isFile());
  const file = hit ?? join(OUT, "404.html");
  res.writeHead(hit ? 200 : 404, { "content-type": TYPES[extname(file)] ?? "application/octet-stream" });
  res.end(readFileSync(file));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === normalize(process.argv[1])) {
  if (!existsSync(join(OUT, "index.html"))) {
    console.error(`No static export at ${OUT}: run \`npm run build\` first.`);
    process.exit(1);
  }
  rmSync(MISSING_LOG, { force: true });
  http
    .createServer((req, res) => {
      (req.url?.startsWith("/api/") ? handleApi(req, res) : Promise.resolve(handleStatic(req, res))).catch((e) => {
        console.error(e);
        res.writeHead(500);
        res.end();
      });
    })
    .listen(PORT, () => console.log(`mock server on http://localhost:${PORT} (${RECORD_FROM ? `recording from ${RECORD_FROM}` : "fixtures"})`));
}
