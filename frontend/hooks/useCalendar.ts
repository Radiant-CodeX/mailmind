'use client';

import { useState, useEffect, useCallback } from 'react';
import { CalendarEvent } from '../lib/types';
import { fetchCalendar } from '../lib/api';

export function useCalendar(enabled = true) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCalendar = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchCalendar(7); // Fetch 7 days of calendar events
      setEvents(res || []);
    } catch (err: unknown) {
      console.error(err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to load calendar events';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const timer = setTimeout(() => {
      loadCalendar();
    }, 0);
    return () => clearTimeout(timer);
  }, [enabled, loadCalendar]);

  const checkConflict = useCallback((deadlineStr: string | null): CalendarEvent | null => {
    if (!deadlineStr || events.length === 0) return null;
    try {
      const deadlineTime = new Date(deadlineStr).getTime();
      
      for (const event of events) {
        const start = new Date(event.start_time).getTime();
        const end = new Date(event.end_time).getTime();
        
        // Check if deadline is exactly during the event
        if (deadlineTime >= start && deadlineTime <= end) {
          return event;
        }
        
        // Also check if they occur on the exact same date (day, month, year) and the event spans the day
        const dDate = new Date(deadlineStr).toDateString();
        const sDate = new Date(event.start_time).toDateString();
        if (dDate === sDate) {
          return event;
        }
      }
    } catch {
      // Ignored
    }
    return null;
  }, [events]);

  return {
    events,
    loading,
    error,
    checkConflict,
    loadCalendar,
  };
}
