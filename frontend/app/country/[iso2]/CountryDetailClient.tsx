"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { FactbookProfile, FactbookCountry } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

function CollapsibleSection({ title, fields, defaultOpen = false }: {
  title: string; fields: { label: string; value: string }[]; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Card className="p-5 lg:col-span-2" data-prov={`sections.${title}`} data-prov-ctx={title}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-left"
      >
        <h2 className="text-base font-semibold text-text-primary">{title}</h2>
        <svg
          width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round"
          className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <dl className="mt-3 space-y-3 border-t border-border/50 pt-3">
          {fields.map((field, j) => (
            <div key={j}>
              {field.label && (
                <dt className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1">
                  {field.label}
                </dt>
              )}
              <dd className="text-sm text-text-primary leading-relaxed whitespace-pre-line">
                {field.value}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  );
}

export default function CountryDetailClient({ iso2 }: { iso2: string }) {
  const router = useRouter();
  const [profile, setProfile] = useState<FactbookProfile | null>(null);
  const [countries, setCountries] = useState<FactbookCountry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const scope = useSourceScope(provOf(profile));

  useEffect(() => { api.factbookCountries().then(setCountries).catch(() => {}); }, []);
  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (!iso2) return;
    setLoading(true); setError(false);
    api.factbookCountry(iso2).then(setProfile).catch(() => setError(true)).finally(() => setLoading(false));
  }, [iso2, refreshNonce]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return countries.slice(0, 30);
    return countries.filter((c) => c.name.toLowerCase().includes(q) || c.iso2.toLowerCase().includes(q)).slice(0, 30);
  }, [countries, search]);

  const neighborPills = useMemo(() => {
    if (!countries.length || !profile) return [];
    const borderSet = new Set(profile.borders || []);
    const sameRegion = countries.filter((c) => c.region === profile.region && c.iso2 !== profile.iso2 && !borderSet.has(c.iso2));
    const borderCountries = countries.filter((c) => borderSet.has(c.iso2));
    return [...borderCountries, ...sameRegion.slice(0, 12 - borderCountries.length)];
  }, [countries, profile]);

  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => { const el = document.getElementById("country-dropdown"); if (el && !el.contains(e.target as Node)) setDropdownOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [dropdownOpen]);

  const navigateTo = (newIso2: string) => { setDropdownOpen(false); setSearch(""); router.push('/country/' + newIso2); };

  if (loading) return <div className="max-w-5xl mx-auto px-4 py-6"><PageSkeleton text="Loading country profile…" /></div>;
  if (error || !profile) return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <Link href="/country" className="text-sm text-accent hover:underline">← Back to Countries</Link>
      <h1 className="text-2xl font-bold text-text-primary mt-4">{iso2}</h1>
      <div className="text-text-secondary text-sm py-8 text-center">Country not found.</div>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-4" {...scope}>
      <div className="flex items-center gap-4 flex-wrap">
        <Link href="/country" className="text-sm text-accent hover:underline shrink-0">← All Countries</Link>
        <div id="country-dropdown" className="relative flex-1 max-w-sm">
          <button onClick={() => { setDropdownOpen(!dropdownOpen); setSearch(""); }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-surface text-sm text-text-primary hover:border-accent/50">
            <span className="text-lg">{profile.flag}</span>
            <span className="font-medium truncate">{profile.name}</span>
            <span className="text-text-muted text-xs ml-auto">{profile.iso2}</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              className={'shrink-0 transition-transform ' + (dropdownOpen ? "rotate-180" : "")}>
              <path d="M6 9l6 6 6-6" /></svg>
          </button>
          {dropdownOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-surface border border-border rounded-xl shadow-xl z-50 overflow-hidden" style={{ maxHeight: 320 }}>
              <div className="p-2 border-b border-border">
                <input type="text" placeholder="Search 250 countries…" value={search} onChange={(e) => setSearch(e.target.value)} autoFocus
                  className="w-full px-2 py-1 text-sm border border-border rounded bg-background text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent" />
              </div>
              <div className="overflow-y-auto" style={{ maxHeight: 260 }}>
                {filtered.map((c) => (
                  <button key={c.iso2} onClick={() => navigateTo(c.iso2)}
                    className={'w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-surface-alt ' + (c.iso2 === iso2 ? "bg-accent/10 text-accent" : "text-text-primary")}>
                    <span className="text-base">{c.flag}</span><span className="truncate">{c.name}</span><span className="text-text-muted text-xs ml-auto">{c.iso2}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-5 py-2">
        <img src={'https://flagcdn.com/w160/' + profile.iso2.toLowerCase() + '.png'} alt={profile.name}
          className="w-20 h-auto rounded shadow-sm" />
        <div>
          <h1 className="text-3xl font-bold text-text-primary">{profile.name}</h1>
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
            {profile.localName && (
              <span className="text-sm text-text-secondary">{profile.localName} <span className="text-[11px] text-text-muted">(local)</span></span>
            )}
            {profile.frenchName && (
              <span className="text-sm text-text-secondary">{profile.frenchName} <span className="text-[11px] text-text-muted">(French)</span></span>
            )}
          </div>
          {profile.continent && (
            <p className="text-xs text-text-muted mt-1.5">{profile.continent}</p>
          )}
          <p className="text-xs text-text-muted mt-0.5">{profile.iso2}{profile.iso3 ? ' · ' + profile.iso3 : ''}</p>
        </div>
      </div>

      {neighborPills.length > 0 && (
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-xs font-medium text-text-muted mr-1 shrink-0">Borders & Neighbors:</span>
          {neighborPills.map((c) => (
            <button key={c.iso2} onClick={() => navigateTo(c.iso2)}
              className={'px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ' +
                (profile.borders?.includes(c.iso2) ? "bg-surface-alt border-accent/40 text-accent hover:bg-accent/10" : "bg-surface-alt border-border text-text-secondary hover:text-text-primary hover:border-accent/40")}>
              {c.flag} {c.name}
            </button>
          ))}
        </div>
      )}

      {profile.sections.map((section, i) => (
        <CollapsibleSection key={i} title={section.title} fields={section.fields}
          defaultOpen={section.title === "Introduction" || section.title === "Economy"} />
      ))}
    </div>
  );
}
