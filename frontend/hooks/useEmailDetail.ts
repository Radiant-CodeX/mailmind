'use client';

import { useState, useEffect } from 'react';
import { Email, ClassificationResult, TriageResult, PrecedentItem } from '../lib/types';
import { classifyEmail, triageEmail, retrievePrecedents, generateEmailDraft, sendEmailReply } from '../lib/api';

// Memory cache for email classifications and precedents to avoid duplicate API calls
const detailCache: Record<string, { classification: ClassificationResult; precedents: PrecedentItem[] }> = {};

export function useEmailDetail(email: Email | null) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [classification, setClassification] = useState<ClassificationResult | null>(null);
  const [triageResult, setTriageResult] = useState<TriageResult | null>(null);
  const [precedents, setPrecedents] = useState<PrecedentItem[]>([]);

  // Draft states
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [isSendingDraft, setIsSendingDraft] = useState(false);
  const [activeStyle, setActiveStyle] = useState<'standard' | 'formal' | 'indepth'>('standard');
  const [aiDrafts, setAiDrafts] = useState<Record<'standard' | 'formal' | 'indepth', string | null>>({
    standard: null,
    formal: null,
    indepth: null,
  });
  const [isDraftApproved, setIsDraftApproved] = useState(false);

  useEffect(() => {
    if (!email) {
      setClassification(null);
      setTriageResult(null);
      setPrecedents([]);
      setAiDrafts({ standard: null, formal: null, indepth: null });
      setActiveStyle('standard');
      setIsDraftApproved(false);
      setError(null);
      return;
    }

    async function loadDetail(currEmail: Email) {
      setLoading(true);
      setError(null);
      setClassification(null);
      setTriageResult(null);
      setPrecedents([]);
      setAiDrafts({ standard: null, formal: null, indepth: null });
      setActiveStyle('standard');
      setIsDraftApproved(false);

      try {
        // 1. Check local session memory cache first
        if (detailCache[currEmail.id]) {
          setClassification(detailCache[currEmail.id].classification);
          setPrecedents(detailCache[currEmail.id].precedents);
          setTriageResult(currEmail.triage || null);
          setLoading(false);
          return;
        }

        // 2. Fetch missing items (reusing triage if available in list item)
        const promises: Promise<any>[] = [
          classifyEmail(currEmail.body),
          retrievePrecedents(currEmail.body),
        ];

        const needsTriageFetch = !currEmail.triage;
        if (needsTriageFetch) {
          promises.push(
            triageEmail({
              email_id: currEmail.id,
              sender: currEmail.sender,
              subject: currEmail.subject,
              body: currEmail.body,
              received_at: currEmail.received_at,
            })
          );
        }

        const [classRes, precRes, fetchedTriageRes] = await Promise.all(promises);
        const triageRes = needsTriageFetch ? fetchedTriageRes : currEmail.triage;

        // Save to cache
        detailCache[currEmail.id] = {
          classification: classRes,
          precedents: precRes,
        };

        setClassification(classRes);
        setPrecedents(precRes);
        setTriageResult(triageRes || null);
      } catch (err: any) {
        console.error(err);
        setError(err.message || 'Failed to load email triage analysis');
      } finally {
        setLoading(false);
      }
    }

    loadDetail(email);
  }, [email]);

  const generateDraft = async (styleToGen?: 'standard' | 'formal' | 'indepth') => {
    if (!email) return;
    const style = styleToGen || activeStyle;

    // If we already have the draft for this style, just switch the active tab
    if (aiDrafts[style]) {
      setActiveStyle(style);
      return;
    }

    setIsGeneratingDraft(true);
    setError(null);
    setIsDraftApproved(false);
    try {
      const draftRes = await generateEmailDraft(email.body, style, email.sender, email.subject);
      setAiDrafts(prev => ({
        ...prev,
        [style]: draftRes.draft
      }));
      setActiveStyle(style);
    } catch (err: any) {
      console.error(err);
      setError(err.message || `Failed to generate ${style} response draft`);
    } finally {
      setIsGeneratingDraft(false);
    }
  };

  const setAiDraft = (text: string) => {
    setAiDrafts(prev => ({
      ...prev,
      [activeStyle]: text
    }));
  };

  const sendDraft = async (comment: string) => {
    if (!email) return;
    setIsSendingDraft(true);
    setError(null);
    setIsDraftApproved(false);
    try {
      await sendEmailReply(email.id, comment);
      setIsDraftApproved(true);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to send email reply');
    } finally {
      setIsSendingDraft(false);
    }
  };

  return {
    loading,
    error,
    classification,
    triageResult,
    precedents,
    aiDraft: aiDrafts[activeStyle],
    setAiDraft,
    isGeneratingDraft,
    generateDraft,
    isDraftApproved,
    setIsDraftApproved,
    activeStyle,
    setActiveStyle,
    aiDrafts,
    isSendingDraft,
    sendDraft,
  };
}
