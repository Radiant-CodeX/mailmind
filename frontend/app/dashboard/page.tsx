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
import { checkAuthStatus, logoutUser, createCalendarEvent } from '../../lib/api';
import { rememberLogin, getRememberMe, Provider } from '../../lib/session';
import { userStorage } from '../../lib/userStorage';
import { CalendarEvent } from '../../lib/types';

export default function Home() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('Inbox');
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>('dark');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const [authenticated, setAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [provider, setProvider] = useState<Provider>('microsoft');
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [isComposeOpen, setIsComposeOpen] = useState(false);

  // Load auth status on mount
  useEffect(() => {
    async function loadAuthStatus() {
      try {
        const data = await checkAuthStatus();
        if (data.authenticated) {
          setAuthenticated(true);
          setUserEmail(data.user_principal_name);
          if (data.provider === 'google' || data.provider === 'microsoft') setProvider(data.provider);
          // Scope all localStorage data to this user — prevents cross-account leaks.
          if (data.user_principal_name) userStorage.setUser(data.user_principal_name);
          setCheckingAuth(false);
        } else {
          router.push('/');
        }
      } catch (err) {
        console.error('Failed to get auth status', err);
        router.push('/');
      }
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
  );

  const {
    events: calendarEvents,
    loading: calendarLoading,
    error: calendarError,
    checkConflict,
    loadCalendar,
  } = useCalendar();

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
        rememberLogin('live', userEmail, provider);
      }
      await logoutUser();
    } catch (err) {
      console.error('Logout request failed (signing out anyway)', err);
    } finally {
      // Always sign the user out locally and return to the login page, even if
      // the backend logout call failed.
      // Clear all user-scoped cached data so the next user starts fresh.
      userStorage.logout();
      setAuthenticated(false);
      setUserEmail(null);
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
        provider={provider}
        onLoginClick={() => {}}
        onLogoutClick={handleLogout}
        onComposeClick={() => setIsComposeOpen(true)}
      />

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header toolbar with Light/Dark Mode toggle */}
        <Header themeMode={themeMode} onToggleTheme={toggleTheme} />

        {/* Dynamic View rendering depending on activeTab */}
        <div className="flex-1 flex overflow-hidden">
          {MAIL_TABS.includes(activeTab) && (
            <>
              {/* Panel A: Prioritized Inbox (Full width if no mail is selected) */}
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
              />

              {/* Panel B: Email Detailed View (renders side-by-side only if an email is selected) */}
              {selectedEmailId && (
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
                  
                  // Commitments Props passed down inline
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
                />
              )}
            </>
          )}

          {activeTab === 'Calendar' && (
            <CalendarView
              events={calendarEvents}
              loading={calendarLoading}
              error={calendarError}
              onRefresh={loadCalendar}
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
