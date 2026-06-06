'use client';

import { useState, useEffect } from 'react';
import { CommitmentItem } from '../lib/types';
import { extractCommitments, confirmCommitments } from '../lib/api';

export function useCommitments(emailId: string | null, emailBody: string | null) {
  const [commitments, setCommitments] = useState<CommitmentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [taskUrls, setTaskUrls] = useState<string[]>([]);
  const [eventUrls, setEventUrls] = useState<string[]>([]);

  useEffect(() => {
    if (!emailId || !emailBody) {
      setCommitments([]);
      setError(null);
      setConfirmed(false);
      setTaskUrls([]);
      setEventUrls([]);
      return;
    }

    async function loadCommitments() {
      setLoading(true);
      setError(null);
      setConfirmed(false);
      setTaskUrls([]);
      setEventUrls([]);
      setCommitments([]);

      try {
        const res = await extractCommitments(emailBody!, '', emailId!);
        // Check newly extracted commitments by default to enable one-click synchronization
        const items = (res.commitments || []).map((c: any) => ({
          ...c,
          approved: true,
        }));
        setCommitments(items);

        // Pre-populate URLs if any tasks were already confirmed
        const confirmedTasks = items.filter((c: any) => c.confirmed && c.task_url).map((c: any) => c.task_url);
        const confirmedEvents = items.filter((c: any) => c.confirmed && c.event_url).map((c: any) => c.event_url);
        if (confirmedTasks.length > 0 || confirmedEvents.length > 0) {
          setConfirmed(true);
          setTaskUrls(confirmedTasks);
          setEventUrls(confirmedEvents);
        }
      } catch (err: any) {
        console.error(err);
        setError(err.message || 'Failed to extract commitments');
      } finally {
        setLoading(false);
      }
    }

    loadCommitments();
  }, [emailId, emailBody]);

  const toggleCommitment = (id: string) => {
    setCommitments((prev) =>
      prev.map((c) => (c.id === id && !c.confirmed ? { ...c, approved: !c.approved } : c))
    );
  };

  const confirmSelected = async () => {
    if (!emailId) return;
    const selected = commitments.filter((c) => c.approved && !c.confirmed);
    if (selected.length === 0) return;

    setConfirming(true);
    setError(null);
    try {
      const res = await confirmCommitments(emailId, selected);
      if (res.success) {
        setConfirmed(true);
        setTaskUrls(res.task_urls || []);
        setEventUrls(res.event_urls || []);

        // Update local state to mark checked items as confirmed
        const approvedList = commitments.filter(x => x.approved && !x.confirmed);
        setCommitments((prev) =>
          prev.map((c) => {
            if (c.approved && !c.confirmed) {
              const idx = approvedList.indexOf(c);
              return {
                ...c,
                confirmed: true,
                task_url: res.task_urls?.[idx],
                event_url: res.event_urls?.[idx],
              };
            }
            return c;
          })
        );
      } else {
        throw new Error('Server returned unsuccessful commitment confirmation');
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to confirm commitments');
    } finally {
      setConfirming(false);
    }
  };

  return {
    commitments,
    loading,
    error,
    confirming,
    confirmed,
    taskUrls,
    eventUrls,
    toggleCommitment,
    confirmSelected,
  };
}
