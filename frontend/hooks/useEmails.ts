'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import { Email } from '../lib/types';
import { fetchEmails, triageEmail, fetchSentEmails } from '../lib/api';
import { MOCK_FOLDER_EMAILS } from '../lib/mockData';

interface RawEmail {
  id?: string;
  email_id?: string;
  sender: string;
  subject: string;
  body: string;
  received_at: string;
  composite_score?: number;
  triage?: Email['triage'];
}

export function useEmails(activeFolder: string = 'Inbox') {
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Load initial state from localStorage if available
  useEffect(() => {
    const cached = localStorage.getItem(`mailmind_emails_${activeFolder}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        const timer = setTimeout(() => {
          setEmails(parsed);
        }, 0);
        return () => clearTimeout(timer);
      } catch (e) {
        console.warn('Failed to parse cached emails', e);
      }
    }
  }, [activeFolder]);

  const loadEmails = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let fetched: RawEmail[] = [];
      if (activeFolder === 'Inbox' || activeFolder === 'Starred' || activeFolder === 'Important') {
        fetched = await fetchEmails(10) as RawEmail[];
      } else if (activeFolder === 'Sent') {
        fetched = await fetchSentEmails(10) as RawEmail[];
      } else {
        fetched = MOCK_FOLDER_EMAILS[activeFolder] || [];
      }

      // Check if we have cached scores in localStorage to populate immediately
      const cachedEmailsStr = localStorage.getItem(`mailmind_emails_${activeFolder}`);
      const cachedMap = new Map<string, Email>();
      if (cachedEmailsStr) {
        try {
          const cachedList = JSON.parse(cachedEmailsStr) as Email[];
          cachedList.forEach((e) => cachedMap.set(e.id, e));
        } catch {}
      }

      const mapped: Email[] = fetched.map((e: RawEmail) => {
        const id = e.email_id || e.id || '';
        const cached = cachedMap.get(id);
        return {
          id,
          sender: e.sender,
          subject: e.subject,
          body: e.body,
          received_at: e.received_at,
          composite_score: e.composite_score || cached?.composite_score || 0,
          triage: e.triage || cached?.triage,
        };
      });
      
      setEmails(mapped);
      localStorage.setItem(`mailmind_emails_${activeFolder}`, JSON.stringify(mapped));
      
      if (mapped.length > 0) {
        setSelectedEmailId((prev) => {
          if (prev && mapped.some((e) => e.id === prev)) {
            return prev;
          }
          return null;
        });
      } else {
        setSelectedEmailId(null);
      }

      // Sync triage scores in background for Inbox/Starred/Important if not present
      if (activeFolder === 'Inbox' || activeFolder === 'Starred' || activeFolder === 'Important') {
        mapped.forEach(async (email) => {
          if (email.triage) return; // Skip if already present in state/cache
          try {
            const res = await triageEmail({
              email_id: email.id,
              sender: email.sender,
              subject: email.subject,
              body: email.body,
              received_at: email.received_at,
            });
            setEmails((prev) => {
              const updated = prev.map((e) =>
                e.id === email.id
                  ? { ...e, composite_score: Math.round(res.composite_score), triage: res }
                  : e
              );
              localStorage.setItem(`mailmind_emails_${activeFolder}`, JSON.stringify(updated));
              return updated;
            });
          } catch (e) {
            console.warn(`Failed to triage email ${email.id}`, e);
          }
        });
      }
    } catch (err: unknown) {
      console.error('Failed to sync emails from backend', err);
      const errMsg = err instanceof Error ? err.message : 'Failed to sync emails';
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  }, [activeFolder]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadEmails();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadEmails]);

  const [starredIds, setStarredIds] = useState<Set<string>>(new Set());

  const toggleStar = useCallback((emailId: string) => {
    setStarredIds((prev) => {
      const next = new Set(prev);
      if (next.has(emailId)) {
        next.delete(emailId);
      } else {
        next.add(emailId);
      }
      return next;
    });
  }, []);

  const filteredAndSortedEmails = useMemo(() => {
    let list = emails.map((e) => ({ ...e, isStarred: starredIds.has(e.id) }));

    if (activeFolder === 'Starred') {
      list = list.filter((e) => e.isStarred);
    } else if (activeFolder === 'Important') {
      list = list.filter((e) => (e.composite_score || 0) >= 50);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (e) =>
          e.sender.toLowerCase().includes(q) ||
          e.subject.toLowerCase().includes(q) ||
          e.body.toLowerCase().includes(q)
      );
    }
    // Sort by composite_score desc
    return list.sort((a, b) => (b.composite_score || 0) - (a.composite_score || 0));
  }, [emails, searchQuery, activeFolder, starredIds]);

  const selectedEmail = useMemo(() => {
    const list = emails.map((e) => ({ ...e, isStarred: starredIds.has(e.id) }));
    return list.find((e) => e.id === selectedEmailId) || null;
  }, [emails, selectedEmailId, starredIds]);

  return {
    emails: filteredAndSortedEmails,
    totalCount: emails.length,
    selectedEmail,
    selectedEmailId,
    setSelectedEmailId,
    searchQuery,
    setSearchQuery,
    loading,
    error,
    refresh: loadEmails,
    toggleStar,
  };
}
