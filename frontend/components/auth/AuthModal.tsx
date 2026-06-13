import React, { useState } from 'react';

interface AuthModalProps {
  userCode: string;
  verificationUri: string;
  onCancel: () => void;
}

export function AuthModal({ userCode, verificationUri, onCancel }: AuthModalProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(userCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code', err);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" id="auth-modal-overlay">
      <div className="relative w-full max-w-md bg-base-100 border border-base-300 rounded-xl shadow-2xl p-6 overflow-hidden text-center text-text-primary">
        {/* Decorative background pulse */}
        <div className="absolute -right-12 -top-12 w-28 h-28 rounded-full bg-primary/10 blur-xl"></div>
        
        {/* Micro-animating spinning loader for polling visual */}
        <div className="mx-auto w-12 h-12 rounded-full bg-base-200 border border-base-300 flex items-center justify-center mb-4 text-primary relative">
          <svg
            className="w-6 h-6 animate-spin"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M21 20v-5h-.581m0 0a8.003 8.003 0 01-15.357-2"
            />
          </svg>
        </div>

        <h3 className="text-base font-bold text-base-content mb-2" id="auth-modal-title">
          Sign In with Microsoft
        </h3>
        
        <p className="text-xs text-base-content/60 leading-relaxed mb-6">
          To connect your real Outlook account, visit the Microsoft device authorization page and enter the code below.
        </p>

        {/* Action Link Box */}
        <div className="mb-5">
          <a
            href={verificationUri}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-base-200 hover:bg-base-200/80 border border-base-300 rounded-lg text-xs font-bold text-primary transition-all cursor-pointer shadow-sm hover:shadow"
            id="auth-verification-link"
          >
            1. Open Authorization Page
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        </div>

        {/* Code Visual Pill */}
        <div className="mb-6 bg-base-200 border border-base-300 rounded-lg p-4 flex flex-col items-center justify-center gap-2">
          <span className="text-[10px] text-base-content/60 uppercase tracking-wider font-bold">
            2. Enter this Code
          </span>
          <div className="flex items-center gap-3">
            <span className="font-mono text-2xl font-black tracking-widest text-base-content select-all" id="auth-user-code">
              {userCode}
            </span>
            <button
              onClick={handleCopy}
              className={`p-1.5 rounded-md border text-xs font-semibold transition-all cursor-pointer ${
                copied
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500'
                  : 'bg-base-100 hover:bg-base-200 border-base-300 text-base-content/60 hover:text-base-content'
              }`}
              title="Copy Code"
              id="btn-copy-auth-code"
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>

        {/* Loading status bar */}
        <div className="text-[10px] font-semibold text-base-content/60 flex items-center justify-center gap-1.5 mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping"></span>
          Waiting for authentication on Microsoft...
        </div>

        {/* Close Button */}
        <button
          onClick={onCancel}
          className="w-full py-2 bg-base-200 hover:bg-red-500/10 border border-base-300 hover:border-red-500/20 rounded-lg text-xs font-bold text-base-content/60 hover:text-red-500 transition-all cursor-pointer"
          id="btn-cancel-auth"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
