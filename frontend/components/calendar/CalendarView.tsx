"use client";

import React, { useState, useMemo } from "react";
import { CalendarEvent } from "../../lib/types";

interface CalendarViewProps {
  events: CalendarEvent[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onCreateEvent?: (event: Partial<CalendarEvent>) => Promise<void>;
}

type ViewMode = "month" | "week" | "agenda";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function isSameDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function fmt(iso: string, opts: Intl.DateTimeFormatOptions) {
  try {
    return new Date(iso).toLocaleString(undefined, opts);
  } catch {
    return "";
  }
}

function getDuration(start: string, end: string) {
  try {
    const ms = new Date(end).getTime() - new Date(start).getTime();
    const mins = Math.round(ms / 60000);
    if (mins < 60) return `${mins}m`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m ? `${h}h ${m}m` : `${h}h`;
  } catch {
    return "";
  }
}

const EVENT_COLORS = [
  "bg-blue-500/20 border-blue-500/40 text-blue-400",
  "bg-purple-500/20 border-purple-500/40 text-purple-400",
  "bg-emerald-500/20 border-emerald-500/40 text-emerald-400",
  "bg-amber-500/20 border-amber-500/40 text-amber-400",
  "bg-pink-500/20 border-pink-500/40 text-pink-400",
  "bg-cyan-500/20 border-cyan-500/40 text-cyan-400",
];

function eventColor(idx: number) {
  return EVENT_COLORS[idx % EVENT_COLORS.length];
}

export function CalendarView({
  events,
  loading,
  error,
  onRefresh,
  onCreateEvent,
}: CalendarViewProps) {
  const today = new Date();
  const [view, setView] = useState<ViewMode>("month");
  const [cursor, setCursor] = useState(
    new Date(today.getFullYear(), today.getMonth(), 1),
  );
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  // ── Month grid ───────────────────────────────────────────────────────────
  const monthDays = useMemo(() => {
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const cells: (Date | null)[] = Array(firstDay).fill(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
    while (cells.length % 7 !== 0) cells.push(null);
    return cells;
  }, [cursor]);

  // ── Week grid ────────────────────────────────────────────────────────────
  const weekDays = useMemo(() => {
    const d = new Date(cursor);
    const day = d.getDay();
    d.setDate(d.getDate() - day);
    return Array.from({ length: 7 }, (_, i) => {
      const wd = new Date(d);
      wd.setDate(d.getDate() + i);
      return wd;
    });
  }, [cursor]);

  function eventsForDay(day: Date) {
    return events.filter((e) => {
      try {
        return isSameDay(new Date(e.start_time), day);
      } catch {
        return false;
      }
    });
  }

  function prevPeriod() {
    const d = new Date(cursor);
    if (view === "month") d.setMonth(d.getMonth() - 1);
    else if (view === "week") d.setDate(d.getDate() - 7);
    setCursor(d);
  }

  function nextPeriod() {
    const d = new Date(cursor);
    if (view === "month") d.setMonth(d.getMonth() + 1);
    else if (view === "week") d.setDate(d.getDate() + 7);
    setCursor(d);
  }

  function goToday() {
    setCursor(
      view === "month"
        ? new Date(today.getFullYear(), today.getMonth(), 1)
        : new Date(today),
    );
  }

  const periodLabel =
    view === "month"
      ? `${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}`
      : view === "week"
        ? `${fmt(weekDays[0].toISOString(), { month: "short", day: "numeric" })} – ${fmt(weekDays[6].toISOString(), { month: "short", day: "numeric", year: "numeric" })}`
        : "Agenda";

  // Sorted upcoming events for agenda view
  const sortedEvents = useMemo(
    () =>
      [...events].sort(
        (a, b) =>
          new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
      ),
    [events],
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle || !newStart || !onCreateEvent) return;
    setCreating(true);
    try {
      await onCreateEvent({
        title: newTitle,
        start_time: newStart,
        end_time: newEnd || newStart,
        organizer: "",
      });
      setShowCreate(false);
      setNewTitle("");
      setNewStart("");
      setNewEnd("");
      setNewDesc("");
      onRefresh();
    } finally {
      setCreating(false);
    }
  }

  // ── Render helpers ────────────────────────────────────────────────────────
  function EventPill({
    event,
    idx,
    compact = false,
  }: {
    event: CalendarEvent;
    idx: number;
    compact?: boolean;
  }) {
    return (
      <button
        onClick={(e) => {
          e.stopPropagation();
          setSelected(event);
        }}
        className={`w-full text-left text-[10px] font-semibold px-1.5 py-0.5 rounded border truncate
          ${eventColor(idx)} hover:brightness-125 transition-all cursor-pointer`}
        title={event.title}
      >
        {!compact && (
          <span className="mr-1 opacity-70">
            {fmt(event.start_time, { hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
        {event.title}
      </button>
    );
  }

  return (
    <div
      className="flex-1 bg-[var(--bg-base)] flex flex-col h-full overflow-hidden text-left"
      id="calendar-view"
    >
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="px-6 pt-6 pb-4 border-b border-[var(--border-subtle)] flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-[var(--text-primary)]">
            Calendar
          </h2>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Synchronized with Microsoft Graph / Outlook
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* View toggle */}
          <div className="flex rounded-lg overflow-hidden border border-[var(--border)] text-xs font-bold">
            {(["month", "week", "agenda"] as ViewMode[]).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-1.5 capitalize transition-colors cursor-pointer
                  ${view === v ? "bg-[var(--accent-primary)] text-black dark:bg-blue-600 dark:text-white font-bold" : "bg-[var(--bg-surface)] text-[var(--text-muted)] hover:bg-[var(--bg-elevated)]"}`}
              >
                {v}
              </button>
            ))}
          </div>

          {/* Nav */}
          {view !== "agenda" && (
            <div className="flex items-center gap-1">
              <button
                onClick={prevPeriod}
                className="w-7 h-7 flex items-center justify-center rounded bg-[var(--bg-surface)] border border-[var(--border)] hover:bg-[var(--bg-elevated)] cursor-pointer text-[var(--text-primary)]"
              >
                ‹
              </button>
              <button
                onClick={goToday}
                className="px-2 h-7 text-xs font-bold rounded bg-[var(--bg-surface)] border border-[var(--border)] hover:bg-[var(--bg-elevated)] cursor-pointer text-[var(--text-primary)]"
              >
                Today
              </button>
              <button
                onClick={nextPeriod}
                className="w-7 h-7 flex items-center justify-center rounded bg-[var(--bg-surface)] border border-[var(--border)] hover:bg-[var(--bg-elevated)] cursor-pointer text-[var(--text-primary)]"
              >
                ›
              </button>
            </div>
          )}

          <span className="text-sm font-bold text-[var(--text-primary)] min-w-[180px] text-center">
            {periodLabel}
          </span>

          {/* Create + Refresh */}
          {onCreateEvent && (
            <button
              onClick={() => setShowCreate(true)}
              className="px-3 h-7 text-xs font-bold rounded bg-[var(--accent-primary)] text-black dark:bg-blue-600 dark:text-white hover:opacity-90 cursor-pointer flex items-center gap-1"
            >
              <span className="text-base leading-none">+</span> Event
            </button>
          )}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="px-3 h-7 text-xs font-semibold rounded border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] disabled:opacity-50 cursor-pointer flex items-center gap-1"
          >
            {loading ? (
              <span className="w-3 h-3 border border-[var(--text-muted)] border-t-[var(--text-primary)] rounded-full animate-spin" />
            ) : (
              "↻"
            )}
            {loading ? "Syncing" : "Sync"}
          </button>
        </div>
      </div>

      {/* ── Stats bar ──────────────────────────────────────────────────────── */}
      <div className="px-6 py-2 flex gap-6 border-b border-[var(--border-subtle)] shrink-0">
        {[
          { label: "Total Events", value: events.length },
          {
            label: "Today",
            value: events.filter((e) => {
              try {
                return isSameDay(new Date(e.start_time), today);
              } catch {
                return false;
              }
            }).length,
          },
          {
            label: "This Week",
            value: events.filter((e) => {
              try {
                const d = new Date(e.start_time);
                const diff = (d.getTime() - today.getTime()) / 86400000;
                return diff >= 0 && diff < 7;
              } catch {
                return false;
              }
            }).length,
          },
          {
            label: "Sync Status",
            value: loading ? "Syncing…" : error ? "Error" : "Live",
          },
        ].map((s) => (
          <div key={s.label} className="text-center">
            <div className="text-base font-bold text-[var(--text-primary)]">
              {s.value}
            </div>
            <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* ── Main content ───────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden flex">
        <div className="flex-1 overflow-auto p-4">
          {loading && events.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="w-8 h-8 border-2 border-[var(--border)] border-t-[var(--accent-primary)] rounded-full animate-spin mx-auto mb-3" />
                <p className="text-xs text-[var(--text-muted)]">
                  Fetching calendar from Microsoft Graph…
                </p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-sm space-y-3">
                <div className="text-3xl">📅</div>
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  Calendar unavailable
                </p>
                <p className="text-xs text-[var(--text-muted)]">{error}</p>
                <p className="text-xs text-[var(--text-muted)]">
                  Sign in with a Microsoft account to sync Outlook calendar.
                </p>
                <button
                  onClick={onRefresh}
                  className="px-4 py-2 text-xs font-bold bg-[var(--accent-primary)] text-white rounded-lg hover:opacity-90 cursor-pointer"
                >
                  Retry
                </button>
              </div>
            </div>
          ) : view === "month" ? (
            // ── MONTH VIEW ──────────────────────────────────────────────────
            <div className="min-w-[560px]">
              {/* Weekday headers */}
              <div className="grid grid-cols-7 mb-1">
                {WEEKDAYS.map((d) => (
                  <div
                    key={d}
                    className="py-1 text-center text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider"
                  >
                    {d}
                  </div>
                ))}
              </div>
              {/* Day cells */}
              <div className="grid grid-cols-7 gap-px bg-[var(--border-subtle)] rounded-lg overflow-hidden border border-[var(--border-subtle)]">
                {monthDays.map((day, i) => {
                  const dayEvents = day ? eventsForDay(day) : [];
                  const isToday = day ? isSameDay(day, today) : false;
                  const isOtherMonth = !day;
                  return (
                    <div
                      key={i}
                      className={`min-h-[90px] p-1.5 flex flex-col bg-[var(--bg-surface)]
                        ${isOtherMonth ? "opacity-30" : "hover:bg-[var(--bg-elevated)]"}
                        ${isToday ? "ring-1 ring-inset ring-[var(--accent-primary)]" : ""}`}
                    >
                      {day && (
                        <>
                          <span
                            className={`text-xs font-bold mb-1 self-start w-6 h-6 flex items-center justify-center rounded-full
                            ${isToday ? "bg-[var(--accent-primary)] text-black dark:bg-blue-600 dark:text-white" : "text-[var(--text-muted)]"}`}
                          >
                            {day.getDate()}
                          </span>
                          <div className="space-y-0.5 overflow-hidden">
                            {dayEvents.slice(0, 3).map((ev, idx) => (
                              <EventPill
                                key={idx}
                                event={ev}
                                idx={events.indexOf(ev)}
                                compact
                              />
                            ))}
                            {dayEvents.length > 3 && (
                              <span className="text-[9px] text-[var(--text-muted)] pl-1">
                                +{dayEvents.length - 3} more
                              </span>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : view === "week" ? (
            // ── WEEK VIEW ──────────────────────────────────────────────────
            <div className="min-w-[560px]">
              <div className="grid grid-cols-7 gap-px bg-[var(--border-subtle)] rounded-lg overflow-hidden border border-[var(--border-subtle)]">
                {weekDays.map((day, i) => {
                  const dayEvents = eventsForDay(day);
                  const isToday = isSameDay(day, today);
                  return (
                    <div
                      key={i}
                      className={`flex flex-col bg-[var(--bg-surface)] min-h-[300px]
                      ${isToday ? "ring-1 ring-inset ring-[var(--accent-primary)]" : ""}`}
                    >
                      {/* Day header */}
                      <div
                        className={`p-2 text-center border-b border-[var(--border-subtle)]
                        ${isToday ? "bg-[var(--accent-primary)]/10" : ""}`}
                      >
                        <div className="text-[10px] font-bold text-[var(--text-muted)] uppercase">
                          {WEEKDAYS[day.getDay()]}
                        </div>
                        <div
                          className={`text-sm font-bold mt-0.5
                          ${isToday ? "text-[var(--accent-primary)]" : "text-[var(--text-primary)]"}`}
                        >
                          {day.getDate()}
                        </div>
                      </div>
                      {/* Events */}
                      <div className="p-1.5 space-y-1 flex-1">
                        {dayEvents.length === 0 ? (
                          <div className="h-full flex items-center justify-center">
                            <span className="text-[9px] text-[var(--text-muted)] opacity-50">
                              —
                            </span>
                          </div>
                        ) : (
                          dayEvents.map((ev, idx) => (
                            <EventPill
                              key={idx}
                              event={ev}
                              idx={events.indexOf(ev)}
                            />
                          ))
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            // ── AGENDA VIEW ──────────────────────────────────────────────
            <div className="max-w-2xl space-y-2">
              {sortedEvents.length === 0 ? (
                <div className="py-16 text-center">
                  <div className="text-4xl mb-3">📭</div>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">
                    No upcoming events
                  </p>
                  <p className="text-xs text-[var(--text-muted)] mt-1">
                    Your calendar is clear for the next 7 days.
                  </p>
                </div>
              ) : (
                (() => {
                  let lastDate = "";
                  return sortedEvents.map((event, idx) => {
                    const dateLabel = fmt(event.start_time, {
                      weekday: "long",
                      month: "long",
                      day: "numeric",
                    });
                    const showDateHeader = dateLabel !== lastDate;
                    lastDate = dateLabel;
                    const isToday = isSameDay(
                      new Date(event.start_time),
                      today,
                    );
                    return (
                      <React.Fragment key={idx}>
                        {showDateHeader && (
                          <div
                            className={`pt-4 pb-1 text-xs font-bold uppercase tracking-wider
                            ${isToday ? "text-[var(--accent-primary)]" : "text-[var(--text-muted)]"}`}
                          >
                            {isToday ? "⭐ Today — " : ""}
                            {dateLabel}
                          </div>
                        )}
                        <button
                          onClick={() => setSelected(event)}
                          className="w-full text-left p-4 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)]
                            hover:border-[var(--border)] hover:bg-[var(--bg-elevated)] transition-all cursor-pointer group"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-3 min-w-0">
                              <div
                                className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${eventColor(idx).split(" ")[0].replace("bg-", "bg-").replace("/20", "/80")}`}
                              />
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-[var(--text-primary)] truncate">
                                  {event.title}
                                </p>
                                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                                  {event.organizer &&
                                  event.organizer !== "unknown@example.com"
                                    ? `By ${event.organizer}`
                                    : ""}
                                </p>
                              </div>
                            </div>
                            <div className="text-right shrink-0">
                              <p className="text-xs font-mono font-semibold text-[var(--text-primary)]">
                                {fmt(event.start_time, {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </p>
                              <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                                {getDuration(event.start_time, event.end_time)}
                              </p>
                            </div>
                          </div>
                        </button>
                      </React.Fragment>
                    );
                  });
                })()
              )}
            </div>
          )}
        </div>

        {/* ── Event detail panel ───────────────────────────────────────────── */}
        {selected && (
          <div className="w-72 border-l border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 flex flex-col gap-4 shrink-0 overflow-y-auto">
            <div className="flex items-start justify-between">
              <h3 className="text-sm font-bold text-[var(--text-primary)] leading-snug flex-1 pr-2">
                {selected.title}
              </h3>
              <button
                onClick={() => setSelected(null)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer text-lg leading-none"
              >
                ×
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)] space-y-2">
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Date</span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {fmt(selected.start_time, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Start</span>
                  <span className="font-mono font-semibold text-[var(--text-primary)]">
                    {fmt(selected.start_time, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">End</span>
                  <span className="font-mono font-semibold text-[var(--text-primary)]">
                    {fmt(selected.end_time, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Duration</span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {getDuration(selected.start_time, selected.end_time)}
                  </span>
                </div>
              </div>

              {selected.organizer &&
                selected.organizer !== "unknown@example.com" && (
                  <div className="p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
                    <div className="text-[var(--text-muted)] mb-1">
                      Organizer
                    </div>
                    <div className="font-semibold text-[var(--text-primary)] break-all">
                      {selected.organizer}
                    </div>
                  </div>
                )}

              <div className="p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
                <div className="text-[var(--text-muted)] mb-1">Source</div>
                <div className="flex items-center gap-1.5 font-semibold text-[var(--text-primary)]">
                  <svg
                    className="w-3.5 h-3.5 shrink-0"
                    viewBox="0 0 21 21"
                    fill="none"
                  >
                    <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                    <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                    <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                    <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
                  </svg>
                  Microsoft Outlook
                </div>
              </div>

              {/* Conflict indicator */}
              {isSameDay(new Date(selected.start_time), today) && (
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-500 text-[10px] font-semibold">
                  ⚠️ This event is today
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Create event modal ───────────────────────────────────────────── */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                New Calendar Event
              </h3>
              <button
                onClick={() => setShowCreate(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer text-lg"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                  Title *
                </label>
                <input
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  required
                  placeholder="Meeting title…"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border)] text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                    Start *
                  </label>
                  <input
                    type="datetime-local"
                    value={newStart}
                    onChange={(e) => setNewStart(e.target.value)}
                    required
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border)] text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                    End
                  </label>
                  <input
                    type="datetime-local"
                    value={newEnd}
                    onChange={(e) => setNewEnd(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border)] text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                  Description
                </label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  rows={2}
                  placeholder="Optional notes…"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border)] text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent-primary)] resize-none"
                />
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="flex-1 py-2 text-sm font-semibold rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newTitle || !newStart}
                  className="flex-1 py-2 text-sm font-bold rounded-lg bg-[var(--accent-primary)] text-white hover:opacity-90 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
                >
                  {creating ? (
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : null}
                  {creating ? "Creating…" : "Create Event"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
