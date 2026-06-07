import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// Raw emails as the backend would return them (email_id keys, with triage so
// the hook doesn't kick off background scoring). Defined via vi.hoisted so it's
// available inside the hoisted vi.mock factory below.
const { rawEmails } = vi.hoisted(() => ({
  rawEmails: [
    { email_id: 'a', sender: 's1@x.com', subject: 'A', body: 'a', received_at: '2026-06-06T10:00:00Z', composite_score: 80, triage: { priority: 'HIGH' } },
    { email_id: 'b', sender: 's2@x.com', subject: 'B', body: 'b', received_at: '2026-06-06T09:00:00Z', composite_score: 40, triage: { priority: 'LOW' } },
  ],
}));

// Mock the API module so the hook never touches the network.
vi.mock('../lib/api', () => ({
  fetchEmails: vi.fn().mockResolvedValue(rawEmails),
  fetchSentEmails: vi.fn().mockResolvedValue([]),
  fetchDraftEmails: vi.fn().mockResolvedValue([]),
  fetchSpamEmails: vi.fn().mockResolvedValue([]),
  fetchTrashEmails: vi.fn().mockResolvedValue(rawEmails),
  triageEmail: vi.fn().mockResolvedValue({ composite_score: 50 }),
  moveEmailToTrash: vi.fn().mockResolvedValue({ success: true }),
  restoreEmailFromTrash: vi.fn().mockResolvedValue({ success: true }),
}));

import { useEmails } from './useEmails';
import * as api from '../lib/api';

const cachedInbox = [
  { id: 'a', sender: 's1@x.com', subject: 'A', body: 'a', received_at: '2026-06-06T10:00:00Z', composite_score: 80 },
  { id: 'b', sender: 's2@x.com', subject: 'B', body: 'b', received_at: '2026-06-06T09:00:00Z', composite_score: 40 },
];

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('useEmails', () => {
  it('paints cached emails instantly on mount (no blocking spinner)', async () => {
    localStorage.setItem('mailmind_emails_Inbox', JSON.stringify(cachedInbox));
    const { result } = renderHook(() => useEmails('Inbox'));

    // Cached content is available synchronously after the first effect.
    await waitFor(() => expect(result.current.emails).toHaveLength(2));
    expect(result.current.emails.map((e) => e.id)).toContain('a');
  });

  it('trashEmail optimistically removes the email and opens the undo toast', async () => {
    // Rely on the fetch (not cache) so waitFor guarantees the network sync settled.
    const { result } = renderHook(() => useEmails('Inbox'));
    await waitFor(() => expect(result.current.emails).toHaveLength(2));

    act(() => result.current.trashEmail('a'));

    expect(result.current.emails.map((e) => e.id)).not.toContain('a');
    expect(result.current.pendingTrash?.email.id).toBe('a');
    // API call is deferred (undo window) — not fired yet.
    expect(api.moveEmailToTrash).not.toHaveBeenCalled();
  });

  it('undoTrash restores the email and cancels the API call', async () => {
    const { result } = renderHook(() => useEmails('Inbox'));
    await waitFor(() => expect(result.current.emails).toHaveLength(2));

    act(() => result.current.trashEmail('a'));
    expect(result.current.emails.map((e) => e.id)).not.toContain('a');

    act(() => result.current.undoTrash());
    expect(result.current.emails.map((e) => e.id)).toContain('a');
    expect(result.current.pendingTrash).toBeNull();

    // Wait beyond the undo window: API must NOT be called because we undid.
    await new Promise((r) => setTimeout(r, 5200));
    expect(api.moveEmailToTrash).not.toHaveBeenCalled();
  }, 9000);

  it('fires moveEmailToTrash after the undo window expires', async () => {
    const { result } = renderHook(() => useEmails('Inbox'));
    await waitFor(() => expect(result.current.emails).toHaveLength(2));

    act(() => result.current.trashEmail('a'));
    await waitFor(() => expect(api.moveEmailToTrash).toHaveBeenCalledWith('a'), { timeout: 7000 });
  }, 9000);

  it('sorts by date and triage score, and persists the choice', async () => {
    const { result } = renderHook(() => useEmails('Inbox'));
    await waitFor(() => expect(result.current.emails).toHaveLength(2));

    // a = score 80 @ 10:00, b = score 40 @ 09:00.
    act(() => result.current.setSortKey('date_asc'));
    expect(result.current.emails.map((e) => e.id)).toEqual(['b', 'a']);

    act(() => result.current.setSortKey('score_asc'));
    expect(result.current.emails.map((e) => e.id)).toEqual(['b', 'a']);

    act(() => result.current.setSortKey('score_desc'));
    expect(result.current.emails.map((e) => e.id)).toEqual(['a', 'b']);

    // Preference persisted for next session.
    expect(localStorage.getItem('mailmind_sort')).toBe('score_desc');
  });

  it('restoreEmail removes from the Trash list and calls the restore API', async () => {
    const { result } = renderHook(() => useEmails('Trash'));
    await waitFor(() => expect(result.current.emails).toHaveLength(2));

    await act(async () => { await result.current.restoreEmail('a'); });

    expect(result.current.emails.map((e) => e.id)).not.toContain('a');
    expect(api.restoreEmailFromTrash).toHaveBeenCalledWith('a');
  });
});
