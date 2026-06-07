import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  fetchEmails,
  fetchSentEmails,
  moveEmailToTrash,
  restoreEmailFromTrash,
  fetchEvaluation,
} from './api';

function mockFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('api client', () => {
  it('fetchEmails hits the inbox endpoint and returns json', async () => {
    const data = [{ email_id: '1', sender: 'a@b.com', subject: 's', body: 'b', received_at: '' }];
    global.fetch = mockFetch(data) as unknown as typeof fetch;

    const result = await fetchEmails(5);

    expect(result).toEqual(data);
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/emails?limit=5'));
  });

  it('fetchSentEmails targets the sent folder', async () => {
    global.fetch = mockFetch([]) as unknown as typeof fetch;
    await fetchSentEmails(10);
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/emails/sent'));
  });

  it('moveEmailToTrash POSTs to the trash endpoint', async () => {
    global.fetch = mockFetch({ success: true }) as unknown as typeof fetch;
    const res = await moveEmailToTrash('abc');
    expect(res).toEqual({ success: true });
    const [url, opts] = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/emails/abc/trash');
    expect(opts.method).toBe('POST');
  });

  it('restoreEmailFromTrash POSTs to the restore endpoint', async () => {
    global.fetch = mockFetch({ success: true }) as unknown as typeof fetch;
    await restoreEmailFromTrash('xyz');
    const [url, opts] = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/emails/xyz/restore');
    expect(opts.method).toBe('POST');
  });

  it('fetchEvaluation returns the report', async () => {
    const report = { accuracy: 92, total_samples: 50, correct_predictions: 46, results: [] };
    global.fetch = mockFetch(report) as unknown as typeof fetch;
    expect(await fetchEvaluation()).toEqual(report);
  });

  it('throws a clear error when the response is not ok', async () => {
    global.fetch = mockFetch(null, false, 500) as unknown as typeof fetch;
    await expect(fetchEmails()).rejects.toThrow('Emails fetch failed');
  });
});
