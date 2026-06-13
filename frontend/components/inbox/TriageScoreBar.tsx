import React from 'react';

interface TriageScoreBarProps {
  score: number;
}

export function TriageScoreBar({ score }: TriageScoreBarProps) {
  // Determine color transition based on score
  const getColorClass = (val: number) => {
    if (val >= 75) return 'bg-error';
    if (val >= 50) return 'bg-orange-500';
    if (val >= 25) return 'bg-warning';
    return 'bg-success';
  };

  const getTrackShadow = (val: number) => {
    if (val >= 75) return 'shadow-[0_0_10px_rgba(239,68,68,0.2)]';
    if (val >= 50) return 'shadow-[0_0_10px_rgba(249,115,22,0.2)]';
    if (val >= 25) return 'shadow-[0_0_10px_rgba(245,158,11,0.2)]';
    return 'shadow-[0_0_10px_rgba(16,185,129,0.2)]';
  };

  const clampedScore = Math.max(0, Math.min(100, score));

  return (
    <div className="w-full flex items-center gap-2" id="triage-score-bar">
      <div className="flex-1 h-1.5 rounded-full bg-base-200 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${getColorClass(clampedScore)} ${getTrackShadow(clampedScore)}`}
          style={{ width: `${clampedScore}%` }}
        ></div>
      </div>
      <span className="text-xs font-mono font-bold text-base-content shrink-0 min-w-8 text-right">
        {Math.round(clampedScore)}
      </span>
    </div>
  );
}
