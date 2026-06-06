'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '../../components/layout/Sidebar';
import { Header } from '../../components/layout/Header';
import { EmailList } from '../../components/inbox/EmailList';
import { EmailDetail } from '../../components/detail/EmailDetail';
import { CalendarView } from '../../components/calendar/CalendarView';
import { RAGSettingsView } from '../../components/rag/RAGSettingsView';

import { useEmails } from '../../hooks/useEmails';
import { useEmailDetail } from '../../hooks/useEmailDetail';
import { useCommitments } from '../../hooks/useCommitments';
import { useCalendar } from '../../hooks/useCalendar';
import { checkAuthStatus, logoutUser } from '../../lib/api';

export default function Home() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('Inbox');
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>('dark');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const [authenticated, setAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [isMockMode, setIsMockMode] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  // Load auth status on mount
  useEffect(() => {
    async function loadAuthStatus() {
      try {
        const data = await checkAuthStatus();
        if (data.authenticated) {
          setAuthenticated(true);
          setUserEmail(data.user_principal_name);
          setIsMockMode(data.status === 'mock' || data.status === 'mock_unauthenticated');
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

  const activeFolder = ['Inbox', 'Drafts', 'Sent', 'Spam', 'Trash', 'Starred', 'Important'].includes(activeTab)
    ? activeTab
    : 'Inbox';

  const {
    emails,
    selectedEmail,
    selectedEmailId,
    setSelectedEmailId,
    searchQuery,
    setSearchQuery,
    loading,
    refresh,
    toggleStar,
  } = useEmails(activeFolder);

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
  } = useEmailDetail(selectedEmail);

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
  } = useCommitments(selectedEmail?.id || null, selectedEmail?.body || null);

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
      await logoutUser();
      setAuthenticated(false);
      setUserEmail(null);
      router.push('/');
    } catch (err) {
      console.error('Logout failed', err);
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
        onLoginClick={() => {}}
        onLogoutClick={handleLogout}
      />

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header toolbar with Light/Dark Mode toggle */}
        <Header themeMode={themeMode} onToggleTheme={toggleTheme} isMockMode={isMockMode} />

        {/* Dynamic View rendering depending on activeTab */}
        <div className="flex-1 flex overflow-hidden">
          {['Inbox', 'Drafts', 'Sent', 'Spam', 'Trash', 'Starred', 'Important'].includes(activeTab) && (
            <>
              {/* Panel A: Prioritized Inbox (Full width if no mail is selected) */}
              <EmailList
                emails={emails}
                selectedEmailId={selectedEmailId}
                onSelectEmail={setSelectedEmailId}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                loading={loading}
                onRefresh={refresh}
                isFullWidth={true}
                activeFolder={activeFolder}
                onToggleStar={toggleStar}
              />

              {/* Panel B: Email Detailed View (renders side-by-side only if an email is selected) */}
              {selectedEmailId && (
                <EmailDetail
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
            />
          )}

          {activeTab === 'RAG Settings' && <RAGSettingsView />}
        </div>
      </div>
    </div>
  );
}
