import { describe, it, expect, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TrashToast } from './TrashToast';
import { Email } from '../../lib/types';

const email: Email = {
  id: 'e1',
  sender: 'sarah@corp.com',
  subject: 'Quarterly report',
  body: 'body',
  received_at: '2026-06-06T10:00:00Z',
};

describe('TrashToast', () => {
  it('renders the email subject and a Moved to Trash label', () => {
    render(<TrashToast email={email} startedAt={Date.now()} onUndo={() => {}} onDismiss={() => {}} />);
    expect(screen.getByText('Quarterly report')).toBeInTheDocument();
    expect(screen.getByText('Moved to Trash')).toBeInTheDocument();
  });

  it('calls onUndo when the Undo button is clicked', async () => {
    const onUndo = vi.fn();
    render(<TrashToast email={email} startedAt={Date.now()} onUndo={onUndo} onDismiss={() => {}} />);
    await userEvent.click(screen.getByText('Undo'));
    expect(onUndo).toHaveBeenCalledOnce();
  });

  it('auto-dismisses once the countdown elapses', () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    // startedAt in the past so the first tick is already past the duration.
    render(<TrashToast email={email} startedAt={Date.now() - 6000} onUndo={() => {}} onDismiss={onDismiss} />);
    act(() => { vi.advanceTimersByTime(100); });
    expect(onDismiss).toHaveBeenCalled();
    vi.useRealTimers();
  });
});
