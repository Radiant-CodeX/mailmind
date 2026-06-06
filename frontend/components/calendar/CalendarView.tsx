'use client';

import React from 'react';
import { CalendarEvent } from '../../lib/types';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { ErrorBanner } from '../shared/ErrorBanner';

interface CalendarViewProps {
  events: CalendarEvent[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function CalendarView({ events, loading, error, onRefresh }: CalendarViewProps) {

  const formatTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (e) {
      return '';
    }
  };

  const formatDate = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleDateString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      });
    } catch (e) {
      return '';
    }
  };

  return (
    <div className="flex-1 bg-[var(--bg-base)] flex flex-col h-full overflow-hidden text-left p-6" id="calendar-view">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-[var(--text-primary)]">Calendar Integration</h2>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          Synchronized events fetched from Microsoft Graph Outlook calendar service.
        </p>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <LoadingSpinner message="Retrieving upcoming calendar slots..." size="lg" />
        </div>
      ) : error ? (
        <ErrorBanner message={error} />
      ) : (
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
          {/* Main Agenda list */}
          <div className="lg:col-span-2 flex flex-col h-full bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg overflow-hidden shadow-sm">
            <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Upcoming Agenda</h3>
              <span className="px-2 py-0.5 rounded-full bg-[var(--bg-elevated)] border border-[var(--border)] text-[10px] font-bold text-[var(--text-primary)]">
                {events.length} Events
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
              {events.length === 0 ? (
                <div className="py-12 text-center text-xs text-[var(--text-muted)]">
                  No upcoming meetings or events found in your calendar.
                </div>
              ) : (
                events.map((event, idx) => (
                  <div
                    key={idx}
                    className="p-4 bg-[var(--bg-elevated)] border border-[var(--border-subtle)] hover:border-[var(--border)] rounded-lg transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <h4 className="text-xs font-bold text-[var(--text-primary)]">
                        {event.title}
                      </h4>
                      <p className="text-[10px] text-[var(--text-muted)]">
                        Organizer: {event.organizer}
                      </p>
                    </div>

                    <div className="text-right shrink-0 flex flex-row sm:flex-col gap-2 sm:gap-0 items-center sm:items-end justify-between sm:justify-start">
                      <span className="text-xs font-bold text-[var(--accent-primary)] font-mono">
                        {formatDate(event.start_time)}
                      </span>
                      <span className="text-[10px] text-[var(--text-muted)] font-mono">
                        {formatTime(event.start_time)} - {formatTime(event.end_time)}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Side calendar widget */}
          <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg p-5 flex flex-col justify-between shadow-sm">
            <div>
              <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider mb-4">
                Schedule Summary
              </h3>

              {/* Quick status box */}
              <div className="p-4 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)] space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[var(--text-muted)]">Active Sync:</span>
                  <span className="text-xs font-bold text-[var(--accent-success)]">ONLINE</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[var(--text-muted)]">SLA Window:</span>
                  <span className="text-xs font-mono font-semibold text-[var(--text-primary)]">7 Days</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[var(--text-muted)]">Conflicts:</span>
                  <span className="text-xs font-bold text-[var(--accent-warning)]">
                    {events.length > 2 ? 'High Load' : 'Cleared'}
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border-subtle)]">
              <button
                onClick={onRefresh}
                disabled={loading}
                className="w-full py-2 bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)] border border-[var(--border)] text-[var(--text-primary)] rounded text-xs font-bold transition-all cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-[var(--text-muted)] border-t-[var(--text-primary)] rounded-full animate-spin"></span>
                    Syncing...
                  </>
                ) : (
                  'Refresh Calendar Sync'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
