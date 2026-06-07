'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { fetchTasks, createTask } from '../../lib/api';

interface TaskItem {
  id: string;
  title: string;
  status: string;
  due: string;
}

export function TasksView() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTasks((await fetchTasks(50)) as TaskItem[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(load, 0);
    return () => clearTimeout(t);
  }, [load]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await createTask(newTitle.trim());
      setNewTitle('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add task');
    } finally {
      setAdding(false);
    }
  };

  const fmtDue = (due: string) => {
    if (!due) return null;
    try {
      return new Date(due).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return null;
    }
  };

  const isDone = (s: string) => s === 'completed' || s === 'complete';

  return (
    <div className="flex-1 h-full overflow-y-auto bg-[var(--bg-base)] p-6 custom-scrollbar" id="tasks-view">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-bold text-[var(--text-primary)] tracking-tight">Tasks</h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5 font-medium">
              Synced from your provider (Microsoft To Do / Google Tasks).
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all cursor-pointer"
            title="Refresh"
          >
            <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="currentColor" viewBox="0 0 24 24">
              <path d="M17.65 6.35A7.958 7.958 0 0 0 12 4a8 8 0 1 0 8 8h-2a6 6 0 1 1-6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
            </svg>
          </button>
        </div>

        {/* Add task */}
        <form onSubmit={handleAdd} className="flex gap-2 mb-5">
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Add a task…"
            className="flex-1 px-3 py-2.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border)] text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent-primary)] transition-all"
            id="new-task-input"
          />
          <button
            type="submit"
            disabled={adding || !newTitle.trim()}
            className="px-4 py-2.5 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/90 disabled:opacity-50 text-[var(--bg-surface)] font-bold text-sm rounded-xl cursor-pointer transition-all active:scale-95"
          >
            {adding ? 'Adding…' : 'Add'}
          </button>
        </form>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-xs font-semibold">
            {error}
          </div>
        )}

        {loading && tasks.length === 0 ? (
          <div className="flex flex-col items-center py-16">
            <div className="w-8 h-8 rounded-full border-2 border-[var(--accent-primary)] border-t-transparent animate-spin mb-3" />
            <p className="text-xs text-[var(--text-muted)]">Loading tasks…</p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="py-16 text-center text-sm text-[var(--text-muted)]">No tasks yet.</div>
        ) : (
          <div className="space-y-2">
            {tasks.map((t) => (
              <div
                key={t.id}
                className="flex items-center gap-3 p-3.5 bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl"
              >
                <span
                  className={`w-5 h-5 rounded-full border-2 shrink-0 flex items-center justify-center ${
                    isDone(t.status)
                      ? 'bg-emerald-500 border-emerald-500'
                      : 'border-[var(--border)]'
                  }`}
                >
                  {isDone(t.status) && (
                    <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </span>
                <span className={`flex-1 text-sm ${isDone(t.status) ? 'line-through text-[var(--text-muted)]' : 'text-[var(--text-primary)]'}`}>
                  {t.title}
                </span>
                {fmtDue(t.due) && (
                  <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-[var(--bg-elevated)] text-[var(--text-muted)] shrink-0">
                    Due {fmtDue(t.due)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
