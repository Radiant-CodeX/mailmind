"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Menu, SquarePen } from "lucide-react";

import { Rail, type View } from "../../components/mm/Rail";
import { MailList } from "../../components/mm/MailList";
import { MailView } from "../../components/mm/MailView";
import { TaskBoard } from "../../components/mm/TaskBoard";
import { Settings } from "../../components/mm/Settings";
import { IconButton } from "../../components/mm/ui";
import { CATEGORY_LABEL, categoryOf, needsYou } from "../../components/mm/format";
import { LogoGlyph } from "../../components/shared/LogoGlyph";
import { CalendarView } from "../../components/calendar/CalendarView";
import { ComposeWindow } from "../../components/inbox/ComposeWindow";
import { TrashToast } from "../../components/shared/TrashToast";
import { FeedbackModal } from "../../components/shared/FeedbackModal";
import { OnboardingFlow } from "../../components/onboarding/OnboardingFlow";
import type { OverridePriority } from "../../components/inbox/PriorityOverrideMenu";

import { useEmails } from "../../hooks/useEmails";
import { useEmailDetail } from "../../hooks/useEmailDetail";
import { useCommitments } from "../../hooks/useCommitments";
import { useCalendar } from "../../hooks/useCalendar";
import {
  AccountInfo,
  ToneProfile,
  checkAuthStatus,
  createCalendarEvent,
  fetchToneProfile,
  logoutUser,
  overrideEmailPriority,
  saveCampusProfile,
} from "../../lib/api";
import { clearRememberedLogin, getRememberMe, rememberLogin } from "../../lib/session";
import { userStorage } from "../../lib/userStorage";
import { clearScores } from "../../lib/scoreCache";
import type { CalendarEvent, Email, Priority } from "../../lib/types";

const FOLDER_FOR: Partial<Record<View, string>> = {
  needs: "Inbox",
  all: "Inbox",
  starred: "Starred",
  sent: "Sent",
  drafts: "Drafts",
  spam: "Spam",
  trash: "Trash",
};

const TITLE_FOR: Partial<Record<View, string>> = {
  needs: "Inbox",
  all: "Inbox",
  starred: "Starred",
  sent: "Sent",
  drafts: "Drafts",
  spam: "Spam",
  trash: "Trash",
};

const SCORE_FOR: Record<Priority, number> = { CRITICAL: 90, HIGH: 65, MEDIUM: 40, LOW: 10 };

export default function Dashboard() {
  const router = useRouter();

  // ── session ──────────────────────────────────────────────────────────────
  const [authenticated, setAuthenticated] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userName, setUserName] = useState<string | null>(null);
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Cookies from the OAuth popup can land a beat after the redirect.
      for (let attempt = 0; attempt < 3; attempt++) {
        if (attempt > 0) await new Promise((r) => setTimeout(r, 600));
        try {
          const data = await checkAuthStatus();
          if (cancelled) return;
          if (data.authenticated) {
            const email = data.user?.primary_email ?? data.default_account?.email ?? null;
            setAuthenticated(true);
            setUserEmail(email);
            setUserName(data.user?.display_name ?? null);
            setAccount(data.default_account ?? null);
            if (email) {
              userStorage.setUser(email);
              if (!localStorage.getItem(`mailmind_onboarded_${email}`)) setShowOnboarding(true);
            }
            setCheckingAuth(false);
            return;
          }
        } catch {
          /* retry */
        }
      }
      if (!cancelled) router.push("/login");
    })();
    return () => { cancelled = true; };
  }, [router]);

  // ── appearance ───────────────────────────────────────────────────────────
  const [dark, setDark] = useState(
    () => typeof document !== "undefined" && document.documentElement.getAttribute("data-theme") === "mailmind-dark",
  );
  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.setAttribute("data-theme", next ? "mailmind-dark" : "mailmind");
    try { localStorage.setItem("mm-theme", next ? "dark" : "light"); } catch {}
  };

  // ── navigation ───────────────────────────────────────────────────────────
  const [view, setView] = useState<View>("needs");
  const [category, setCategory] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [composeOpen, setComposeOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const isMail = view in FOLDER_FOR;
  const folder = FOLDER_FOR[view] ?? "Inbox";
  const triageApplies = ["Inbox", "Starred"].includes(folder);
  const showPipeline = folder !== "Sent" && folder !== "Drafts";

  const {
    emails, allEmails, setSelectedEmailId, selectedEmailId,
    searchQuery, setSearchQuery, total, pageIndex, pageSize, hasNextPage, hasPrevPage, nextPage, prevPage,
    loading, refresh, toggleStar, trashEmail, undoTrash, dismissTrashToast, pendingTrash, restoreEmail,
    markRead, archiveEmail, isStreaming, triageProgress, triageTotal, patchEmailTriage, markDone,
  } = useEmails(folder, authenticated && !checkingAuth);

  // Local priority corrections, applied instantly while the server learns them.
  const [overrides, setOverrides] = useState<Record<string, Priority>>({});
  const applyOverride = useCallback(
    (e: Email): Email => {
      const p = overrides[e.id];
      if (!p) return e;
      return { ...e, composite_score: SCORE_FOR[p], triage: e.triage ? { ...e.triage, priority: p, composite_score: SCORE_FOR[p] } : e.triage };
    },
    [overrides],
  );

  const pageEmails = useMemo(() => emails.map(applyOverride), [emails, applyOverride]);
  const everyEmail = useMemo(() => allEmails.map(applyOverride), [allEmails, applyOverride]);

  const listEmails = useMemo(() => {
    if (!isMail) return [];
    if (view === "needs") {
      const q = searchQuery.trim().toLowerCase();
      return everyEmail.filter((e) => needsYou(e) && (!q || `${e.subject} ${e.sender}`.toLowerCase().includes(q)));
    }
    if (category) return everyEmail.filter((e) => categoryOf(e) === category);
    return pageEmails;
  }, [isMail, view, category, everyEmail, pageEmails, searchQuery]);

  const counts = useMemo(() => {
    const cats: Record<string, number> = {};
    let needs = 0;
    let unread = 0;
    for (const e of everyEmail) {
      if (needsYou(e)) needs++;
      if (e.isRead === false) unread++;
      const c = categoryOf(e);
      if (c) cats[c] = (cats[c] ?? 0) + 1;
    }
    return { needs, unread, cats };
  }, [everyEmail]);

  // The open email may live on another page than the one shown (Needs you
  // spans every loaded page), so resolve it from the full set.
  const selected = useMemo(() => {
    if (!selectedEmailId) return null;
    const onPage = pageEmails.find((e) => e.id === selectedEmailId);
    return onPage ?? everyEmail.find((e) => e.id === selectedEmailId) ?? null;
  }, [selectedEmailId, pageEmails, everyEmail]);

  const open = useCallback((id: string) => {
    setSelectedEmailId(id);
    const target = everyEmail.find((e) => e.id === id);
    if (target && target.isRead === false) markRead(id, true);
  }, [everyEmail, markRead, setSelectedEmailId]);

  const close = useCallback(() => setSelectedEmailId(null), [setSelectedEmailId]);

  const onOverride = (id: string, sender: string, next: OverridePriority, current: Priority) => {
    if (next === "DONE") return markDone(id, sender, current);
    setOverrides((o) => ({ ...o, [id]: next }));
    overrideEmailPriority({ email_id: id, sender, override_priority: next, original_priority: current }).catch(() => {
      setOverrides((o) => {
        const n = { ...o };
        delete n[id];
        return n;
      });
    });
  };

  // ── detail pipeline ──────────────────────────────────────────────────────
  const detail = useEmailDetail(selected, showPipeline, userEmail, patchEmailTriage);
  const detailEmail = useMemo(() => {
    if (!selected) return null;
    if (!detail.fullContent) return selected;
    return { ...selected, html_body: detail.fullContent.html_body ?? selected.html_body, body: detail.fullContent.body || selected.body };
  }, [selected, detail.fullContent]);

  useEffect(() => {
    if (detail.isDraftApproved && selected?.id) markDone(selected.id, selected.sender ?? "", selected.triage?.priority);
  }, [detail.isDraftApproved, selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const commit = useCommitments(
    showPipeline ? selected?.id || null : null,
    showPipeline ? selected?.body || null : null,
    showPipeline ? detail.pipelineCommitments : undefined,
  );
  const calendar = useCalendar(authenticated && !checkingAuth);

  const [tone, setTone] = useState<ToneProfile | null>(null);
  useEffect(() => {
    if (authenticated) fetchToneProfile().then(setTone);
  }, [authenticated]);

  // ── keyboard ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isMail) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      const ids = listEmails.map((m) => m.id);
      const idx = selectedEmailId ? ids.indexOf(selectedEmailId) : -1;
      if (e.key === "j" && ids.length) { e.preventDefault(); open(ids[Math.min(ids.length - 1, idx + 1)]); }
      else if (e.key === "k" && ids.length) { e.preventDefault(); open(ids[Math.max(0, idx - 1)]); }
      else if (e.key === "e" && selected) { e.preventDefault(); markDone(selected.id, selected.sender, selected.triage?.priority); }
      else if (e.key === "s" && selected) { e.preventDefault(); toggleStar(selected.id); }
      else if (e.key === "/") { e.preventDefault(); document.querySelector<HTMLInputElement>('input[placeholder="Search mail"]')?.focus(); }
      else if (e.key === "c") { e.preventDefault(); setComposeOpen(true); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isMail, listEmails, selectedEmailId, selected, open, markDone, toggleStar]);

  // Changing view closes an open email that no longer belongs to it.
  useEffect(() => { setSelectedEmailId(null); }, [view, category]); // eslint-disable-line react-hooks/exhaustive-deps

  const signOut = async () => {
    try {
      if (userEmail && getRememberMe()) rememberLogin(userEmail, "google");
      await logoutUser();
    } catch {
      /* sign out locally regardless */
    } finally {
      clearRememberedLogin();
      const uid = userStorage.getUser();
      if (uid) await clearScores(uid);
      userStorage.logout();
      router.replace("/login");
    }
  };

  if (checkingAuth) {
    return (
      <div className="mm flex h-dvh w-screen items-center justify-center bg-bg">
        <div className="flex items-center gap-2.5 text-[13px] text-ink-3">
          <LogoGlyph className="size-6 text-ink" />
          <span>Opening your inbox</span>
        </div>
      </div>
    );
  }

  const inFolder = view !== "needs" && view !== "all";
  const listTitle = category ? CATEGORY_LABEL[category] ?? "Inbox" : TITLE_FOR[view] ?? "Inbox";
  const listMode = view === "needs" ? "needs" : view === "all" ? "all" : "folder";

  const rail = (inDrawer: boolean) => (
    <Rail
      view={view}
      onView={setView}
      category={category}
      onCategory={setCategory}
      needsCount={counts.needs}
      unreadCount={counts.unread}
      categoryCounts={counts.cats}
      onCompose={() => setComposeOpen(true)}
      userEmail={userEmail}
      userName={userName}
      account={account}
      dark={dark}
      onToggleTheme={toggleTheme}
      onFeedback={() => setFeedbackOpen(true)}
      onSignOut={signOut}
      onNavigate={inDrawer ? () => setDrawerOpen(false) : undefined}
    />
  );

  return (
    <div className="mm flex h-dvh w-screen overflow-hidden bg-bg text-ink">
      {/* Rail: fixed column on large screens, drawer below. */}
      <aside id="sidebar" className="hidden w-[232px] shrink-0 border-r border-rule lg:block">
        {rail(false)}
      </aside>
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button type="button" aria-label="Close navigation" onClick={() => setDrawerOpen(false)} className="absolute inset-0 bg-ink/25" />
          <div className="animate-fade-in absolute inset-y-0 left-0 w-[272px] border-r border-rule shadow-pop">{rail(true)}</div>
        </div>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        {/* Compact bar below lg */}
        <div className="flex h-12 shrink-0 items-center gap-1 border-b border-rule bg-surface px-2 lg:hidden">
          <IconButton icon={Menu} label="Open navigation" onClick={() => setDrawerOpen(true)} />
          <span className="flex items-center gap-2 pl-1 text-[15px] font-semibold text-ink">
            <LogoGlyph className="size-6 text-ink" /> MailMind
          </span>
          <IconButton icon={SquarePen} label="Compose" onClick={() => setComposeOpen(true)} className="ml-auto" />
        </div>

        <div className="flex min-h-0 flex-1">
          {isMail && (
            <>
              <div
                id="email-list-panel"
                className={`min-w-0 border-rule ${
                  selected ? "hidden lg:block lg:w-[400px] lg:shrink-0 lg:border-r xl:w-[440px]" : "flex-1"
                }`}
              >
                <MailList
                  title={listTitle}
                  mode={category ? "all" : listMode}
                  emails={listEmails}
                  selectedId={selectedEmailId}
                  onOpen={open}
                  onModeChange={(m) => setView(m)}
                  showModeSwitch={!inFolder && !category}
                  triageApplies={triageApplies}
                  search={searchQuery}
                  onSearch={setSearchQuery}
                  loading={loading}
                  onRefresh={refresh}
                  total={category ? listEmails.length : total}
                  pageIndex={category ? 0 : pageIndex}
                  pageSize={pageSize}
                  hasNext={!category && hasNextPage}
                  hasPrev={!category && hasPrevPage}
                  onNext={nextPage}
                  onPrev={prevPage}
                  streaming={isStreaming}
                  triageDone={triageProgress}
                  triageTotal={triageTotal}
                  onStar={toggleStar}
                  onDone={!inFolder ? markDone : undefined}
                  onArchive={!inFolder ? archiveEmail : undefined}
                  onTrash={view !== "trash" ? trashEmail : undefined}
                  onRestore={view === "trash" ? restoreEmail : undefined}
                  onToggleRead={!inFolder ? markRead : undefined}
                  onOverride={triageApplies ? onOverride : undefined}
                  onShowAll={view === "needs" ? () => setView("all") : undefined}
                />
              </div>
              {selected && detailEmail && (
                <div className="min-w-0 flex-1">
                  <MailView
                    key={selected.id}
                    email={detailEmail}
                    loading={detail.loading}
                    error={detail.error}
                    showPipeline={showPipeline}
                    classification={detail.classification}
                    triage={detail.triageResult}
                    precedents={detail.precedents}
                    draft={detail.aiDraft}
                    setDraft={detail.setAiDraft}
                    generating={detail.isGeneratingDraft}
                    generate={detail.generateDraft}
                    sent={detail.isDraftApproved}
                    setSent={detail.setIsDraftApproved}
                    style={detail.activeStyle}
                    setStyle={detail.setActiveStyle}
                    sending={detail.isSendingDraft}
                    send={detail.sendDraft}
                    tone={tone}
                    commitments={commit.commitments}
                    commitmentsLoading={commit.loading}
                    commitmentsError={commit.error}
                    confirming={commit.confirming}
                    confirmed={commit.confirmed}
                    toggleCommitment={commit.toggleCommitment}
                    confirmCommitments={commit.confirmSelected}
                    checkConflict={calendar.checkConflict}
                    onClose={close}
                    onDone={!inFolder ? () => { markDone(selected.id, selected.sender, selected.triage?.priority); close(); } : undefined}
                    onArchive={!inFolder ? () => { archiveEmail(selected.id); close(); } : undefined}
                    onTrash={view !== "trash" ? () => { trashEmail(selected.id); close(); } : undefined}
                    onStar={() => toggleStar(selected.id)}
                    onMarkUnread={!inFolder ? () => { markRead(selected.id, false); close(); } : undefined}
                  />
                </div>
              )}
            </>
          )}

          {view === "tasks" && <TaskBoard />}
          {view === "calendar" && (
            <div className="min-w-0 flex-1 overflow-hidden">
              <CalendarView
                events={calendar.events}
                loading={calendar.loading}
                error={calendar.error}
                onRefresh={calendar.loadCalendar}
                provider="google"
                onCreateEvent={async (event: Partial<CalendarEvent>) => {
                  await createCalendarEvent({ title: event.title || "", start_time: event.start_time || "", end_time: event.end_time });
                }}
              />
            </div>
          )}
          {view === "settings" && <Settings />}
        </div>
      </main>

      {pendingTrash && (
        <TrashToast email={pendingTrash.email} startedAt={pendingTrash.startedAt} onUndo={undoTrash} onDismiss={dismissTrashToast} />
      )}
      {composeOpen && <ComposeWindow onClose={() => { setComposeOpen(false); refresh(); }} />}
      <FeedbackModal isOpen={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
      {showOnboarding && (
        <OnboardingFlow
          userEmail={userEmail}
          userName={userName}
          onComplete={({ role, goals }) => {
            setShowOnboarding(false);
            if (userEmail) localStorage.setItem(`mailmind_onboarded_${userEmail}`, JSON.stringify({ role, goals, ts: Date.now() }));
            if (role === "student" || role === "faculty" || role === "staff") {
              saveCampusProfile({ role, department: null, year_of_study: null }).catch(() => {});
            }
          }}
        />
      )}
    </div>
  );
}
