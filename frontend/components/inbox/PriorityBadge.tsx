import React from 'react';
import { Priority } from '../../lib/types';

interface PriorityBadgeProps {
  priority: Priority;
}

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  const colors = {
    CRITICAL: 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20 font-extrabold shadow-sm shadow-red-500/5',
    HIGH: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border border-orange-500/20 font-bold shadow-sm',
    MEDIUM: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-semibold',
    LOW: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20 font-medium',
  };

  return (
    <span
      className={`px-2 py-0.5 text-[10px] font-bold rounded tracking-wider uppercase inline-flex items-center justify-center ${
        colors[priority] || colors.LOW
      }`}
      id={`priority-badge-${priority.toLowerCase()}`}
    >
      {priority}
    </span>
  );
}
