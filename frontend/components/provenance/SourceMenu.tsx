"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  FLAG_LABELS,
  getScope,
  openExternal,
  resolveInputs,
  resolveRefs,
  type Provenance,
  type SourceRef,
} from "@/lib/provenance";

interface MenuRequest {
  x: number;
  y: number;
  refs: SourceRef[];
  /** Map the refs came from, used to resolve a computed metric's inputs. */
  prov?: Provenance;
  /** What was clicked, e.g. "AAPL · P/E" or "Germany · 2023". */
  ctx?: string;
  /** Text offered by "Copy value". */
  value?: string;
}

let openHandler: ((req: MenuRequest) => void) | null = null;

/**
 * Open the Source menu programmatically, for elements that can't carry
 * `data-prov` attributes (e.g. map geographies).
 */
export function openSourceMenu(req: MenuRequest): void {
  openHandler?.(req);
}

function fmtFetched(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-20 shrink-0 text-text-muted">{label}</dt>
      <dd className="min-w-0 break-words text-text-primary">{children}</dd>
    </div>
  );
}

function RefCard({ r, prov, nested = false }: { r: SourceRef; prov?: Provenance; nested?: boolean }) {
  const inputs = nested ? [] : resolveInputs(prov, r);
  return (
    <div className={nested ? "" : "rounded-md border border-border bg-surface-alt/40 p-2.5"}>
      <div className="font-semibold text-text-primary">{r.providerName ?? r.provider}</div>
      {r.flags && r.flags.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {r.flags.map((f) => (
            <span key={f} className="rounded border border-warning/40 bg-warning/10 px-1.5 py-0.5 text-[10px] text-warning">
              {FLAG_LABELS[f] ?? f}
            </span>
          ))}
        </div>
      )}
      <dl className="mt-1.5 space-y-0.5">
        {r.title && <Row label="Data">{r.title}</Row>}
        {r.series && <Row label="Series"><span className="font-mono">{r.series}</span></Row>}
        {r.units && <Row label="Units">{r.units}</Row>}
        {r.frequency && <Row label="Frequency">{r.frequency}</Row>}
        {r.observed && <Row label="As of">{r.observed}</Row>}
        {r.fetchedAt && !nested && <Row label="Fetched">{fmtFetched(r.fetchedAt)}</Row>}
        {r.transform && <Row label="Transform">{r.transform}</Row>}
        {r.formula && <Row label="Formula"><span className="font-mono">{r.formula}</span></Row>}
        {r.note && <Row label="Note">{r.note}</Row>}
      </dl>
      {inputs.length > 0 && (
        <div className="mt-2 border-t border-border pt-2">
          <div className="mb-1 text-text-muted">Computed from</div>
          <ul className="space-y-1.5">
            {inputs.map((inp, i) => (
              <li key={i} className="border-l-2 border-border pl-2">
                {inp.refs.length === 0 ? (
                  <span className="text-text-secondary">{inp.label}</span>
                ) : (
                  inp.refs.map((ir, j) => <RefCard key={j} r={ir} nested />)
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {r.url && (
        <button
          type="button"
          onClick={() => void openExternal(r.url!)}
          className="mt-1.5 text-accent hover:underline"
        >
          Open at source ↗
        </button>
      )}
    </div>
  );
}

/**
 * Right-click → Source. One document-level listener serves the whole app: it
 * only takes over the context menu inside a <SourceScope>, so the browser's
 * own menu still works everywhere else (and with Shift held, everywhere).
 */
export function SourceMenu() {
  const [req, setReq] = useState<MenuRequest | null>(null);
  const [showPanel, setShowPanel] = useState(false);
  const [pos, setPos] = useState({ left: 0, top: 0 });
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const open = (r: MenuRequest) => {
      setShowPanel(false);
      setReq(r);
    };
    openHandler = open;

    function onContextMenu(e: MouseEvent) {
      // A component that handled the event itself (e.g. the Atlas map, via
      // openSourceMenu) has called preventDefault: leave its menu alone.
      if (e.defaultPrevented || e.shiftKey || !(e.target instanceof Element)) return;
      if (boxRef.current?.contains(e.target)) return;
      const innermost = e.target.closest("[data-prov-scope]");
      if (!innermost) return;
      e.preventDefault();

      // Innermost scope first; if its map has no answer (not loaded, or the
      // endpoint carries none), fall back to the enclosing scopes.
      let scopeEl: Element = innermost;
      let point: Element | null = null;
      let prov: Provenance | undefined;
      let key: string | null | undefined;
      let refs: SourceRef[] = [];
      for (let s: Element | null = innermost; s; s = s.parentElement?.closest("[data-prov-scope]") ?? null) {
        const pointEl = e.target.closest("[data-prov]");
        const p = pointEl && s.contains(pointEl) ? pointEl : null;
        const map = getScope(s.getAttribute("data-prov-scope") ?? "");
        const k = p?.getAttribute("data-prov");
        const found = resolveRefs(map, k);
        if (s === innermost || found.length) {
          scopeEl = s;
          point = p;
          prov = map;
          key = k;
          refs = found;
        }
        if (found.length) break;
      }
      const ctxEl = e.target.closest("[data-prov-ctx]");

      // The keyboard context-menu key reports (0, 0): anchor to the element.
      let { clientX: x, clientY: y } = e;
      if (x === 0 && y === 0) {
        const rect = (point ?? e.target).getBoundingClientRect();
        x = rect.left;
        y = rect.bottom;
      }

      // "Copy value" takes the selection, else the clicked table cell, else
      // the annotated element (a whole row's text is rarely what is wanted).
      const selection = window.getSelection()?.toString().trim();
      const cell = e.target.closest("td, th, [data-prov]");
      const valueEl = cell && scopeEl.contains(cell) ? cell : point;
      const text = selection || (valueEl as HTMLElement | null)?.innerText?.trim();
      open({
        x,
        y,
        prov,
        refs,
        ctx: (ctxEl && scopeEl.contains(ctxEl) ? ctxEl.getAttribute("data-prov-ctx") : null) ?? undefined,
        value: text ? text.slice(0, 500) : undefined,
      });
      if (process.env.NODE_ENV !== "production" && refs.length === 0) {
        console.warn("[provenance] no source annotated for", key ?? "(no data-prov key)");
      }
    }

    document.addEventListener("contextmenu", onContextMenu);
    return () => {
      document.removeEventListener("contextmenu", onContextMenu);
      openHandler = null;
    };
  }, []);

  useEffect(() => {
    if (!req) return;
    const close = () => setReq(null);
    function onMouseDown(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) close();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", close);
    };
  }, [req]);

  // Keep the box inside the viewport, and move focus into it.
  useLayoutEffect(() => {
    const box = boxRef.current;
    if (!req || !box) return;
    const { width, height } = box.getBoundingClientRect();
    setPos({
      left: Math.max(8, Math.min(req.x, window.innerWidth - width - 8)),
      top: Math.max(8, Math.min(req.y, window.innerHeight - height - 8)),
    });
    // Menu: focus the first item so Enter activates it. Panel: focus the
    // panel itself so it can be read and dismissed with Esc.
    (showPanel ? box : box.querySelector("button") ?? box).focus();
  }, [req, showPanel]);

  if (!req) return null;

  const base = "fixed z-[100] bg-surface border border-border rounded-lg shadow-xl text-xs text-text-primary";
  const item = "block w-full px-3 py-1.5 text-left hover:bg-surface-alt focus:bg-surface-alt focus:outline-none";

  if (!showPanel) {
    return (
      <div ref={boxRef} role="menu" tabIndex={-1} style={pos} className={`${base} min-w-[150px] py-1`}>
        <button type="button" role="menuitem" className={item} onClick={() => setShowPanel(true)}>
          Source
        </button>
        {req.value && (
          <button
            type="button"
            role="menuitem"
            className={item}
            onClick={() => {
              void navigator.clipboard?.writeText(req.value!);
              setReq(null);
            }}
          >
            Copy value
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      ref={boxRef}
      role="dialog"
      aria-label="Data source"
      tabIndex={-1}
      style={pos}
      className={`${base} w-[340px] max-w-[calc(100vw-16px)] max-h-[70vh] overflow-y-auto p-3 leading-relaxed focus:outline-none`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-text-muted">Source</div>
          {req.ctx && <div className="font-medium text-text-secondary">{req.ctx}</div>}
        </div>
        <button
          type="button"
          aria-label="Close"
          onClick={() => setReq(null)}
          className="text-text-muted hover:text-text-primary"
        >
          ✕
        </button>
      </div>
      {req.refs.length === 0 ? (
        <p className="text-text-secondary">Source not annotated for this value.</p>
      ) : (
        <div className="space-y-2">
          {req.refs.map((r, i) => (
            <RefCard key={i} r={r} prov={req.prov} />
          ))}
        </div>
      )}
    </div>
  );
}
