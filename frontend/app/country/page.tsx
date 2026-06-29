"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { FactbookCountry } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";

export default function CountryListPage() {
  const [countries, setCountries] = useState<FactbookCountry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.factbookCountries()
      .then(setCountries)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  const filtered = search.trim()
    ? countries.filter((c) =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.iso2.toLowerCase().includes(search.toLowerCase())
      )
    : countries;

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Country Profiles</h1>
          <p className="text-sm text-text-secondary mt-1">
            CIA World Factbook data for ~260 countries — geography, people, government, economy & more
          </p>
        </div>
        <PageSkeleton text="Loading country profiles…" />
      </div>
    );
  }

  if (error || !countries.length) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-text-primary">Country Profiles</h1>
        <p className="text-sm text-text-secondary mt-1">
          CIA World Factbook data for ~260 countries
        </p>
        <div className="text-text-secondary text-sm py-8 text-center">
          Country data unavailable — factbook.json may not be downloaded yet.<br />
          Run <code className="bg-surface-alt px-1 rounded">Bulk Data Refresh</code> from the Admin page.
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Country Profiles</h1>
        <p className="text-sm text-text-secondary mt-1">
          {countries.length} countries · CIA World Factbook
        </p>
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="Search countries…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-md px-3 py-2 rounded-lg border border-border bg-surface text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-accent"
      />

      {/* Country Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {filtered.map((c) => (
          <Link
            key={c.iso2}
            href={`/country/${c.iso2}`}
            prefetch={false}
            className="block"
          >
            <Card className="p-4 h-full hover:border-accent/30 transition-colors cursor-pointer text-center">
              <img
                src={`https://flagcdn.com/w80/${c.iso2.toLowerCase()}.png`}
                alt={c.name}
                className="w-12 h-auto mx-auto mb-2 rounded-sm"
                loading="lazy"
              />
              <div className="text-sm font-medium text-text-primary truncate">{c.name}</div>
              <div className="text-xs text-text-muted mt-0.5">{c.iso2}{c.region ? ` · ${c.region}` : ""}</div>
            </Card>
          </Link>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-text-secondary text-sm py-8 text-center">
          No countries match &quot;{search}&quot;
        </div>
      )}
    </div>
  );
}
