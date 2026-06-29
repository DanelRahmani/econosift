"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { FactbookProfile } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";

export default function CountryDetailPage() {
  const params = useParams();
  const iso2 = (params?.iso2 as string) || "";
  const [profile, setProfile] = useState<FactbookProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!iso2) return;
    setLoading(true);
    setError(false);
    api.factbookCountry(iso2)
      .then(setProfile)
      .catch((e) => {
        if (e?.toString?.().includes("404")) setError(true);
        else setError(true);
      })
      .finally(() => setLoading(false));
  }, [iso2]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        <PageSkeleton text="Loading country profile…" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
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
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      <Link href="/country" className="text-sm text-accent hover:underline inline-block">
        ← All Countries
      </Link>

      <div className="flex items-center gap-3">
        <span className="text-3xl">{profile.flag || "🏳️"}</span>
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{profile.name}</h1>
          <p className="text-sm text-text-muted">
            {profile.iso2}{profile.iso3 ? ` · ${profile.iso3}` : ""}
          </p>
        </div>
      </div>

      {/* Sections */}
      {profile.sections.map((section, i) => (
        <Card key={i} className="p-5">
          <h2 className="text-lg font-semibold text-text-primary mb-3">{section.title}</h2>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
            {section.fields.map((field, j) => (
              <div key={j} className={field.label === "" ? "sm:col-span-2" : ""}>
                {field.label && (
                  <dt className="text-xs font-medium text-text-muted uppercase tracking-wide mb-0.5">
                    {field.label}
                  </dt>
                )}
                <dd className="text-sm text-text-primary">{field.value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      ))}

      {profile.sections.length === 0 && (
        <Card className="p-5 text-center text-text-muted text-sm">
          No detailed data available for this country.
        </Card>
      )}
    </div>
  );
}
