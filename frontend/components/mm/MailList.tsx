"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  MailOpen,
  Mail,
  Paperclip,
  RefreshCw,
  Search,
  Star,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
import type { Email, Priority } from "../../lib/types";
import { PriorityOverrideMenu, type OverridePriority } from "../inbox/PriorityOverrideMenu";
import {
  CATEGORY_LABEL,
  PRIORITY_ORDER,
  categoryOf,
  dayBucket,
  priorityOf,
  reasonFor,
  senderName,
  displayName,
  shortTime,
} from "./format";
import { Avatar, IconButton, PriorityChip, Tag } from "./ui";

export type ListMode = "needs" | "all" | "folder";

interface MailListProps {
  title: string;
  mode: ListMode;
  emails: Email[];
  selectedId: string | null;
  onOpen: (id: string) => void;
  onModeChange?: (m: "needs" | "all") => void;
  showModeSwitch: boolean;
  triageApplies: boolean;
  search: string;
  onSearch: (q: string) => void;
  loading: boolean;
  onRefresh: () => void;
  // paging
  total: number;
  pageIndex: number;
  pageSize: number;
  hasNext: boolean;
  hasPrev: boolean;
  onNext: () => void;
  onPrev: () => void;
  // triage stream
  streaming: boolean;
  triageDone: number;
  triageTotal: number;
  // actions
  onStar: (id: string) => void;
  onDone?: (id: string, sender: string, priority?: string) => void;
  onArchive?: (id: string) => void;
  onTrash?: (id: string) => void;
  onRestore?: (id: string) => void;
  onToggleRead?: (id: string, read: boolean) => void;
  onOverride?: (id: string, sender: string, p: OverridePriority, current: Priority) => void;
  onShowAll?: () => void;
}

function RowActions({
  email,
  onStar, onDone, onArchive, onTrash, onRestore, onToggleRead,
}: Pick<MailListProps, "onStar" | "onDone" | "onArchive" | "onTrash" | "onRestore" | "onToggleRead"> & { email: Email }) {
  const stop = (fn: () => void) => (e: React.MouseEvent) => { e.stopPropagation(); fn(); };
  const unread = email.isRead === false;
  return (
    <div className="pointer-events-none absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-0.5 rounded-full border border-rule bg-surface px-1 py-0.5 opacity-0 shadow-paper transition-opacity duration-150 group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100">
      {onDone && <IconButton icon={CircleCheck} label="Done" onClick={stop(() => onDone(email.id, email.sender, email.triage?.priority))} />}
      {onArchive && <IconButton icon={Archive} label="Archive" onClick={stop(() => onArchive(email.id))} />}
      {onToggleRead && (
        <IconButton icon={unread ? MailOpen : Mail} label={unread ? "Mark read" : "Mark unread"} onClick={stop(() => onToggleRead(email.id, unread))} />
      )}
      <IconButton icon={Star} label={email.isStarred ? "Unstar" : "Star"} active={email.isStarred} onClick={stop(() => onStar(email.id))} />
      {onRestore && <IconButton icon={Undo2} label="Restore" onClick={stop(() => onRestore(email.id))} />}
      {onTrash && <IconButton icon={Trash2} label="Delete" tone="danger" onClick={stop(() => onTrash(email.id))} />}
    </div>
  );
}

function MailRow({
  email, selected, showReason, showPriority, triageApplies, onOpen, onOverride, now, ...actions
}: {
  email: Email;
  selected: boolean;
  showReason: boolean;
  showPriority: boolean;
  triageApplies: boolean;
  onOpen: () => void;
  onOverride?: MailListProps["onOverride"];
  now: number;
} & Pick<MailListProps, "onStar" | "onDone" | "onArchive" | "onTrash" | "onRestore" | "onToggleRead">) {
  const name = displayName(email);
  const unread = email.isRead === false;
  const priority = priorityOf(email);
  const cat = categoryOf(email);
  const reason = showReason ? reasonFor(email) : null;
  const score = email.triage?.composite_score ?? email.composite_score;
  const pending = triageApplies && !email.triage && email.composite_score === undefined;
  const snippet = (email.body || "").replace(/\s+/g, " ").trim();

  return (
    <li className="group relative" data-selected={selected || undefined}>
      <button
        type="button"
        onClick={onOpen}
        aria-current={selected ? "true" : undefined}
        className={`mm-settle grid w-full grid-cols-[auto_minmax(0,1fr)] gap-3 px-4 py-3 text-left transition-colors duration-150 cursor-pointer ${
          selected ? "bg-cobalt-soft" : "hover:bg-hover"
        }`}
      >
        <span className="relative mt-0.5">
          <Avatar name={name} size={32} />
          {unread && (
            <span className="absolute -left-1.5 top-1/2 size-1.5 -translate-y-1/2 rounded-full bg-cobalt" aria-label="Unread" />
          )}
        </span>
        <span className="min-w-0">
          <span className="flex items-baseline gap-2">
            <span className={`truncate text-[13.5px] ${unread ? "font-semibold text-ink" : "font-medium text-ink-2"}`}>{name}</span>
            {cat && <Tag className="shrink-0">{CATEGORY_LABEL[cat]}</Tag>}
            <span className="ml-auto flex shrink-0 items-center gap-1.5">
              {email.hasAttachments && <Paperclip className="size-3.5 text-ink-3" strokeWidth={1.75} aria-label="Has attachment" />}
              {email.isStarred && <Star className="size-3.5 fill-soon text-soon" strokeWidth={1.75} aria-label="Starred" />}
              {triageApplies && typeof score === "number" && score > 0 && (
                <span className="text-[11.5px] font-medium tabular-nums text-ink-3" title="Priority score out of 100">{Math.round(score)}</span>
              )}
              {showPriority && priority && (priority === "CRITICAL" || priority === "HIGH") && (
                onOverride ? (
                  <span onClick={(e) => e.stopPropagation()}>
                    <PriorityOverrideMenu current={priority} onOverride={(p) => onOverride(email.id, email.sender, p, priority)}>
                      <PriorityChip priority={priority} />
                    </PriorityOverrideMenu>
                  </span>
                ) : (
                  <PriorityChip priority={priority} />
                )
              )}
              {pending && <span className="mm-skeleton h-4 w-10" aria-label="Sorting" />}
              <time className="text-[12px] tabular-nums text-ink-3" dateTime={email.received_at} suppressHydrationWarning>
                {shortTime(email.received_at, now)}
              </time>
            </span>
          </span>
          <span className="mt-0.5 block truncate text-[13px]">
            <span className={unread ? "font-medium text-ink" : "text-ink"}>{email.subject || "(no subject)"}</span>
            {snippet && <span className="text-ink-3">  {snippet.slice(0, 160)}</span>}
          </span>
          {reason && (
            <span className="mt-1 block text-[12.5px] leading-snug text-cobalt">{reason}</span>
          )}
        </span>
      </button>
      <RowActions email={email} {...actions} />
    </li>
  );
}

function GroupHeader({ label, count, tone }: { label: string; count?: number; tone?: "urgent" | "soon" }) {
  return (
    <li
      role="presentation"
      className="sticky top-0 z-10 flex items-center gap-2 border-b border-rule bg-bg/95 px-4 py-1.5 text-[12px] font-medium text-ink-3 backdrop-blur"
    >
      <span className={tone === "urgent" ? "text-urgent" : tone === "soon" ? "text-soon" : undefined}>{label}</span>
      {count !== undefined && <span className="tabular-nums">{count}</span>}
    </li>
  );
}

function SkeletonRows() {
  return (
    <ul aria-hidden className="divide-y divide-rule">
      {Array.from({ length: 7 }).map((_, i) => (
        <li key={i} className="flex gap-3 px-4 py-3.5">
          <span className="mm-skeleton size-8 shrink-0 rounded-full" />
          <span className="flex-1 space-y-2">
            <span className="mm-skeleton block h-3 w-1/3" />
            <span className="mm-skeleton block h-3 w-4/5" />
          </span>
        </li>
      ))}
    </ul>
  );
}

export function MailList(props: MailListProps) {
  const {
    title, mode, emails, selectedId, onOpen, onModeChange, showModeSwitch, triageApplies,
    search, onSearch, loading, onRefresh, total, pageIndex, pageSize, hasNext, hasPrev, onNext, onPrev,
    streaming, triageDone, triageTotal, onOverride, onShowAll, ...actions
  } = props;

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);

  const groups = useMemo(() => {
    if (mode === "needs") {
      const sorted = [...emails].sort((a, b) => {
        const pa = PRIORITY_ORDER[priorityOf(a) ?? "LOW"];
        const pb = PRIORITY_ORDER[priorityOf(b) ?? "LOW"];
        if (pa !== pb) return pa - pb;
        return (b.composite_score ?? 0) - (a.composite_score ?? 0);
      });
      const now_ = sorted.filter((e) => priorityOf(e) === "CRITICAL");
      const soon = sorted.filter((e) => priorityOf(e) === "HIGH");
      return [
        { key: "now", label: "Needs you now", tone: "urgent" as const, items: now_ },
        { key: "soon", label: "Needs you soon", tone: "soon" as const, items: soon },
      ].filter((g) => g.items.length);
    }
    const order = ["Today", "Yesterday", "This week", "Earlier"];
    const map = new Map<string, Email[]>();
    for (const e of emails) {
      const k = dayBucket(e.received_at, now);
      map.set(k, [...(map.get(k) ?? []), e]);
    }
    return order.filter((k) => map.has(k)).map((k) => ({ key: k, label: k, tone: undefined, items: map.get(k)! }));
  }, [emails, mode, now]);

  const sorting = streaming && triageTotal > 0;
  const from = pageIndex * pageSize + (emails.length ? 1 : 0);
  const to = pageIndex * pageSize + emails.length;

  return (
    <section aria-label={title} className="flex h-full min-w-0 flex-col bg-surface">
      <header className="shrink-0 border-b border-rule px-4 pb-3 pt-4">
        <div className="flex items-center gap-2">
          <h1 className="text-[17px] font-semibold tracking-tight text-ink">{title}</h1>
          {showModeSwitch && onModeChange && (
            <div role="tablist" aria-label="Inbox view" className="ml-2 inline-flex rounded-full bg-sunk p-0.5">
              {(["needs", "all"] as const).map((m) => (
                <button
                  key={m}
                  role="tab"
                  type="button"
                  aria-selected={mode === m}
                  onClick={() => onModeChange(m)}
                  className={`h-7 rounded-full px-3 text-[12.5px] font-medium transition-colors cursor-pointer ${
                    mode === m ? "bg-surface text-ink shadow-paper" : "text-ink-3 hover:text-ink"
                  }`}
                >
                  {m === "needs" ? "Needs you" : "Everything"}
                </button>
              ))}
            </div>
          )}
          <div className="ml-auto flex items-center gap-0.5">
            {total > 0 && mode !== "needs" && (
              <>
                <span className="mr-1 text-[12px] tabular-nums text-ink-3">
                  {from}-{to} of {total.toLocaleString()}
                </span>
                <IconButton icon={ChevronLeft} label="Newer" onClick={onPrev} disabled={!hasPrev || loading} />
                <IconButton icon={ChevronRight} label="Older" onClick={onNext} disabled={!hasNext || loading} />
              </>
            )}
            <IconButton icon={RefreshCw} label="Refresh" onClick={onRefresh} disabled={loading} className={loading ? "[&>svg]:animate-spin" : ""} />
          </div>
        </div>

        <label className="mt-3 flex h-9 items-center gap-2 rounded-full bg-sunk px-3 text-ink-3 focus-within:ring-2 focus-within:ring-cobalt/40">
          <Search className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />
          <span className="sr-only">Search mail</span>
          <input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search mail"
            className="h-full min-w-0 flex-1 bg-transparent text-[13.5px] text-ink placeholder:text-ink-3 focus:outline-none"
          />
          {search && <IconButton icon={X} label="Clear search" onClick={() => onSearch("")} className="-mr-2 size-7" />}
          <kbd className="hidden rounded border border-rule px-1 font-mono text-[10px] text-ink-3 md:inline">/</kbd>
        </label>

        {sorting && (
          <p className="mt-2.5 flex items-center gap-2 text-[12.5px] text-ink-2" aria-live="polite">
            <span className="relative h-1 w-16 overflow-hidden rounded-full bg-sunk">
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-cobalt transition-[width] duration-500 ease-out-expo"
                style={{ width: `${Math.min(100, (triageDone / Math.max(1, triageTotal)) * 100)}%` }}
              />
            </span>
            Reading ahead: {triageDone} of {triageTotal} new emails sorted
          </p>
        )}
      </header>

      <div className="mm-scroll min-h-0 flex-1 overflow-y-auto">
        {loading && emails.length === 0 ? (
          <SkeletonRows />
        ) : groups.length === 0 ? (
          <EmptyState mode={mode} searching={!!search} sorting={sorting} onShowAll={onShowAll} />
        ) : (
          <ul>
            {groups.map((g) => (
              <React.Fragment key={g.key}>
                <GroupHeader label={g.label} count={mode === "needs" ? g.items.length : undefined} tone={g.tone} />
                {g.items.map((e) => (
                  <MailRow
                    key={e.id}
                    email={e}
                    now={now}
                    selected={e.id === selectedId}
                    showReason={mode === "needs"}
                    showPriority={mode !== "needs" && triageApplies}
                    triageApplies={triageApplies}
                    onOpen={() => onOpen(e.id)}
                    onOverride={onOverride}
                    {...actions}
                  />
                ))}
              </React.Fragment>
            ))}
            {mode === "needs" && onShowAll && (
              <li className="px-4 py-5 text-center">
                <button type="button" onClick={onShowAll} className="text-[13px] font-medium text-cobalt hover:underline cursor-pointer">
                  Everything else is filed in Everything, nothing deleted
                </button>
              </li>
            )}
          </ul>
        )}
      </div>
    </section>
  );
}

function EmptyState({ mode, searching, sorting, onShowAll }: { mode: ListMode; searching: boolean; sorting: boolean; onShowAll?: () => void }) {
  if (searching) {
    return (
      <div className="px-8 py-16 text-center">
        <p className="text-[14px] font-medium text-ink">No mail matches that search</p>
        <p className="mt-1 text-[13px] text-ink-3">Try a sender, a subject word or a course code.</p>
      </div>
    );
  }
  if (mode === "needs") {
    return (
      <div className="px-8 py-16 text-center">
        <CircleCheck className="mx-auto size-8 text-ok" strokeWidth={1.5} aria-hidden />
        <p className="mt-3 text-[15px] font-medium text-ink">
          {sorting ? "Still reading your new mail" : "Nothing needs you right now"}
        </p>
        <p className="mx-auto mt-1 max-w-[34ch] text-[13px] text-ink-3">
          {sorting
            ? "Anything with a deadline or a request for you will appear here as it is sorted."
            : "No deadlines, requests or warnings are waiting on you. The rest of your mail is still in Everything."}
        </p>
        {onShowAll && !sorting && (
          <button type="button" onClick={onShowAll} className="mt-4 text-[13px] font-medium text-cobalt hover:underline cursor-pointer">
            Open Everything
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="px-8 py-16 text-center">
      <p className="text-[14px] font-medium text-ink">Nothing here</p>
      <p className="mt-1 text-[13px] text-ink-3">This folder is empty.</p>
    </div>
  );
}
