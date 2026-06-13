import React, { useState, useEffect, useRef } from 'react';
import { composeEmail } from '../../lib/api';

interface ComposeWindowProps {
  onClose: () => void;
}

export function ComposeWindow({ onClose }: ComposeWindowProps) {
  const [to, setTo] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [cc, setCc] = useState('');
  const [bcc, setBcc] = useState('');

  // UI state
  const [isMinimized, setIsMinimized] = useState(false);
  const [showCc, setShowCc] = useState(false);
  const [showBcc, setShowBcc] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Field validation states
  const [validationErrors, setValidationErrors] = useState<{ to?: string; subject?: string; body?: string }>({});

  const toInputRef = useRef<HTMLInputElement>(null);

  // Focus the "To" input field on mount
  useEffect(() => {
    if (toInputRef.current) {
      toInputRef.current.focus();
    }
  }, []);

  const validate = () => {
    const errors: { to?: string; subject?: string; body?: string } = {};
    if (!to.trim()) {
      errors.to = 'Recipient email is required';
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      const emails = to.split(',').map(e => e.trim());
      const allValid = emails.every(email => emailRegex.test(email));
      if (!allValid) {
        errors.to = 'One or more recipient email addresses are invalid';
      }
    }

    if (!subject.trim()) {
      errors.subject = 'Subject is required';
    }

    if (!body.trim()) {
      errors.body = 'Email body is required';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!validate()) {
      return;
    }

    setIsSending(true);
    try {
      await composeEmail({
        to,
        subject,
        body,
        cc: showCc ? cc : undefined,
        bcc: showBcc ? bcc : undefined,
      });

      setSuccess(true);
      // Automatically close after a short delay so user can see success message
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send email. Please try again.';
      setError(errorMessage);
    } finally {
      setIsSending(false);
    }
  };

  if (success) {
    return (
      <div
        className="fixed bottom-4 right-4 z-50 w-96 bg-base-100 border border-base-300 rounded-xl shadow-2xl p-6 text-center animate-fade-in"
        id="compose-window-success"
      >
        <div className="mx-auto w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-4 text-emerald-500">
          <svg className="w-6 h-6 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h4 className="text-sm font-bold text-base-content mb-1">Email Sent!</h4>
        <p className="text-xs text-base-content/60">Your message has been sent successfully.</p>
      </div>
    );
  }

  return (
    <div
      className={`fixed bottom-0 right-4 z-50 w-96 bg-base-100 border border-base-300 rounded-t-xl shadow-2xl flex flex-col transition-all duration-300 ease-in-out ${
        isMinimized ? 'h-12' : 'h-[500px]'
      }`}
      id="compose-window"
    >
      {/* Header bar */}
      <div className="h-12 bg-base-200 border-b border-base-300 px-4 flex items-center justify-between rounded-t-xl select-none shrink-0">
        <span className="text-xs font-bold text-base-content uppercase tracking-wider">
          New Message
        </span>
        <div className="flex items-center gap-1.5">
          {/* Minimize / Restore button */}
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1 hover:bg-base-100 rounded text-base-content/60 hover:text-base-content cursor-pointer transition-colors"
            title={isMinimized ? 'Restore Window' : 'Minimize Window'}
            id="btn-compose-minimize"
          >
            {isMinimized ? (
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            )}
          </button>

          {/* Close button */}
          <button
            onClick={onClose}
            className="p-1 hover:bg-red-500/10 rounded text-base-content/60 hover:text-red-500 cursor-pointer transition-colors"
            title="Discard Draft"
            id="btn-compose-close"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Form body */}
      {!isMinimized && (
        <form onSubmit={handleSend} className="flex-1 flex flex-col p-4 overflow-hidden">
          <div className="flex-1 flex flex-col gap-3 overflow-y-auto pr-1 custom-scrollbar min-h-0">
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded text-red-500 text-[10px] font-semibold leading-relaxed animate-fade-in">
                {error}
              </div>
            )}

            {/* Recipient Field */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 border-b border-base-200 pb-1 relative">
                <span className="text-[10px] font-bold text-base-content/60 w-8 select-none">To:</span>
                <input
                  ref={toInputRef}
                  type="text"
                  value={to}
                  onChange={(e) => {
                    setTo(e.target.value);
                    if (validationErrors.to) {
                      setValidationErrors((prev) => ({ ...prev, to: undefined }));
                    }
                  }}
                  disabled={isSending}
                  placeholder="recipient@example.com"
                  className="flex-1 bg-transparent border-0 text-xs text-base-content focus:outline-none placeholder-base-content/60/50 font-medium"
                  id="compose-to-input"
                />
                {/* Cc/Bcc Toggle Triggers */}
                <div className="flex items-center gap-1.5 text-[10px] font-bold text-base-content/60 select-none absolute right-1">
                  {!showCc && (
                    <button
                      type="button"
                      onClick={() => setShowCc(true)}
                      className="hover:text-base-content transition-colors cursor-pointer"
                    >
                      Cc
                    </button>
                  )}
                  {!showBcc && (
                    <button
                      type="button"
                      onClick={() => setShowBcc(true)}
                      className="hover:text-base-content transition-colors cursor-pointer"
                    >
                      Bcc
                    </button>
                  )}
                </div>
              </div>
              {validationErrors.to && (
                <span className="text-[9px] font-semibold text-red-500">{validationErrors.to}</span>
              )}
            </div>

            {/* Collapsible Cc Field */}
            {showCc && (
              <div className="flex flex-col gap-1 animate-fade-in">
                <div className="flex items-center gap-2 border-b border-base-200 pb-1 relative">
                  <span className="text-[10px] font-bold text-base-content/60 w-8 select-none">Cc:</span>
                  <input
                    type="text"
                    value={cc}
                    onChange={(e) => setCc(e.target.value)}
                    disabled={isSending}
                    placeholder="cc1@example.com"
                    className="flex-1 bg-transparent border-0 text-xs text-base-content focus:outline-none placeholder-base-content/60/50 font-medium"
                    id="compose-cc-input"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setShowCc(false);
                      setCc('');
                    }}
                    className="text-[10px] font-bold text-base-content/60 hover:text-red-500 transition-colors cursor-pointer absolute right-1"
                    title="Remove Cc"
                  >
                    ×
                  </button>
                </div>
              </div>
            )}

            {/* Collapsible Bcc Field */}
            {showBcc && (
              <div className="flex flex-col gap-1 animate-fade-in">
                <div className="flex items-center gap-2 border-b border-base-200 pb-1 relative">
                  <span className="text-[10px] font-bold text-base-content/60 w-8 select-none">Bcc:</span>
                  <input
                    type="text"
                    value={bcc}
                    onChange={(e) => setBcc(e.target.value)}
                    disabled={isSending}
                    placeholder="bcc1@example.com"
                    className="flex-1 bg-transparent border-0 text-xs text-base-content focus:outline-none placeholder-base-content/60/50 font-medium"
                    id="compose-bcc-input"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setShowBcc(false);
                      setBcc('');
                    }}
                    className="text-[10px] font-bold text-base-content/60 hover:text-red-500 transition-colors cursor-pointer absolute right-1"
                    title="Remove Bcc"
                  >
                    ×
                  </button>
                </div>
              </div>
            )}

            {/* Subject Field */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 border-b border-base-200 pb-1">
                <span className="text-[10px] font-bold text-base-content/60 w-8 select-none">Sub:</span>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => {
                    setSubject(e.target.value);
                    if (validationErrors.subject) {
                      setValidationErrors((prev) => ({ ...prev, subject: undefined }));
                    }
                  }}
                  disabled={isSending}
                  placeholder="Subject"
                  className="flex-1 bg-transparent border-0 text-xs text-base-content focus:outline-none placeholder-base-content/60/50 font-medium"
                  id="compose-subject-input"
                />
              </div>
              {validationErrors.subject && (
                <span className="text-[9px] font-semibold text-red-500">{validationErrors.subject}</span>
              )}
            </div>

            {/* Body Textarea */}
            <div className="flex-1 flex flex-col gap-1 min-h-[150px]">
              <textarea
                value={body}
                onChange={(e) => {
                  setBody(e.target.value);
                  if (validationErrors.body) {
                    setValidationErrors((prev) => ({ ...prev, body: undefined }));
                  }
                }}
                disabled={isSending}
                placeholder="Write your email here..."
                className="w-full flex-1 p-3 rounded bg-base-200 border border-base-300 text-xs text-base-content leading-relaxed focus:outline-none focus:border-primary resize-none font-medium custom-scrollbar"
                id="compose-body-textarea"
              ></textarea>
              {validationErrors.body && (
                <span className="text-[9px] font-semibold text-red-500">{validationErrors.body}</span>
              )}
            </div>
          </div>

          {/* Footer Controls */}
          <div className="flex items-center justify-between border-t border-base-300 pt-3 mt-3 shrink-0">
            <button
              type="button"
              onClick={onClose}
              disabled={isSending}
              className="p-2 bg-base-200 border border-base-300 hover:border-red-500/20 text-base-content/60 hover:text-red-500 rounded-lg text-xs transition-all cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50"
              id="btn-compose-discard"
              title="Discard Email"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Discard
            </button>

            <button
              type="submit"
              disabled={isSending}
              className="px-5 py-2 bg-primary hover:opacity-90 disabled:opacity-50 text-base-100 rounded-lg text-xs font-bold transition-all shadow-sm cursor-pointer flex items-center gap-1.5"
              id="btn-compose-send"
            >
              {isSending ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-base-100 border-t-transparent animate-spin rounded-full"></span>
                  Sending...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4 rotate-45 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  Send
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
