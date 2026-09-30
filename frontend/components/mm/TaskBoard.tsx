"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CalendarClock, Check, Plus, RefreshCw } from "lucide-react";
import { completeTask, createTask, fetchTasks } from "../../lib/api";
import { userStorage } from "../../lib/userStorage";
import { deadlineLabel } from "./format";
import { Button, IconButton } from "./ui";

interface Task {
  id: string;
  title: string;
  status: string;
  due: string;
}

type Stage = "todo" | "doing" | "done";

const STAGES: { id: Stage; title: string; empty: string }[] = [
  { id: "todo", title: "Needs action", empty: "Nothing waiting. Tasks you approve from emails land here." },
  { id: "doing", title: "In progress", empty: "Move a task here when you start on it." },
  { id: "done", title: "Done", empty: "Finished tasks collect here." },
];

const DOING_KEY = "mm_tasks_in_progress";

function readDoing(): Set<string> {
  try {
    return new Set(JSON.parse(userStorage.getItem(DOING_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function writeDoing(ids: Set<string>) {
  try {
    userStorage.setItem(DOING_KEY, JSON.stringify([...ids]));
  } catch {}
}

export function TaskBoard() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [doing, setDoing] = useState<Set<string>>(() => (typeof window === "undefined" ? new Set() : readDoing()));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTasks((await fetchTasks(100)) as Task[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load your tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch from Google Tasks; state is set asynchronously in load().
    const t = setTimeout(load, 0);
    return () => clearTimeout(t);
  }, [load]);

  const stageOf = useCallback(
    (t: Task): Stage => (t.status === "completed" ? "done" : doing.has(t.id) ? "doing" : "todo"),
    [doing],
  );

  const columns = useMemo(() => {
    const by: Record<Stage, Task[]> = { todo: [], doing: [], done: [] };
    for (const t of tasks) by[stageOf(t)].push(t);
    const dueSort = (a: Task, b: Task) =>
      (a.due ? new Date(a.due).getTime() : Infinity) - (b.due ? new Date(b.due).getTime() : Infinity);
    by.todo.sort(dueSort);
    by.doing.sort(dueSort);
    return by;
  }, [tasks, stageOf]);

  const setStage = async (t: Task, to: Stage) => {
    const nextDoing = new Set(doing);
    if (to === "doing") nextDoing.add(t.id);
    else nextDoing.delete(t.id);
    setDoing(nextDoing);
    writeDoing(nextDoing);
    if (to === "done") {
      setTasks((prev) => prev.map((x) => (x.id === t.id ? { ...x, status: "completed" } : x)));
      try {
        await completeTask(t.id);
      } catch {
        setTasks((prev) => prev.map((x) => (x.id === t.id ? { ...x, status: "needsAction" } : x)));
        setError("Could not mark that task done in Google Tasks. Try again.");
      }
    }
  };

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const v = title.trim();
    if (!v) return;
    setAdding(true);
    setError(null);
    try {
      await createTask(v);
      setTitle("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the task");
    } finally {
      setAdding(false);
    }
  };

  const openCount = columns.todo.length + columns.doing.length;

  return (
    <section aria-label="Tasks" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <header className="flex shrink-0 flex-wrap items-end gap-3 border-b border-rule bg-surface px-5 pb-4 pt-5 md:px-8">
        <div className="mr-auto">
          <h1 className="text-[20px] font-semibold tracking-tight text-ink">Tasks</h1>
          <p className="mt-0.5 text-[13px] text-ink-3">
            {loading ? "Loading your Google Tasks" : openCount ? `${openCount} open. Synced with Google Tasks.` : "All clear. Synced with Google Tasks."}
          </p>
        </div>
        <form onSubmit={add} className="flex w-full items-center gap-2 sm:w-auto">
          <label className="sr-only" htmlFor="new-task">New task</label>
          <input
            id="new-task"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Add a task, e.g. Pay semester fee"
            className="h-9 min-w-0 flex-1 rounded-full border border-rule bg-surface px-4 text-[13.5px] text-ink placeholder:text-ink-3 focus:border-cobalt focus:outline-none sm:w-72"
          />
          <Button type="submit" variant="primary" size="md" icon={Plus} loading={adding} disabled={!title.trim()}>
            Add
          </Button>
          <IconButton icon={RefreshCw} label="Refresh" onClick={load} disabled={loading} />
        </form>
      </header>

      {error && (
        <p className="mx-5 mt-4 rounded-xl bg-urgent-soft px-3.5 py-2.5 text-[13px] text-urgent md:mx-8">{error}</p>
      )}

      <div className="mm-scroll grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto p-5 md:grid-cols-3 md:p-8">
        {STAGES.map((stage) => (
          <div key={stage.id} className="flex min-h-0 flex-col rounded-[14px] bg-sunk/60 p-2" aria-label={stage.title}>
            <h2 className="flex items-center justify-between px-2 pb-2 pt-1 text-[13px] font-semibold text-ink">
              {stage.title}
              <span className="text-[12px] font-normal tabular-nums text-ink-3">{columns[stage.id].length}</span>
            </h2>
            {loading ? (
              <div className="space-y-2 p-1">
                <span className="mm-skeleton block h-14" />
                <span className="mm-skeleton block h-14" />
              </div>
            ) : columns[stage.id].length === 0 ? (
              <p className="px-2 pb-3 text-[12.5px] leading-snug text-ink-3">{stage.empty}</p>
            ) : (
              <ul className="grid gap-2">
                {columns[stage.id].map((t) => {
                  const dl = deadlineLabel(t.due || null);
                  return (
                    <li key={t.id} className="mm-settle rounded-xl border border-rule bg-surface px-3.5 py-3 shadow-paper">
                      <p className={`text-[13.5px] leading-snug ${stage.id === "done" ? "text-ink-3 line-through" : "text-ink"}`}>{t.title}</p>
                      <div className="mt-2 flex items-center gap-2">
                        {dl && stage.id !== "done" ? (
                          <span className={`inline-flex items-center gap-1 text-[12px] ${dl.overdue ? "text-urgent" : dl.soon ? "text-soon" : "text-ink-3"}`}>
                            <CalendarClock className="size-3.5" strokeWidth={1.75} aria-hidden />
                            {dl.overdue ? "Overdue, " : ""}{dl.text.split(",").slice(0, 2).join(",")}
                          </span>
                        ) : <span />}
                        <span className="ml-auto flex items-center gap-1">
                          {stage.id === "doing" && (
                            <IconButton icon={ArrowLeft} label="Back to needs action" onClick={() => setStage(t, "todo")} className="size-7" />
                          )}
                          {stage.id === "todo" && (
                            <Button variant="ghost" size="sm" icon={ArrowRight} onClick={() => setStage(t, "doing")} className="h-7 px-2.5">
                              Start
                            </Button>
                          )}
                          {stage.id !== "done" && (
                            <Button variant="quiet" size="sm" icon={Check} onClick={() => setStage(t, "done")} className="h-7 px-2.5">
                              Done
                            </Button>
                          )}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
