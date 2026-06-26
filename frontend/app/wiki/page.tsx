"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { WikiSearch } from "@/components/wiki/WikiSearch";
import { WikiTermCard } from "@/components/wiki/WikiTermCard";
import { WikiCategoryNav } from "@/components/wiki/WikiCategoryNav";
import type { WikiTerm, WikiCategory } from "@/lib/types";

function termToCard(t: WikiTerm): WikiTerm { return t; }

export default function WikiPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null);

  const { data: catData } = useQuery({
    queryKey: ["wikiCategories"],
    queryFn: api.wikiCategories,
  });

  const { data: termsData, isLoading } = useQuery({
    queryKey: ["wikiTerms", query, category],
    queryFn: () => api.wikiTerms(query || undefined, category || undefined),
  });

  const categories: (WikiCategory & { count: number })[] = catData?.categories || [];
  const totalCount = catData?.total || 0;
  const results: WikiTerm[] = termsData?.terms || [];

  const handleSearch = useCallback((q: string) => { setQuery(q); setExpandedSlug(null); }, []);
  const handleCategorySelect = useCallback((key: string) => { setCategory(key === "all" ? "" : key); setExpandedSlug(null); }, []);
  const handleToggle = useCallback((slug: string) => { setExpandedSlug((p) => (p === slug ? null : slug)); }, []);
  const handleRelatedClick = useCallback((slug: string) => {
    const t = results.find((r) => r.slug === slug);
    if (t) { setCategory(t.category); setQuery(""); setExpandedSlug(slug);
      setTimeout(() => document.getElementById(`wiki-term-${slug}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 100);
    }
  }, [results]);

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold text-text-primary">Wiki</h1>
        <p className="text-sm text-text-muted mt-1">Financial dictionary — {totalCount} terms across {categories.length} categories. Click any term for details.</p>
      </div>
      <WikiSearch onSearch={handleSearch} />
      <div className="md:hidden"><WikiCategoryNav categories={categories} activeCategory={category || "all"} onSelect={handleCategorySelect} totalCount={totalCount} /></div>
      <div className="flex gap-6">
        <aside className="hidden md:block w-64 flex-shrink-0"><div className="sticky top-20 space-y-4"><p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Categories</p><WikiCategoryNav categories={categories} activeCategory={category || "all"} onSelect={handleCategorySelect} totalCount={totalCount} /></div></aside>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-text-muted mb-4">{termsData?.total || 0} {termsData?.total === 1 ? "term" : "terms"}{query ? ` matching "${query}"` : ""}{category ? ` in ${categories.find((c) => c.key === category)?.label || category}` : ""}</p>
          {isLoading ? <div className="text-text-muted text-sm py-8 text-center">Loading…</div> :
           results.length > 0 ? <div className="space-y-2">{results.map((t) => (<div key={t.slug} id={`wiki-term-${t.slug}`}><WikiTermCard term={t} isExpanded={expandedSlug === t.slug} onToggle={() => handleToggle(t.slug)} onRelatedClick={handleRelatedClick} /></div>))}</div> :
           <div className="text-center py-16"><p className="text-text-muted text-sm">No terms found.</p></div>}
        </div>
      </div>
    </main>
  );
}