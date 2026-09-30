"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  CalendarDays,
  Check,
  FileText,
  Inbox,
  Layers,
  ListChecks,
  LogOut,
  MessageSquareText,
  Moon,
  Plus,
  Send,
  Settings,
  SquarePen,
  Star,
  Sun,
  Trash2,
  Ban,
  type LucideIcon,
} from "lucide-react";
import { LogoGlyph } from "../shared/LogoGlyph";
import { AccountInfo, fetchAccounts, setDefaultAccount } from "../../lib/api";
import { CATEGORY_LABEL, CATEGORY_ORDER } from "./format";
import { Avatar } from "./ui";

export type View =
  | "needs"
  | "all"
  | "starred"
  | "sent"
  | "drafts"
  | "spam"
  | "trash"
  | "tasks"
  | "calendar"
  | "settings";

interface RailProps {
  view: View;
  onView: (v: View) => void;
  category: string | null;
  onCategory: (c: string | null) => void;
  needsCount: number;
  unreadCount: number;
  categoryCounts: Record<string, number>;
  onCompose: () => void;
  userEmail: string | null;
  userName: string | null;
  account: AccountInfo | null;
  dark: boolean;
  onToggleTheme: () => void;
  onFeedback: () => void;
  onSignOut: () => void;
  /** Mobile drawer: close after navigating. */
  onNavigate?: () => void;
}

function NavItem({
  icon: Icon,
  label,
  active,
  count,
  emphasis,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  active: boolean;
  count?: number;
  emphasis?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`group flex h-8 w-full items-center gap-2.5 rounded-lg px-2.5 text-[13.5px] transition-colors duration-150 cursor-pointer ${
        active ? "bg-surface text-ink font-medium shadow-paper" : "text-ink-2 hover:bg-hover hover:text-ink"
      }`}
    >
      <Icon className={`size-4 shrink-0 ${active ? "text-cobalt" : "text-ink-3 group-hover:text-ink-2"}`} strokeWidth={1.75} aria-hidden />
      <span className="flex-1 truncate text-left">{label}</span>
      {count !== undefined && count > 0 && (
        <span className={`tabular-nums text-[12px] ${emphasis ? "font-semibold text-cobalt" : "text-ink-3"}`}>{count}</span>
      )}
    </button>
  );
}

function GroupLabel({ children }: { children: React.ReactNode }) {
  return <p className="px-2.5 pb-1 pt-4 text-[12px] font-medium text-ink-3">{children}</p>;
}

export function Rail(props: RailProps) {
  const {
    view, onView, category, onCategory, needsCount, unreadCount, categoryCounts,
    onCompose, userEmail, userName, account, dark, onToggleTheme, onFeedback, onSignOut, onNavigate,
  } = props;
  const [menuOpen, setMenuOpen] = useState(false);
  const [accounts, setAccounts] = useState<AccountInfo[]>([]);
  const menuRef = useRef<HTMLDivElement>(null);

  const go = (v: View) => {
    onView(v);
    onCategory(null);
    onNavigate?.();
  };

  useEffect(() => {
    if (!menuOpen) return;
    fetchAccounts().then(setAccounts).catch(() => setAccounts([]));
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const switchTo = async (a: AccountInfo) => {
    if (a.id === account?.id) return setMenuOpen(false);
    await setDefaultAccount(a.id).catch(() => {});
    window.location.reload();
  };

  const displayName = userName || account?.email?.split("@")[0] || "You";
  const cats = CATEGORY_ORDER.filter((c) => (categoryCounts[c] ?? 0) > 0);

  return (
    <nav aria-label="Mail" className="flex h-full w-full flex-col bg-bg px-3 pb-3 pt-4">
      <div className="flex items-center gap-2 px-2.5 pb-4">
        <LogoGlyph className="size-7 text-ink" />
        <span className="text-[15px] font-semibold tracking-tight text-ink">MailMind</span>
      </div>

      <button
        type="button"
        id={onNavigate ? undefined : "sidebar-compose-btn"}
        onClick={() => { onCompose(); onNavigate?.(); }}
        className="mb-3 flex h-9 items-center justify-center gap-2 rounded-full bg-cobalt text-[13.5px] font-medium text-cobalt-ink transition-[filter,transform] duration-200 hover:brightness-110 active:scale-[0.98] cursor-pointer"
      >
        <SquarePen className="size-4" strokeWidth={1.75} aria-hidden />
        Compose
      </button>

      <div className="mm-scroll -mx-1 flex-1 overflow-y-auto px-1">
        <div className="space-y-0.5">
          <NavItem icon={Inbox} label="Needs you" active={view === "needs" && !category} count={needsCount} emphasis onClick={() => go("needs")} />
          <NavItem icon={Layers} label="Everything" active={view === "all" && !category} count={unreadCount} onClick={() => go("all")} />
          <NavItem icon={Star} label="Starred" active={view === "starred"} onClick={() => go("starred")} />
          <NavItem icon={Send} label="Sent" active={view === "sent"} onClick={() => go("sent")} />
          <NavItem icon={FileText} label="Drafts" active={view === "drafts"} onClick={() => go("drafts")} />
        </div>

        <GroupLabel>Plan</GroupLabel>
        <div className="space-y-0.5">
          <NavItem icon={ListChecks} label="Tasks" active={view === "tasks"} onClick={() => go("tasks")} />
          <NavItem icon={CalendarDays} label="Calendar" active={view === "calendar"} onClick={() => go("calendar")} />
        </div>

        {cats.length > 0 && (
          <>
            <GroupLabel>On campus</GroupLabel>
            <div className="space-y-0.5">
              {cats.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => { onView("all"); onCategory(category === c ? null : c); onNavigate?.(); }}
                  aria-pressed={category === c}
                  className={`flex h-8 w-full items-center gap-2.5 rounded-lg px-2.5 text-[13.5px] transition-colors duration-150 cursor-pointer ${
                    category === c ? "bg-surface font-medium text-ink shadow-paper" : "text-ink-2 hover:bg-hover hover:text-ink"
                  }`}
                >
                  <span className="flex-1 truncate pl-[26px] text-left">{CATEGORY_LABEL[c]}</span>
                  <span className="tabular-nums text-[12px] text-ink-3">{categoryCounts[c]}</span>
                </button>
              ))}
            </div>
          </>
        )}

        <GroupLabel>More</GroupLabel>
        <div className="space-y-0.5">
          <NavItem icon={Ban} label="Spam" active={view === "spam"} onClick={() => go("spam")} />
          <NavItem icon={Trash2} label="Trash" active={view === "trash"} onClick={() => go("trash")} />
        </div>
      </div>

      <div className="space-y-0.5 border-t border-rule pt-2">
        <NavItem icon={Settings} label="Settings" active={view === "settings"} onClick={() => go("settings")} />
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="flex w-full items-center gap-2.5 rounded-lg px-1.5 py-1.5 text-left transition-colors hover:bg-hover cursor-pointer"
          >
            {account?.photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={account.photo_url} alt="" referrerPolicy="no-referrer" className="size-7 rounded-full object-cover" />
            ) : (
              <Avatar name={displayName} size={28} />
            )}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium text-ink">{displayName}</span>
              <span className="block truncate text-[11.5px] text-ink-3">{account?.email || userEmail}</span>
            </span>
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="animate-fade-in absolute bottom-full left-0 right-0 z-30 mb-2 overflow-hidden rounded-xl border border-rule bg-surface p-1 shadow-pop"
            >
              {accounts.length > 0 && (
                <>
                  <p className="px-2.5 pb-1 pt-1.5 text-[11.5px] font-medium text-ink-3">Accounts</p>
                  {accounts.map((a) => (
                    <button
                      key={a.id}
                      role="menuitem"
                      type="button"
                      onClick={() => switchTo(a)}
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] text-ink hover:bg-hover cursor-pointer"
                    >
                      <span className="min-w-0 flex-1 truncate">{a.email}</span>
                      {a.id === account?.id && <Check className="size-3.5 text-cobalt" strokeWidth={2} aria-label="Current" />}
                    </button>
                  ))}
                  <a
                    role="menuitem"
                    href="/login?add=1"
                    className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] text-ink-2 hover:bg-hover hover:text-ink"
                  >
                    <Plus className="size-3.5" strokeWidth={1.75} aria-hidden />
                    Add another Gmail
                  </a>
                  <div className="my-1 h-px bg-rule" />
                </>
              )}
              <button role="menuitem" type="button" onClick={() => { onToggleTheme(); setMenuOpen(false); }}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] text-ink-2 hover:bg-hover hover:text-ink cursor-pointer">
                {dark ? <Sun className="size-3.5" strokeWidth={1.75} aria-hidden /> : <Moon className="size-3.5" strokeWidth={1.75} aria-hidden />}
                {dark ? "Light appearance" : "Dark appearance"}
              </button>
              <button role="menuitem" type="button" onClick={() => { onFeedback(); setMenuOpen(false); }}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] text-ink-2 hover:bg-hover hover:text-ink cursor-pointer">
                <MessageSquareText className="size-3.5" strokeWidth={1.75} aria-hidden />
                Send feedback
              </button>
              <button role="menuitem" type="button" onClick={onSignOut}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] text-ink-2 hover:bg-hover hover:text-ink cursor-pointer">
                <LogOut className="size-3.5" strokeWidth={1.75} aria-hidden />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
