import React from 'react';

interface ConfirmButtonProps {
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
}

export function ConfirmButton({ onClick, disabled, loading }: ConfirmButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`w-full py-2.5 px-4 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-sm ${
        disabled || loading
          ? 'bg-base-200 border border-base-300 text-base-content/60 cursor-not-allowed shadow-none'
          : 'bg-primary hover:opacity-90 text-base-100 cursor-pointer'
      }`}
      id="confirm-commitments-btn"
    >
      {loading ? (
        <>
          <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
          Writing Tasks...
        </>
      ) : (
        <>
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
          Confirm & Sync to To Do + Calendar
        </>
      )}
    </button>
  );
}
