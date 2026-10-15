// Set by the desktop BackendGate while /api/health is not answering yet.
// Only then do queries keep retrying long: once the backend is up, a failing
// request is a real failure and retrying it six times just re-hits Yahoo.
let starting = false;

export function setBackendStarting(value: boolean): void {
  starting = value;
}

export function isBackendStarting(): boolean {
  return starting;
}
