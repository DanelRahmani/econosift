"use client";

import { useState, useEffect, useCallback } from "react";

type ApiKeys = {
  fred_api_key: string;
  finnhub_api_key: string;
  gemini_api_key: string;
};

const defaultKeys: ApiKeys = {
  fred_api_key: "",
  finnhub_api_key: "",
  gemini_api_key: "",
};

/** Check if running inside a Tauri desktop window. */
function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI__" in window;
}

/** Read settings from the Tauri sidecar's settings.json. */
async function tauriReadSettings(): Promise<ApiKeys> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const { readTextFile } = await import("@tauri-apps/plugin-fs");
    const settingsPath: string = await invoke("get_settings_path");
    const raw = await readTextFile(settingsPath);
    return { ...defaultKeys, ...JSON.parse(raw) };
  } catch {
    return { ...defaultKeys };
  }
}

/** Write settings to the Tauri sidecar's settings.json. */
async function tauriWriteSettings(keys: ApiKeys): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  const { writeTextFile } = await import("@tauri-apps/plugin-fs");
  const settingsPath: string = await invoke("get_settings_path");
  await writeTextFile(settingsPath, JSON.stringify(keys, null, 2));
}

/** Read settings via the admin API (Docker / non-Tauri mode). */
async function apiReadSettings(): Promise<ApiKeys> {
  try {
    const res = await fetch("/api/admin/config");
    if (!res.ok) return { ...defaultKeys };
    const data = await res.json();
    return {
      fred_api_key: data?.fred_api_key || "",
      finnhub_api_key: data?.finnhub_api_key || "",
      gemini_api_key: data?.gemini_api_key || "",
    };
  } catch {
    return { ...defaultKeys };
  }
}

/** Write settings via the admin API. */
async function apiWriteSettings(keys: ApiKeys): Promise<void> {
  await fetch("/api/admin/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(keys),
  });
}

// ── Component ──────────────────────────────────────────────────────────────

type Props = {
  open: boolean;
  onClose: () => void;
};

export function SettingsPanel({ open, onClose }: Props) {
  const [keys, setKeys] = useState<ApiKeys>(defaultKeys);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    const k = isTauri() ? await tauriReadSettings() : await apiReadSettings();
    setKeys(k);
    setDirty(false);
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  if (!open) return null;

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      if (isTauri()) {
        await tauriWriteSettings(keys);
      } else {
        await apiWriteSettings(keys);
      }
      setDirty(false);
      setMessage({ type: "ok", text: "Settings saved. Restart the app for changes to take effect." });
    } catch (err) {
      setMessage({ type: "error", text: `Failed to save: ${err}` });
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field: keyof ApiKeys, value: string) => {
    setKeys((prev) => ({ ...prev, [field]: value }));
    setDirty(true);
    setMessage(null);
  };

  const masked = (val: string) => (val ? "••••••••" + val.slice(-4) : "");

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-text-primary">Settings</h2>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary p-1 rounded-lg hover:bg-surface-alt transition-colors"
            aria-label="Close"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-4">
          {/* FRED */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              FRED API Key
            </label>
            <input
              type="password"
              value={keys.fred_api_key ? masked(keys.fred_api_key) : ""}
              onChange={(e) => {
                // If user starts typing in a masked field, clear it first
                if (keys.fred_api_key && e.target.value.startsWith("•")) return;
                handleChange("fred_api_key", e.target.value);
              }}
              onFocus={(e) => {
                // Reveal on focus
                if (keys.fred_api_key) {
                  setKeys((prev) => ({ ...prev, fred_api_key: keys.fred_api_key }));
                }
              }}
              placeholder="Enter FRED API key"
              className="w-full px-3 py-2 rounded-lg bg-surface-alt border border-border text-text-primary placeholder-text-muted text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
            <p className="text-[11px] text-text-muted mt-1">
              Get yours free at{" "}
              <a href="https://fred.stlouisfed.org/docs/api/api_key.html" target="_blank" rel="noreferrer" className="text-accent underline">
                fred.stlouisfed.org
              </a>
            </p>
          </div>

          {/* Finnhub */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              Finnhub API Key
            </label>
            <input
              type="password"
              value={keys.finnhub_api_key ? masked(keys.finnhub_api_key) : ""}
              onChange={(e) => {
                if (keys.finnhub_api_key && e.target.value.startsWith("•")) return;
                handleChange("finnhub_api_key", e.target.value);
              }}
              onFocus={(e) => {
                if (keys.finnhub_api_key) {
                  setKeys((prev) => ({ ...prev, finnhub_api_key: keys.finnhub_api_key }));
                }
              }}
              placeholder="Enter Finnhub API key"
              className="w-full px-3 py-2 rounded-lg bg-surface-alt border border-border text-text-primary placeholder-text-muted text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
            <p className="text-[11px] text-text-muted mt-1">
              Get yours free at{" "}
              <a href="https://finnhub.io/register" target="_blank" rel="noreferrer" className="text-accent underline">
                finnhub.io
              </a>
            </p>
          </div>

          {/* Gemini */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              Gemini API Key
            </label>
            <input
              type="password"
              value={keys.gemini_api_key ? masked(keys.gemini_api_key) : ""}
              onChange={(e) => {
                if (keys.gemini_api_key && e.target.value.startsWith("•")) return;
                handleChange("gemini_api_key", e.target.value);
              }}
              onFocus={(e) => {
                if (keys.gemini_api_key) {
                  setKeys((prev) => ({ ...prev, gemini_api_key: keys.gemini_api_key }));
                }
              }}
              placeholder="Enter Gemini API key"
              className="w-full px-3 py-2 rounded-lg bg-surface-alt border border-border text-text-primary placeholder-text-muted text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
            <p className="text-[11px] text-text-muted mt-1">
              Get yours free at{" "}
              <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="text-accent underline">
                aistudio.google.com
              </a>
            </p>
          </div>
        </div>

        {message && (
          <div
            className={`mt-4 px-3 py-2 rounded-lg text-sm ${
              message.type === "ok"
                ? "bg-emerald-900/30 text-emerald-400 border border-emerald-800/50"
                : "bg-red-900/30 text-red-400 border border-red-800/50"
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary rounded-lg hover:bg-surface-alt transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className="px-4 py-2 text-sm font-medium text-white bg-accent rounded-lg hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
