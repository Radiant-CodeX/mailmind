import React from 'react';
import { AxisScore } from '../../lib/types';

interface AxisScoreCardProps {
  score: AxisScore;
}

export function AxisScoreCard({ score }: AxisScoreCardProps) {
  const formatAxisName = (name: string) => {
    return name.charAt(0).toUpperCase() + name.slice(1);
  };

  const pct = Math.round(score.raw_score * 100);

  const getBarColor = (name: string) => {
    switch (name.toLowerCase()) {
      case 'deadline':
        return 'bg-red-500';
      case 'authority':
        return 'bg-sky-500';
      case 'sentiment':
        return 'bg-pink-500';
      case 'decay':
        return 'bg-amber-500';
      case 'action':
        return 'bg-emerald-500';
      default:
        return 'bg-slate-500';
    }
  };

  return (
    <div className="p-3 bg-base-200 border border-base-300 rounded-lg text-left" id={`axis-card-${score.axis}`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-bold text-base-content">
          {formatAxisName(score.axis)}
        </span>
        <span className="text-xs font-mono font-bold text-base-content">
          {pct}%
        </span>
      </div>

      <div className="w-full h-1.5 bg-base-300 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getBarColor(score.axis)}`}
          style={{ width: `${pct}%` }}
        ></div>
      </div>

      <p className="text-[10px] text-base-content/60 leading-tight">
        {score.explanation || 'No detail available'}
      </p>
    </div>
  );
}
