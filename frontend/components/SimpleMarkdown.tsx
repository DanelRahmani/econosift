import { Fragment, type ReactNode } from "react";

// Renders the small Markdown subset Gemini writes (headings, bullet and
// numbered lists, **bold**, *italic*, `code`) as React elements. The text is
// never injected as HTML, so model output cannot add markup or scripts.

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;

function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      return <strong key={i} className="font-semibold text-text-primary">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`"))
      return <code key={i} className="rounded bg-surface-alt px-1 py-0.5 font-mono text-[0.85em]">{part.slice(1, -1)}</code>;
    if (part.length > 2 && part.startsWith("*") && part.endsWith("*"))
      return <em key={i}>{part.slice(1, -1)}</em>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

type Block =
  | { kind: "h"; level: number; text: string }
  | { kind: "p"; text: string }
  | { kind: "ul" | "ol"; items: string[] };

function parse(src: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ kind: "p", text: para.join(" ") });
    para = [];
  };
  for (const raw of src.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trim();
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    const ul = /^[-*•]\s+(.*)$/.exec(line);
    const ol = /^\d+[.)]\s+(.*)$/.exec(line);
    if (!line) { flush(); continue; }
    if (h) { flush(); blocks.push({ kind: "h", level: h[1].length, text: h[2].replace(/\*\*/g, "") }); continue; }
    if (ul || ol) {
      flush();
      const kind = ul ? "ul" : "ol";
      const item = (ul ?? ol)![1];
      const last = blocks[blocks.length - 1];
      if (last && last.kind === kind) last.items.push(item);
      else blocks.push({ kind, items: [item] });
      continue;
    }
    para.push(line);
  }
  flush();
  return blocks;
}

export function SimpleMarkdown({ text, className = "" }: { text: string; className?: string }) {
  return (
    <div className={`space-y-3 ${className}`}>
      {parse(text).map((b, i) => {
        if (b.kind === "h")
          return (
            <h4 key={i} className={`font-display font-semibold text-text-primary ${b.level <= 2 ? "text-base pt-1" : "text-sm"}`}>
              {inline(b.text)}
            </h4>
          );
        if (b.kind === "p") return <p key={i}>{inline(b.text)}</p>;
        const List = b.kind === "ul" ? "ul" : "ol";
        return (
          <List key={i} className={`space-y-1.5 pl-5 ${b.kind === "ul" ? "list-disc marker:text-accent-light" : "list-decimal marker:text-text-muted"}`}>
            {b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}
          </List>
        );
      })}
    </div>
  );
}
