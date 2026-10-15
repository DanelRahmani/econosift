// Global teardown for the mocked run (PW_MOCK_API=1): any /api request without a recorded
// fixture fails the suite, so the fixtures cannot silently fall behind the pages. Re-record with
// `npm run e2e:record` against a live stack, then run the suite with PLAYWRIGHT_BASE_URL=http://localhost:4100.
import { existsSync, readFileSync } from "node:fs";
import { MISSING_LOG } from "./mock-server.mjs";

export default function teardown() {
  if (!existsSync(MISSING_LOG)) return;
  const missing = [...new Set(readFileSync(MISSING_LOG, "utf8").split("\n").filter(Boolean))];
  if (missing.length) {
    throw new Error(`${missing.length} /api request(s) had no recorded fixture:\n${missing.join("\n")}`);
  }
}
