import React from 'react';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function LoadingSpinner({ message = 'Loading...', size = 'md' }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-5 h-5 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  };

  return (
    <div className="flex flex-col items-center justify-center p-6 text-center animate-fade-in" id="loading-spinner">
      <div
        className={`${sizeClasses[size]} rounded-full border-primary border-t-transparent animate-spin`}
      ></div>
      {message && <p className="mt-3 text-sm text-base-content/60 tracking-wide">{message}</p>}
    </div>
  );
}
