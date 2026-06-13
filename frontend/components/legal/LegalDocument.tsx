import React from "react";
import Link from "next/link";

/**
 * Self-contained legal-document page: branded header, scrollable body, and a
 * tiny dependency-free Markdown renderer. The global `body { overflow: hidden }`
 * rule means we own our own scroll container (`h-screen overflow-y-auto`).
 */

interface LegalDocumentProps {
  /** Document title shown in the header (e.g. "Privacy Policy"). */
  title: string;
  /** Raw Markdown body. */
  content: string;
  /** Cross-link shown in the footer. */
  otherDoc: { label: string; href: string };
}

// ── Inline Markdown: **bold**, `code`, [text](url) ──────────────────────────
function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Split on bold / code / link tokens while keeping the delimiters.
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  const parts = text.split(pattern);
  parts.forEach((part, i) => {
    if (!part) return;
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      nodes.push(
        <strong key={key} className="font-semibold text-base-content">
          {part.slice(2, -2)}
        </strong>,
      );
    } else if (part.startsWith("`") && part.endsWith("`")) {
      nodes.push(
        <code
          key={key}
          className="px-1.5 py-0.5 rounded bg-base-300 text-primary text-[0.85em] font-mono"
        >
          {part.slice(1, -1)}
        </code>,
      );
    } else {
      const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (link) {
        const [, label, href] = link;
        const internal = href.startsWith("/");
        nodes.push(
          <a
            key={key}
            href={href}
            {...(internal ? {} : { target: "_blank", rel: "noopener noreferrer" })}
            className="text-primary hover:underline font-medium"
          >
            {label}
          </a>,
        );
      } else {
        nodes.push(<React.Fragment key={key}>{part}</React.Fragment>);
      }
    }
  });
  return nodes;
}

// ── Block-level Markdown renderer ───────────────────────────────────────────
function renderMarkdown(md: string): React.ReactNode[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Blank line
    if (trimmed === "") {
      i++;
      continue;
    }

    // Horizontal rule
    if (/^---+$/.test(trimmed)) {
      blocks.push(<hr key={key++} className="my-8 border-base-300" />);
      i++;
      continue;
    }

    // Headings
    const heading = trimmed.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2];
      if (level === 1) {
        blocks.push(
          <h1 key={key++} className="text-3xl font-bold text-base-content mt-2 mb-4">
            {renderInline(text, `h1-${key}`)}
          </h1>,
        );
      } else if (level === 2) {
        blocks.push(
          <h2 key={key++} className="text-xl font-bold text-base-content mt-10 mb-3 pb-2 border-b border-base-200">
            {renderInline(text, `h2-${key}`)}
          </h2>,
        );
      } else if (level === 3) {
        blocks.push(
          <h3 key={key++} className="text-base font-semibold text-base-content mt-6 mb-2">
            {renderInline(text, `h3-${key}`)}
          </h3>,
        );
      } else {
        blocks.push(
          <h4 key={key++} className="text-sm font-semibold text-base-content/80 mt-4 mb-2">
            {renderInline(text, `h4-${key}`)}
          </h4>,
        );
      }
      i++;
      continue;
    }

    // Tables: a header row followed by a |---| separator row
    if (trimmed.startsWith("|") && i + 1 < lines.length && /^\|[\s:|-]+\|$/.test(lines[i + 1].trim())) {
      const parseRow = (row: string) =>
        row
          .trim()
          .replace(/^\||\|$/g, "")
          .split("|")
          .map((c) => c.trim());
      const headers = parseRow(lines[i]);
      i += 2; // skip header + separator
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(parseRow(lines[i]));
        i++;
      }
      blocks.push(
        <div key={key++} className="my-5 overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-base-300">
                {headers.map((h, hi) => (
                  <th key={hi} className="text-left py-2 px-3 font-semibold text-base-content">
                    {renderInline(h, `th-${key}-${hi}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="border-b border-base-200">
                  {r.map((c, ci) => (
                    <td key={ci} className="py-2 px-3 text-base-content/70 align-top">
                      {renderInline(c, `td-${key}-${ri}-${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // Unordered list
    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ""));
        i++;
      }
      blocks.push(
        <ul key={key++} className="my-3 space-y-1.5 list-disc pl-5 marker:text-primary/60">
          {items.map((it, ii) => (
            <li key={ii} className="text-base-content/70 leading-relaxed">
              {renderInline(it, `li-${key}-${ii}`)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    // Ordered list
    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i++;
      }
      blocks.push(
        <ol key={key++} className="my-3 space-y-1.5 list-decimal pl-5 marker:text-primary/60 marker:font-semibold">
          {items.map((it, ii) => (
            <li key={ii} className="text-base-content/70 leading-relaxed">
              {renderInline(it, `ol-${key}-${ii}`)}
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    // Paragraph — gather consecutive non-blank, non-structural lines
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^(#{1,4})\s+/.test(lines[i].trim()) &&
      !/^---+$/.test(lines[i].trim()) &&
      !/^[-*]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim()) &&
      !lines[i].trim().startsWith("|")
    ) {
      paraLines.push(lines[i].trim());
      i++;
    }
    blocks.push(
      <p key={key++} className="my-3 text-base-content/70 leading-relaxed">
        {paraLines.flatMap((pl, pi) => {
          const inline = renderInline(pl, `p-${key}-${pi}`);
          return pi < paraLines.length - 1 ? [...inline, <br key={`br-${key}-${pi}`} />] : inline;
        })}
      </p>,
    );
  }

  return blocks;
}

export function LegalDocument({ title, content, otherDoc }: LegalDocumentProps) {
  return (
    <div className="h-screen w-screen overflow-y-auto custom-scrollbar bg-base-100">
      {/* Sticky header */}
      <header className="sticky top-0 z-10 bg-base-100/90 backdrop-blur border-b border-base-200">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/mailmind-logo.svg" alt="MailMind" className="w-8 h-8 rounded-lg shadow" />
            <span className="font-bold tracking-tight text-base-content text-base group-hover:text-primary transition-colors">
              MailMind
            </span>
          </Link>
          <Link
            href="/"
            className="text-xs font-semibold text-base-content/60 hover:text-base-content flex items-center gap-1.5 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to home
          </Link>
        </div>
      </header>

      {/* Body */}
      <main className="max-w-3xl mx-auto px-6 py-10 pb-24">
        {renderMarkdown(content)}

        {/* Footer cross-link */}
        <div className="mt-16 pt-8 border-t border-base-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p className="text-xs text-base-content/40">
            © {new Date().getFullYear()} MailMind. All rights reserved.
          </p>
          <Link
            href={otherDoc.href}
            className="text-xs font-semibold text-primary hover:underline flex items-center gap-1.5"
          >
            {otherDoc.label}
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>
      </main>
    </div>
  );
}
