'use client';

import { useState, useEffect } from 'react';
import { CommitmentItem } from '../lib/types';
import { extractCommitments, confirmCommitments } from '../lib/api';

export function useCommitments(
  emailId: string | null,
  emailBody: string | null,
  initialCommitments?: CommitmentItem[],
  // "loading" while the email's enrichment runs (it extracts tasks too),
  // "done" to use its result, "failed" to extract here as a fallback.
  enrichStatus: "loading" | "done" | "failed" = "failed",
) {
  const [commitments, setCommitments] = useState<CommitmentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [taskUrls, setTaskUrls] = useState<string[]>([]);
  const [eventUrls, setEventUrls] = useState<string[]>([]);

  useEffect(() => {
    if (!emailId || !emailBody) {
      const resetTimer = setTimeout(() => {
        setCommitments([]);
        setError(null);
        setConfirmed(false);
        setTaskUrls([]);
        setEventUrls([]);
      }, 0);
      return () => clearTimeout(resetTimer);
    }

    // Enrichment extracts tasks already: wait for it rather than paying for a
    // second AI call, and take its answer even when it found nothing.
    if (enrichStatus === "loading") {
      const t = setTimeout(() => { setCommitments([]); setError(null); setLoading(true); }, 0);
      return () => clearTimeout(t);
    }
    if (enrichStatus === "done") {
      const seeded = (initialCommitments ?? []).map((c) => ({ ...c, approved: c.approved ?? true }));
      const t = setTimeout(() => { setCommitments(seeded); setError(null); setLoading(false); }, 0);
      return () => clearTimeout(t);
    }

    // Fallback (enrichment failed): extract here.
    if (initialCommitments && initialCommitments.length > 0) {
      const seeded = initialCommitments.map((c) => ({ ...c, approved: c.approved ?? true }));
      const t = setTimeout(() => { setCommitments(seeded); setLoading(false); }, 0);
      return () => clearTimeout(t);
    }

    let cancelled = false;
    async function loadCommitments() {
      setLoading(true);
      setError(null);
      setConfirmed(false);
      setTaskUrls([]);
      setEventUrls([]);
      setCommitments([]);

      try {
        const res = await extractCommitments(emailBody!, '', emailId!);
        if (cancelled) return;
        // Check newly extracted commitments by default to enable one-click synchronization
        const items = (res.commitments || []).map((c: CommitmentItem) => ({
          ...c,
          approved: true,
        }));
        setCommitments(items);

        // Pre-populate URLs if any tasks were already confirmed
        const confirmedTasks = items.filter((c: CommitmentItem) => c.confirmed && c.task_url).map((c: CommitmentItem) => c.task_url as string);
        const confirmedEvents = items.filter((c: CommitmentItem) => c.confirmed && c.event_url).map((c: CommitmentItem) => c.event_url as string);
        if (confirmedTasks.length > 0 || confirmedEvents.length > 0) {
          setConfirmed(true);
          setTaskUrls(confirmedTasks);
          setEventUrls(confirmedEvents);
        }
      } catch (err: unknown) {
        if (cancelled) return;
        console.error(err);
        const errorMessage = err instanceof Error ? err.message : 'Failed to extract commitments';
        setError(errorMessage);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    const loadTimer = setTimeout(() => {
      loadCommitments();
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(loadTimer);
    };
    // initialCommitments must be a dependency: the pipeline result for the newly
    // opened email arrives after the selection changes, and without it the
    // previous email's items stayed on screen.
  }, [emailId, emailBody, initialCommitments, enrichStatus]);

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
    } catch (err: unknown) {
      console.error(err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to confirm commitments';
      setError(errorMessage);
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
