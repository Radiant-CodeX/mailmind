'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '../../components/layout/Sidebar';
import { Header } from '../../components/layout/Header';
import { EmailList } from '../../components/inbox/EmailList';
import { EmailDetail } from '../../components/detail/EmailDetail';
import { CalendarView } from '../../components/calendar/CalendarView';
import { RAGSettingsView } from '../../components/rag/RAGSettingsView';
import { ComposeWindow } from '../../components/inbox/ComposeWindow';
import { TrashToast } from '../../components/shared/TrashToast';
import { EvaluationView } from '../../components/evaluation/EvaluationView';
import { TasksView } from '../../components/tasks/TasksView';

import { useEmails } from '../../hooks/useEmails';
import { useEmailDetail } from '../../hooks/useEmailDetail';
import { useCommitments } from '../../hooks/useCommitments';
import { useCalendar } from '../../hooks/useCalendar';
import { checkAuthStatus, logoutUser, createCalendarEvent, AccountInfo } from '../../lib/api';
import { rememberLogin, getRememberMe, clearRememberedLogin, Provider } from '../../lib/session';
import { userStorage } from '../../lib/userStorage';
import { CalendarEvent } from '../../lib/types';

export default function Home() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('Inbox');
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>('dark');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const [authenticated, setAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userName, setUserName] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<AccountInfo | null>(null);
  const [provider, setProvider] = useState<Provider>('microsoft');
  const [checkingAuth, setCheckingAuth] = useState(true);
  // Per-tab state — NOT persisted server-side (multi-tab safety).
  // Initialized from the default account on first auth check.
  const [currentAccountId, setCurrentAccountId] = useState<string | null>(null);
  const [isComposeOpen, setIsComposeOpen] = useState(false);

  // Load auth status on mount — retries up to 3× (500ms apart) to handle the
  // race where cookies from the OAuth popup haven't been flushed to the browser
  // cookie jar before the dashboard mounts and makes its first request.
  useEffect(() => {
    async function loadAuthStatus() {
      const MAX_ATTEMPTS = 3;
      for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
        if (attempt > 0) await new Promise(r => setTimeout(r, 600));
        try {
          const data = await checkAuthStatus();
          if (data.authenticated) {
            setAuthenticated(true);
            const email = data.user?.primary_email ?? data.default_account?.email ?? null;
            const displayName = data.user?.display_name ?? null;
            setUserEmail(email);
            setUserName(displayName);
            if (data.default_account) {
              setUserProfile(data.default_account);
              setCurrentAccountId(data.default_account.id);
              const p = data.default_account.provider;
              if (p === 'google' || p === 'microsoft') setProvider(p);
            }
            if (email) userStorage.setUser(email);
            setCheckingAuth(false);
            return;
          }
        } catch (err) {
          console.error(`Auth check attempt ${attempt + 1} failed:`, err);
        }
      }
      // All retries exhausted — redirect to login
      router.push('/');
    }
    loadAuthStatus();
  }, [router]);

  const toggleTheme = () => {
    setThemeMode((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => !prev);
  };

  const MAIL_TABS = ['Inbox', 'Drafts', 'Sent', 'Spam', 'Trash', 'Starred', 'Important'];
  const activeFolder = MAIL_TABS.includes(activeTab) ? activeTab : 'Inbox';
  // The AI pipeline (triage / commitments / draft reply) doesn't apply to mail
  // you've already sent — hide it for the Sent folder.
  const showPipeline = activeFolder !== 'Sent';

  const {
    emails,
    selectedEmail,
    selectedEmailId,
    setSelectedEmailId,
    searchQuery,
    setSearchQuery,
    sortKey,
    setSortKey,
    filters,
    setFilters,
    total,
    pageIndex,
    pageSize,
    hasNextPage,
    hasPrevPage,
    nextPage,
    prevPage,
    loading,
    refresh,
    toggleStar,
    trashEmail,
    undoTrash,
    dismissTrashToast,
    pendingTrash,
    restoreEmail,
    markRead,
    archiveEmail,
    reportSpam,
    isStreaming,
    triageProgress,
  } = useEmails(activeFolder, authenticated && !checkingAuth);

  // Opening an email marks it read.
  const handleSelectEmail = (id: string) => {
    setSelectedEmailId(id);
    const target = emails.find((e) => e.id === id);
    if (target && target.isRead === false) markRead(id, true);
  };

  const {
    loading: detailLoading,
    error: detailError,
    classification,
    triageResult,
    precedents,
    attachments: detailAttachments,
    pipelineCommitments,
    aiDraft,
    setAiDraft,
    isGeneratingDraft,
    generateDraft,
    isDraftApproved,
    setIsDraftApproved,
    activeStyle,
    setActiveStyle,
    isSendingDraft,
    sendDraft,
  } = useEmailDetail(selectedEmail, showPipeline, userEmail);

  const {
    commitments,
    loading: commitmentsLoading,
    error: commitmentsError,
    confirming,
    confirmed,
    taskUrls,
    eventUrls,
    toggleCommitment,
    confirmSelected,
  } = useCommitments(
    showPipeline ? selectedEmail?.id || null : null,
    showPipeline ? selectedEmail?.body || null : null,
    showPipeline ? pipelineCommitments : undefined,
  );

  const {
    events: calendarEvents,
    loading: calendarLoading,
    error: calendarError,
    checkConflict,
    loadCalendar,
  } = useCalendar(authenticated && !checkingAuth);

  if (checkingAuth) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-bg-base text-text-primary">
        <div className="text-center">
          <div className="w-8 h-8 rounded-full border-2 border-[var(--accent-primary)] border-t-transparent animate-spin mx-auto mb-4"></div>
          <p className="text-xs text-[var(--text-muted)] font-medium">Checking authorization status...</p>
        </div>
      </div>
    );
  }

  const handleLogout = async () => {
    try {
      // Remember this account for one-tap Quick Login (valid for 1 week) —
      // only when "Remember me" was checked, and only on sign-out.
      if (userEmail && getRememberMe()) {
        rememberLogin(userEmail, provider);
      }
      await logoutUser();
    } catch (err) {
      console.error('Logout request failed (signing out anyway)', err);
    } finally {
      // Always sign the user out locally and return to the login page, even if
      // the backend logout call failed.
      // Clear quick login on logout to prevent other users on shared device from
      // impersonating this user. When the same user logs back in, their quick login
      // will be automatically re-saved.
      clearRememberedLogin();
      userStorage.logout();
      setAuthenticated(false);
      setUserEmail(null);
      setUserProfile(null);
      router.replace('/');
    }
  };

  return (
    <div
      className={`flex h-screen w-screen overflow-hidden text-text-primary transition-colors duration-200 ${
        themeMode === 'light' ? 'theme-light bg-bg-base' : 'theme-dark bg-bg-base'
      }`}
      id="app-workspace"
    >
      {/* 1. Leftmost Navigation Sidebar (Collapsible on Logo Click) */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={toggleSidebar}
        authenticated={authenticated}
        userEmail={userEmail}
        userName={userName}
        userProfile={userProfile}
        provider={provider}
        onLoginClick={() => {}}
        onLogoutClick={handleLogout}
        onComposeClick={() => setIsComposeOpen(true)}
        onAccountChange={setCurrentAccountId}
      />

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header toolbar with Light/Dark Mode toggle */}
        <Header themeMode={themeMode} onToggleTheme={toggleTheme} />

        {/* Dynamic View rendering depending on activeTab */}
        <div className="flex-1 flex overflow-hidden">
          {MAIL_TABS.includes(activeTab) && (
            <>
              {/* Panel A: Inbox — 45% when inspector open, full width otherwise */}
              <div
                className={`h-full flex flex-col overflow-hidden transition-all duration-200 ${
                  selectedEmailId ? 'w-[45%] border-r border-[var(--border)]' : 'flex-1'
                }`}
              >
                <EmailList
                  emails={emails}
                  selectedEmailId={selectedEmailId}
                  onSelectEmail={handleSelectEmail}
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                  sortKey={sortKey}
                  onSortChange={setSortKey}
                  filters={filters}
                  onFiltersChange={setFilters}
                  total={total}
                  pageIndex={pageIndex}
                  pageSize={pageSize}
                  hasNextPage={hasNextPage}
                  hasPrevPage={hasPrevPage}
                  onNextPage={nextPage}
                  onPrevPage={prevPage}
                  loading={loading}
                  onRefresh={refresh}
                  isFullWidth={true}
                  activeFolder={activeFolder}
                  onToggleStar={toggleStar}
                  onTrashEmail={trashEmail}
                  onRestoreEmail={restoreEmail}
                  onArchiveEmail={archiveEmail}
                  onReportSpam={reportSpam}
                  onToggleRead={markRead}
                  isStreaming={isStreaming}
                  triageProgress={triageProgress}
                />
              </div>

              {/* Panel B: Email inspector — 55% split pane */}
              {selectedEmailId && (
                <div className="w-[55%] h-full overflow-hidden">
                  <EmailDetail
                    key={selectedEmailId}
                    email={selectedEmail}
                    loading={detailLoading}
                    error={detailError}
                    classification={classification}
                    triageResult={triageResult}
                    precedents={precedents}
                    aiDraft={aiDraft}
                    setAiDraft={setAiDraft}
                    isGeneratingDraft={isGeneratingDraft}
                    generateDraft={generateDraft}
                    isDraftApproved={isDraftApproved}
                    setIsDraftApproved={setIsDraftApproved}
                    activeStyle={activeStyle}
                    setActiveStyle={setActiveStyle}
                    isSendingDraft={isSendingDraft}
                    sendDraft={sendDraft}
                    commitments={commitments}
                    commitmentsLoading={commitmentsLoading}
                    commitmentsError={commitmentsError}
                    confirmingCommitments={confirming}
                    confirmedCommitments={confirmed}
                    taskUrls={taskUrls}
                    eventUrls={eventUrls}
                    toggleCommitment={toggleCommitment}
                    confirmSelectedCommitments={confirmSelected}
                    checkConflict={checkConflict}
                    onClose={() => setSelectedEmailId(null)}
                    showPipeline={showPipeline}
                    provider={provider}
                  />
                </div>
              )}
            </>
          )}

          {activeTab === 'Calendar' && (
            <CalendarView
              events={calendarEvents}
              loading={calendarLoading}
              error={calendarError}
              onRefresh={loadCalendar}
              provider={provider}
              onCreateEvent={async (event: Partial<CalendarEvent>) => {
                await createCalendarEvent({
                  title: event.title || '',
                  start_time: event.start_time || '',
                  end_time: event.end_time,
                });
              }}
            />
          )}

          {activeTab === 'RAG Settings' && <RAGSettingsView />}
          {activeTab === 'Tasks' && <TasksView />}
          {activeTab === 'Evaluation' && <EvaluationView />}
        </div>
      </div>

      {/* Trash undo toast — floats above everything */}
      {pendingTrash && (
        <TrashToast
          email={pendingTrash.email}
          startedAt={pendingTrash.startedAt}
          onUndo={undoTrash}
          onDismiss={dismissTrashToast}
        />
      )}

      {isComposeOpen && (
        <ComposeWindow
          onClose={() => {
            setIsComposeOpen(false);
            refresh();
          }}
        />
      )}
    </div>
  );
}
