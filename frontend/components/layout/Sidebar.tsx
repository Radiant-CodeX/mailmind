"use client";

import React from "react";
import type { AccountInfo } from "../../lib/api";
import {
  fetchAccounts,
  setDefaultAccount,
  logoutSession,
  logoutUser,
} from "../../lib/api";
import { SignOutModal } from "../shared/SignOutModal";

/** Small sub-component for the connected mailboxes list. */
function MailboxesSection({
  currentAccountId,
  onAccountChange,
}: {
  currentAccountId: string | null;
  onAccountChange?: (id: string) => void;
}) {
  const [accounts, setAccounts] = React.useState<AccountInfo[]>([]);

  React.useEffect(() => {
    fetchAccounts()
      .then(setAccounts)
      .catch(() => {
        /* silent — list stays empty */
      });
  }, []);

  const handleSelect = async (account: AccountInfo) => {
    if (account.id === currentAccountId) return;
    try {
      await setDefaultAccount(account.id);
    } catch {
      /* ignore — UI still switches */
    }
    onAccountChange?.(account.id);
  };

  if (accounts.length === 0) return null;

  return (
    <div className="mt-1">
      <div className="h-[1px] bg-[var(--border-subtle)] my-2.5 mx-1.5 opacity-60" />
      <p className="px-3 mb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
        Mailboxes
      </p>
      {accounts.map((account) => {
        const isActive = account.id === currentAccountId;
        const label = account.nickname || account.email.split("@")[0];
        const initials = label.slice(0, 2).toUpperCase();
        return (
          <button
            key={account.id}
            onClick={() => handleSelect(account)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-all duration-200 cursor-pointer ${
              isActive
                ? "bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] font-bold"
                : "text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
            }`}
            title={account.email}
          >
            <span
              className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 text-white"
              style={{ background: account.color || "var(--accent-primary)" }}
            >
              {initials}
            </span>
            <span className="truncate flex-1 text-left">{label}</span>
            <span className="text-[9px] uppercase tracking-wider opacity-60">
              {account.provider === "google" ? "G" : "MS"}
            </span>
          </button>
        );
      })}
    </div>
  );
}

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  authenticated: boolean;
  userEmail: string | null;
  /** v3: the currently active account's metadata */
  userProfile?: AccountInfo | null;
  /** User's display name (from User table, not account-specific) */
  userName?: string | null;
  provider?: "google" | "microsoft";
  onLoginClick: () => void;
  onLogoutClick: () => void;
  onComposeClick?: () => void;
  /** v3: callback when the user selects a different mailbox in the sidebar */
  onAccountChange?: (accountId: string) => void;
}

export function Sidebar({
  activeTab,
  onTabChange,
  isCollapsed,
  onToggleCollapse,
  authenticated,
  userEmail,
  userProfile,
  userName,
  provider = "microsoft",
  onLoginClick,
  onLogoutClick,
  onComposeClick,
  onAccountChange,
}: SidebarProps) {
  const profileEmail = userProfile?.email || userEmail;

  // Display name: prefer user's actual name, then account nickname, then email-derived name
  const accountLabel = React.useMemo(() => {
    if (userName?.trim()) return userName;
    const profileName = userProfile?.nickname?.trim();
    if (profileName) return profileName;
    if (!profileEmail)
      return provider === "google" ? "Google Account" : "Microsoft Account";
    const local = profileEmail.split("@")[0];
    const name = local
      .split(/[._-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
    return name || profileEmail;
  }, [userName, profileEmail, provider, userProfile?.nickname]);

  const accountInitials = React.useMemo(() => {
    const source = accountLabel || profileEmail || "User";
    const parts = source
      .replace(/@.*$/, "")
      .split(/\s+|[._-]+/)
      .filter(Boolean);
    const initials = parts
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join("");
    return initials || "US";
  }, [accountLabel, profileEmail]);

  // Sign-out modal state
  const [showSignOutModal, setShowSignOutModal] = React.useState(false);
  const [signOutLoading, setSignOutLoading] = React.useState(false);

  const handleSignOutSession = () => {
    setSignOutLoading(true);
    // Fire API in background — redirect immediately so UI doesn't hang
    logoutSession().catch(() => {});
    // signedOut=session tells the login page to skip auto-redirect and show Quick Login card
    window.location.href = "/?signedOut=session";
  };

  const handleSignOutEverywhere = () => {
    setSignOutLoading(true);
    // Fire API in background — redirect immediately
    logoutUser().catch(() => {});
    // signedOut=full tells the login page to clear remembered login
    window.location.href = "/?signedOut=full";
  };

  // Use profile picture from OAuth provider if available
  const avatar: string | null = userProfile?.photo_url || null;
  const [isMoreExpanded, setIsMoreExpanded] = React.useState(false);

  const primaryItems = [
    {
      name: "Inbox",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0a2 2 0 01-2 2H6a2 2 0 01-2-2m16 0V9a2 2 0 00-2-2H6a2 2 0 00-2 2v4m16 0a2 2 0 01-2 2H6a2 2 0 01-2-2"
          />
        </svg>
      ),
    },
    {
      name: "Sent",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
          />
        </svg>
      ),
    },
  ];

  const expandableItems = [
    {
      name: "Starred",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.907c.961 0 1.36 1.245.588 1.81l-3.97 2.883a1 1 0 00-.364 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.971-2.883a1 1 0 00-1.18 0l-3.97 2.883c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.364-1.118l-3.97-2.883c-.772-.565-.373-1.81.588-1.81h4.906a1 1 0 00.951-.69l1.519-4.674z"
          />
        </svg>
      ),
    },
    {
      name: "Important",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      ),
    },
    {
      name: "Drafts",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
          />
        </svg>
      ),
    },
    {
      name: "Spam",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      ),
    },
    {
      name: "Trash",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
          />
        </svg>
      ),
    },
  ];

  const utilityItems = [
    {
      name: "Calendar",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
      ),
    },
    {
      name: "Tasks",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
          />
        </svg>
      ),
    },
    {
      name: "RAG Settings",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2H5a2 2 0 00-2 2v2m14 0V5a2 2 0 00-2-2H5a2 2 0 00-2 2v6"
          />
        </svg>
      ),
    },
    {
      name: "Evaluation",
      icon: (
        <svg
          className="w-5 h-5 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
      ),
    },
  ];

  return (
    <aside
      className={`bg-[var(--bg-surface)] border-r border-[var(--border)] flex flex-col shrink-0 h-screen transition-all duration-300 ease-in-out ${
        isCollapsed ? "w-16" : "w-64"
      }`}
      id="sidebar"
    >
      <div className="flex flex-col flex-1 min-h-0">
        {/* Brand Header: Clickable logo toggle trigger (No hamburger menu button) */}
        <div
          onClick={onToggleCollapse}
          className="h-16 shrink-0 flex items-center px-4 border-b border-[var(--border-subtle)] overflow-hidden cursor-pointer hover:bg-[var(--bg-elevated)]/20 transition-all"
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          id="brand-header-toggle"
        >
          {!isCollapsed ? (
            <div className="flex items-center gap-3 animate-fade-in text-left">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/mailmind-logo.svg"
                alt="MailMind"
                width={32}
                height={32}
                className="w-8 h-8 rounded-lg shadow"
              />
              <div>
                <span className="font-bold tracking-tight text-[var(--text-primary)] text-base">
                  MailMind
                </span>
                <span className="text-[10px] block text-[var(--text-muted)] font-semibold uppercase tracking-wider -mt-1">
                  Co-pilot Studio
                </span>
              </div>
            </div>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src="/mailmind-logo.svg"
              alt="MailMind"
              width={32}
              height={32}
              className="w-8 h-8 rounded-lg mx-auto shadow animate-fade-in"
            />
          )}
        </div>

        {/* Compose Button */}
        {authenticated && (
          <div className="p-3">
            <button
              onClick={onComposeClick}
              className={`w-full flex items-center justify-center gap-2 bg-[var(--accent-primary)] hover:opacity-90 text-[var(--bg-surface)] font-bold rounded-lg transition-all cursor-pointer shadow-sm hover:shadow active:scale-95 duration-200 ${
                isCollapsed ? "p-2.5" : "px-4 py-3 text-sm"
              }`}
              title="Compose Email"
              id="sidebar-compose-btn"
            >
              <svg
                className="w-5 h-5 shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              {!isCollapsed && <span className="animate-fade-in">Compose</span>}
            </button>
          </div>
        )}

        {/* Navigation items */}
        <nav className="p-3 space-y-1.5 flex-1 min-h-0 overflow-y-auto custom-scrollbar">
          {/* Primary items */}
          {primaryItems.map((item) => {
            const isActive = activeTab === item.name;
            return (
              <button
                key={item.name}
                onClick={() => onTabChange(item.name)}
                className={`w-full flex items-center rounded-lg text-sm transition-all duration-200 cursor-pointer ${
                  isCollapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5"
                } ${
                  isActive
                    ? "bg-[var(--accent-primary)] text-[var(--bg-surface)] font-bold shadow-sm"
                    : "text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                }`}
                title={isCollapsed ? item.name : undefined}
              >
                {item.icon}
                {!isCollapsed && (
                  <span className="animate-fade-in">{item.name}</span>
                )}
              </button>
            );
          })}

          {/* More/Less toggle button */}
          <button
            onClick={() => setIsMoreExpanded((prev) => !prev)}
            className={`w-full flex items-center rounded-lg text-sm transition-all duration-200 cursor-pointer ${
              isCollapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5"
            } text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]`}
            title={
              isCollapsed
                ? isMoreExpanded
                  ? "Show Less"
                  : "Show More"
                : undefined
            }
          >
            {isMoreExpanded ? (
              <svg
                className="w-5 h-5 shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M5 15l7-7 7 7"
                />
              </svg>
            ) : (
              <svg
                className="w-5 h-5 shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            )}
            {!isCollapsed && (
              <span className="animate-fade-in flex-1 text-left">
                {isMoreExpanded ? "Less" : "More"}
              </span>
            )}
          </button>

          {/* Expandable items */}
          {isMoreExpanded &&
            expandableItems.map((item) => {
              const isActive = activeTab === item.name;
              return (
                <button
                  key={item.name}
                  onClick={() => onTabChange(item.name)}
                  className={`w-full flex items-center rounded-lg text-sm transition-all duration-200 cursor-pointer ${
                    isCollapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5"
                  } ${
                    isActive
                      ? "bg-[var(--accent-primary)] text-[var(--bg-surface)] font-bold shadow-sm"
                      : "text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  }`}
                  title={isCollapsed ? item.name : undefined}
                >
                  {item.icon}
                  {!isCollapsed && (
                    <span className="animate-fade-in">{item.name}</span>
                  )}
                </button>
              );
            })}

          {/* Divider */}
          <div className="h-[1px] bg-[var(--border-subtle)] my-2.5 mx-1.5 opacity-60" />

          {/* Utility items */}
          {utilityItems.map((item) => {
            const isActive = activeTab === item.name;
            return (
              <button
                key={item.name}
                onClick={() => onTabChange(item.name)}
                className={`w-full flex items-center rounded-lg text-sm transition-all duration-200 cursor-pointer ${
                  isCollapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5"
                } ${
                  isActive
                    ? "bg-[var(--accent-primary)] text-[var(--bg-surface)] font-bold shadow-sm"
                    : "text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                }`}
                title={isCollapsed ? item.name : undefined}
              >
                {item.icon}
                {!isCollapsed && (
                  <span className="animate-fade-in">{item.name}</span>
                )}
              </button>
            );
          })}

          {/* ── Mailboxes section (v3) ── */}
          {authenticated && !isCollapsed && (
            <MailboxesSection
              currentAccountId={userProfile?.id ?? null}
              onAccountChange={onAccountChange}
            />
          )}
        </nav>
      </div>

      {/* User Footer Profile */}
      <div className="p-3 shrink-0 border-t border-[var(--border-subtle)] flex flex-col justify-center bg-[var(--border-subtle)]/30 min-h-[68px] overflow-hidden text-left">
        {isCollapsed ? (
          authenticated ? (
            <button
              onClick={() => setShowSignOutModal(true)}
              className="w-9 h-9 rounded-full bg-[var(--bg-elevated)] border border-red-500/20 hover:border-red-500 text-red-500 hover:bg-red-500/5 flex items-center justify-center font-bold text-xs mx-auto shadow-inner cursor-pointer transition-all duration-200 animate-fade-in"
              title={`Logged in as ${accountLabel || profileEmail || "User"}. Click to Sign Out.`}
              id="sidebar-user-collapsed-signout"
            >
              {avatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={avatar}
                  alt={accountLabel}
                  className="h-full w-full rounded-full object-cover"
                />
              ) : (
                accountInitials
              )}
            </button>
          ) : (
            <button
              onClick={onLoginClick}
              className="w-9 h-9 rounded-full bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/80 text-[var(--bg-surface)] flex items-center justify-center mx-auto shadow-sm cursor-pointer transition-all duration-200 animate-fade-in"
              title="Sign In with Microsoft"
              id="sidebar-user-collapsed-signin"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"
                />
              </svg>
            </button>
          )
        ) : authenticated ? (
          <div className="flex items-center justify-between gap-2 animate-fade-in w-full">
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="w-9 h-9 rounded-full bg-[var(--bg-elevated)] border border-[var(--accent-primary)]/30 flex items-center justify-center font-bold text-xs text-[var(--accent-primary)] shadow-inner shrink-0">
                {avatar ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={avatar}
                    alt={accountLabel}
                    className="h-full w-full rounded-full object-cover"
                  />
                ) : (
                  accountInitials
                )}
              </div>
              <div className="overflow-hidden">
                <h4 className="text-xs font-semibold text-[var(--text-primary)] truncate">
                  {accountLabel}
                </h4>
                <p
                  className="text-[10px] text-[var(--text-muted)] truncate"
                  title={profileEmail || ""}
                >
                  {profileEmail}
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowSignOutModal(true)}
              className="text-[10px] font-bold text-red-500 hover:text-red-400 bg-transparent border-0 cursor-pointer shrink-0 transition-colors"
              id="sidebar-signout-btn"
            >
              Sign Out
            </button>
          </div>
        ) : (
          <button
            onClick={onLoginClick}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/95 text-[var(--bg-surface)] font-bold text-xs transition-all cursor-pointer shadow-sm hover:shadow active:scale-95 animate-fade-in"
            id="sidebar-signin-btn"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"
              />
            </svg>
            Sign In with Microsoft
          </button>
        )}
      </div>

      <SignOutModal
        isOpen={showSignOutModal}
        onClose={() => !signOutLoading && setShowSignOutModal(false)}
        onSignOutSession={handleSignOutSession}
        onSignOutEverywhere={handleSignOutEverywhere}
        loading={signOutLoading}
      />
    </aside>
  );
}
