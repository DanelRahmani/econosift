"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { rankCommands, STATIC_COMMANDS, type CommandGroup, type CommandItem } from "@/lib/commandRegistry";

/** Fired by the navbar button (and anything else) to open the palette. */
export const OPEN_COMMAND_PALETTE = "econosift:open-command-palette";

const GROUP_ORDER: CommandGroup[] = ["Pages", "Tabs", "Tickers", "Wiki"];

/**
 * Global command palette (P1-18): Ctrl/⌘+K or the navbar button. Fuzzy-matches every page and
 * deep-linkable sub-tab instantly, and searches tickers ("Open AAPL in Markets") and Wiki terms
 * through the backend as you type.
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [tickers, setTickers] = useState<CommandItem[]>([]);
  const [wiki, setWiki] = useState<CommandItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const requestId = useRef(0);
  const openRef = useRef(open);
  openRef.current = open;

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setTickers([]);
    setWiki([]);
    setActive(0);
  }, []);

  // Ctrl/⌘+K toggles from anywhere (also inside inputs: it is the app-wide shortcut).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape" && openRef.current) {
        // Here rather than on the input: focus moves into the input a tick after opening, and Esc
        // must close the dialog whatever has focus (the button that opened it, or the list).
        e.preventDefault();
        close();
      }
    }
    function onOpen() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_COMMAND_PALETTE, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_COMMAND_PALETTE, onOpen);
    };
  }, [close]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  // Live ticker and Wiki results, debounced; a slower stale response never overwrites a newer one.
  useEffect(() => {
    const q = query.trim();
    if (!open || !q) {
      setTickers([]);
      setWiki([]);
      return;
    }
    const id = ++requestId.current;
    const t = setTimeout(() => {
      api.search(q).then((r) => {
        if (id !== requestId.current) return;
        setTickers((r.results ?? []).slice(0, 5).map((s) => ({
          id: `ticker:${s.symbol}`,
          group: "Tickers" as const,
          label: `Open ${s.symbol} in Markets`,
          hint: [s.name, s.exchange].filter(Boolean).join(" · "),
          href: `/markets?t=${encodeURIComponent(s.symbol)}`,
        })));
      }).catch(() => { if (id === requestId.current) setTickers([]); });
      if (q.length >= 2) {
        api.wikiTerms(q).then((r) => {
          if (id !== requestId.current) return;
          setWiki((r.terms ?? []).slice(0, 5).map((w) => ({
            id: `wiki:${w.slug}`,
            group: "Wiki" as const,
            label: w.term,
            hint: "Wiki",
            href: `/wiki?q=${encodeURIComponent(w.term)}&term=${encodeURIComponent(w.slug)}`,
          })));
        }).catch(() => { if (id === requestId.current) setWiki([]); });
      } else {
        setWiki([]);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [query, open]);

  // Groups are ordered by their best local match (so "inflation" leads with the Macro › Inflation
  // tab, not the Macro page that only matches a keyword), then live tickers and Wiki terms.
  const { items, groupOrder } = useMemo(() => {
    const local = query.trim()
      ? rankCommands(query, STATIC_COMMANDS, 8)
      : STATIC_COMMANDS.filter((c) => c.group === "Pages");
    const order = [...new Set<CommandGroup>([...local.map((i) => i.group), ...GROUP_ORDER])];
    const all = [...local, ...tickers, ...wiki];
    return { items: order.flatMap((g) => all.filter((i) => i.group === g)), groupOrder: order };
  }, [query, tickers, wiki]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    if (active >= items.length) setActive(Math.max(0, items.length - 1));
  }, [items.length, active]);

  const go = useCallback((item: CommandItem | undefined) => {
    if (!item) return;
    close();
    router.push(item.href);
  }, [close, router]);

  function onInputKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(items[active]);
    }
  }

  useEffect(() => {
    document.getElementById(`cmd-opt-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  let index = -1;
  return (
    <div
      className="fixed inset-0 z-[200] bg-black/50 backdrop-blur-sm flex items-start justify-center px-4 pt-[12vh] animate-[fade-in_0.15s_ease-out]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="w-full max-w-xl bg-surface/95 backdrop-blur-xl border border-border rounded-2xl shadow-[0_24px_64px_-16px_rgb(0_0_0/0.6),inset_0_1px_0_rgb(var(--highlight)/var(--highlight-a))] overflow-hidden animate-[pop-in_0.2s_cubic-bezier(0.22,1,0.36,1)]"
      >
        <div className="flex items-center gap-2 px-4 border-b border-border">
          <svg className="w-4 h-4 text-text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            placeholder="Search pages, tabs, tickers, Wiki terms…"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-palette-list"
            aria-activedescendant={items.length ? `cmd-opt-${active}` : undefined}
            className="flex-1 bg-transparent py-3 text-sm text-text-primary placeholder-text-muted focus:outline-none"
          />
          <kbd className="hidden sm:inline text-[10px] text-text-muted border border-border rounded px-1.5 py-0.5">Esc</kbd>
        </div>
        <ul id="command-palette-list" role="listbox" aria-label="Results" className="max-h-[60vh] overflow-y-auto py-1">
          {items.length === 0 && (
            <li className="px-4 py-6 text-sm text-text-muted text-center">No matches for “{query.trim()}”.</li>
          )}
          {groupOrder.map((group) => {
            const groupItems = items.filter((i) => i.group === group);
            if (!groupItems.length) return null;
            return (
              <li key={group} role="presentation">
                <div className="px-4 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">{group}</div>
                <ul role="presentation">
                  {groupItems.map((item) => {
                    index += 1;
                    const i = index;
                    const selected = i === active;
                    return (
                      <li
                        key={item.id}
                        id={`cmd-opt-${i}`}
                        role="option"
                        aria-selected={selected}
                        onMouseEnter={() => setActive(i)}
                        onMouseDown={(e) => { e.preventDefault(); go(item); }}
                        className={`mx-1 px-3 py-2 rounded-lg flex items-center justify-between gap-3 cursor-pointer text-sm ${
                          selected ? "bg-accent-light/10 text-text-primary shadow-[inset_2px_0_0_rgb(var(--primary-light))]" : "text-text-secondary"
                        }`}
                      >
                        <span className="truncate">{item.label}</span>
                        {item.hint && <span className="text-xs text-text-muted truncate shrink-0 max-w-[45%]">{item.hint}</span>}
                      </li>
                    );
                  })}
                </ul>
              </li>
            );
          })}
        </ul>
        <div className="px-4 py-2 border-t border-border text-[11px] text-text-muted flex gap-4">
          <span>↑↓ to move</span><span>Enter to open</span><span>Ctrl/⌘ K to toggle</span>
        </div>
      </div>
    </div>
  );
}
