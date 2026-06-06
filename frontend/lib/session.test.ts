import { describe, it, expect, beforeEach } from 'vitest';
import {
  getRememberedLogin,
  rememberLogin,
  clearRememberedLogin,
  initialsFor,
} from './session';

beforeEach(() => localStorage.clear());

describe('session (quick login)', () => {
  it('returns null when nothing is remembered', () => {
    expect(getRememberedLogin()).toBeNull();
  });

  it('remembers and reads back a login', () => {
    rememberLogin('live', 'jane.doe@corp.com');
    const r = getRememberedLogin();
    expect(r?.mode).toBe('live');
    expect(r?.email).toBe('jane.doe@corp.com');
    expect(typeof r?.ts).toBe('number');
  });

  it('falls back to a placeholder email when none provided', () => {
    rememberLogin('mock', null);
    expect(getRememberedLogin()?.email).toBe('Signed-in user');
  });

  it('clears the remembered login', () => {
    rememberLogin('mock', 'm@x.com');
    clearRememberedLogin();
    expect(getRememberedLogin()).toBeNull();
  });

  it('ignores corrupted storage gracefully', () => {
    localStorage.setItem('mailmind_last_login', '{not json');
    expect(getRememberedLogin()).toBeNull();
  });

  it('expires a remembered login older than one week', () => {
    const eightDaysAgo = Date.now() - 8 * 24 * 60 * 60 * 1000;
    localStorage.setItem(
      'mailmind_last_login',
      JSON.stringify({ mode: 'live', email: 'old@x.com', ts: eightDaysAgo })
    );
    expect(getRememberedLogin()).toBeNull();
    // Expired entry is purged from storage.
    expect(localStorage.getItem('mailmind_last_login')).toBeNull();
  });

  it('keeps a login that is within the one-week window', () => {
    const twoDaysAgo = Date.now() - 2 * 24 * 60 * 60 * 1000;
    localStorage.setItem(
      'mailmind_last_login',
      JSON.stringify({ mode: 'mock', email: 'recent@x.com', ts: twoDaysAgo })
    );
    expect(getRememberedLogin()?.email).toBe('recent@x.com');
  });

  it('derives avatar initials from the email', () => {
    expect(initialsFor('mock.user@example.com')).toBe('MO');
    expect(initialsFor('a@b.com')).toBe('A');
  });
});
