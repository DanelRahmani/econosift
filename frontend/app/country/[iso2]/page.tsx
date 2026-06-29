"use client";
import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { FactbookProfile, FactbookCountry } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";

export default function CountryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const iso2 = (params?.iso2 as string) || "";
  const [profile, setProfile] = useState<FactbookProfile | null>(null);
  const [countries, setCountries] = useState<FactbookCountry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Load country list once
  useEffect(() => {
    api.factbookCountries().then(setCountries).catch(() => {});
  }, []);

  // Load profile when iso2 changes
  useEffect(() => {
    if (!iso2) return;
    setLoading(true);
    setError(false);
    api.factbookCountry(iso2)
      .then(setProfile)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [iso2]);

  // Filter countries for dropdown
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return countries.slice(0, 30);
    return countries
      .filter((c) =>
        c.name.toLowerCase().includes(q) ||
        c.iso2.toLowerCase().includes(q) ||
        c.iso3.toLowerCase().includes(q)
      )
      .slice(0, 30);
  }, [countries, search]);

  // Build neighbor pills: borders first, then same-region countries
  const neighborPills = useMemo(() => {
    if (!countries.length || !profile) return [];
    const borderSet = new Set(profile.borders || []);
    const sameRegion = countries.filter(
      (c) => c.region === profile.region && c.iso2 !== profile.iso2 && !borderSet.has(c.iso2)
    );
    const borderCountries = countries.filter((c) => borderSet.has(c.iso2));
    return [...borderCountries, ...sameRegion.slice(0, 12 - borderCountries.length)];
  }, [countries, profile]);

  // Close dropdown on click outside
  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => {
      const el = document.getElementById("country-dropdown");
      if (el && !el.contains(e.target as Node)) setDropdownOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [dropdownOpen]);

  const navigateTo = (newIso2: string) => {
    setDropdownOpen(false);
    setSearch("");
    router.push(`/country/${newIso2}`);
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <PageSkeleton text="Loading country profile…" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-6">
        <Link href="/country" className="text-sm text-accent hover:underline mb-4 inline-block">
          ← Back to Countries
        </Link>
        <h1 className="text-2xl font-bold text-text-primary">{iso2}</h1>
        <div className="text-text-secondary text-sm py-8 text-center">
          Country not found. The factbook data may not include this country code.
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* Top bar: back link + country selector */}
      <div className="flex items-center gap-4 flex-wrap">
        <Link href="/country" className="text-sm text-accent hover:underline shrink-0">
          ← All Countries
        </Link>

        {/* Country Selector Dropdown */}
        <div id="country-dropdown" className="relative flex-1 max-w-sm">
          <button
            onClick={() => { setDropdownOpen(!dropdownOpen); setSearch(""); }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-surface text-sm text-text-primary hover:border-accent/50 transition-colors"
          >
            <span className="text-lg">{profile.flag}</span>
            <span className="font-medium truncate">{profile.name}</span>
            <span className="text-text-muted text-xs ml-auto">{profile.iso2}</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" className={`shrink-0 transition-transform ${dropdownOpen ? "rotate-180" : ""}`}>
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>

          {dropdownOpen && (
            <div
              className="absolute top-full left-0 right-0 mt-1 bg-surface border border-border rounded-xl shadow-xl z-50 overflow-hidden"
              style={{ maxHeight: "320px" }}
            >
              <div className="p-2 border-b border-border">
                <input
                  type="text"
                  placeholder="Search 250 countries…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  autoFocus
                  className="w-full px-2 py-1 text-sm border border-border rounded bg-background text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                />
              </div>
              <div className="overflow-y-auto" style={{ maxHeight: "260px" }}>
                {filtered.map((c) => (
                  <button
                    key={c.iso2}
                    onClick={() => navigateTo(c.iso2)}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-surface-alt transition-colors ${
                      c.iso2 === iso2 ? "bg-accent/10 text-accent" : "text-text-primary"
                    }`}
                  >
                    <span className="text-base">{c.flag || "🏳️"}</span>
                    <span className="truncate">{c.name}</span>
                    <span className="text-text-muted text-xs ml-auto">{c.iso2}</span>
                  </button>
                ))}
                {filtered.length === 0 && (
                  <div className="px-3 py-4 text-center text-sm text-text-muted">
                    No countries match &quot;{search}&quot;
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="text-4xl">{profile.flag || "🏳️"}</span>
        <div>
          <h1 className="text-3xl font-bold text-text-primary">{profile.name}</h1>
          <p className="text-sm text-text-muted">
            {profile.iso2}{profile.iso3 ? ` · ${profile.iso3}` : ""}
          </p>
        </div>
      </div>

      {/* Neighbor Pills — Atlas-style */}
      {neighborPills.length > 0 && (
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-xs font-medium text-text-muted mr-1 shrink-0">
            {profile.borders?.length ? "Borders & Neighbors" : "Same Region"}:
          </span>
          {neighborPills.map((c) => (
            <button
              key={c.iso2}
              onClick={() => navigateTo(c.iso2)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                profile.borders?.includes(c.iso2)
                  ? "bg-surface-alt border-accent/40 text-accent hover:bg-accent/10"
                  : "bg-surface-alt border-border text-text-secondary hover:text-text-primary hover:border-accent/40"
              }`}
            >
              {c.flag} {c.name}
            </button>
          ))}
        </div>
      )}

      {/* Sections — 2-column on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {profile.sections.map((section, i) => (
          <Card key={i} className="p-5">
            <h2 className="text-base font-semibold text-text-primary mb-3 pb-2 border-b border-border/50">
              {section.title}
            </h2>
            <dl className="space-y-2.5">
              {section.fields.map((field, j) => (
                <div key={j}>
                  {field.label && (
                    <dt className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-0.5">
                      {field.label}
                    </dt>
                  )}
                  <dd className={`text-sm text-text-primary ${!field.label ? "italic text-text-secondary" : ""}`}>
                    {field.value}
                  </dd>
                </div>
              ))}
            </dl>
          </Card>
        ))}
      </div>

      {profile.sections.length === 0 && (
        <Card className="p-5 text-center text-text-muted text-sm">
          No detailed data available for this country.
        </Card>
      )}
    </div>
  );
}
