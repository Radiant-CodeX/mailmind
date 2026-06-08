import React from 'react';
import { TriageResult, CommitmentItem, CalendarEvent } from '../../lib/types';

interface PipelineMetric {
  node: string;
  duration_ms: number;
  status: 'completed' | 'running' | 'pending' | 'error';
  timestamp?: string;
}

interface PipelineVisualizationProps {
  metrics?: PipelineMetric[];
  triageResult?: TriageResult | null;
  commitmentCount?: number;
  conflictCount?: number;
  draftGenerated?: boolean;
  approved?: boolean;
  isLoading?: boolean;
  error?: string | null;
}

/**
 * PipelineVisualization
 *
 * Displays the MailMind 6-node pipeline with real-time execution metrics.
 * Shows node progression, timing per stage, and key results at a glance.
 *
 * Perfect for live demos and stakeholder presentations.
 */
export function PipelineVisualization({
  metrics = [],
  triageResult,
  commitmentCount = 0,
  conflictCount = 0,
  draftGenerated = false,
  approved = false,
  isLoading = false,
  error = null,
}: PipelineVisualizationProps) {
  // Define the 6 nodes in order
  const nodes = [
    {
      id: 'ingest',
      label: 'INGEST',
      description: 'PII Masking',
      color: 'from-blue-500 to-blue-600',
      icon: '🛡️',
    },
    {
      id: 'triage',
      label: 'TRIAGE',
      description: '5-Axis Scoring',
      color: 'from-purple-500 to-purple-600',
      icon: '⚖️',
    },
    {
      id: 'commitment',
      label: 'COMMITMENT',
      description: 'Extract Tasks',
      color: 'from-orange-500 to-orange-600',
      icon: '✓',
    },
    {
      id: 'calendar',
      label: 'CALENDAR',
      description: 'Conflict Check',
      color: 'from-red-500 to-red-600',
      icon: '📅',
    },
    {
      id: 'rag',
      label: 'RAG',
      description: 'Draft Generation',
      color: 'from-emerald-500 to-emerald-600',
      icon: '✍️',
    },
    {
      id: 'gate',
      label: 'GATE',
      description: 'Approval Checkpoint',
      color: 'from-pink-500 to-pink-600',
      icon: approved ? '✅' : '🔴',
    },
  ];

  // Get status for each node
  const getNodeStatus = (nodeId: string) => {
    const metric = metrics.find((m) => m.node === nodeId);
    if (metric) {
      return metric.status;
    }
    // Check if this node should be running/completed based on triage
    if (nodeId === 'triage' && triageResult) return 'completed';
    if (nodeId === 'commitment' && commitmentCount > 0) return 'completed';
    if (nodeId === 'calendar' && conflictCount >= 0) return 'completed';
    if (nodeId === 'rag' && draftGenerated) return 'completed';
    if (nodeId === 'gate') return approved ? 'completed' : 'pending';
    if (isLoading && nodeId === 'ingest') return 'running';
    return 'pending';
  };

  const getDuration = (nodeId: string) => {
    const metric = metrics.find((m) => m.node === nodeId);
    return metric?.duration_ms ?? null;
  };

  // Calculate total duration
  const totalDuration = metrics.reduce((sum, m) => sum + m.duration_ms, 0);
  const slaTarget = 1500; // 1.5s for triage
  const slaMet = totalDuration <= slaTarget;

  return (
    <div className="space-y-6 p-4 bg-gradient-to-br from-[var(--bg-base)] to-[var(--bg-elevated)] rounded-lg border border-[var(--border-subtle)]">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">
            Pipeline Execution
          </h3>
          {!isLoading && totalDuration > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--text-muted)]">Total</span>
              <span className="font-mono font-bold text-[var(--text-primary)]">
                {totalDuration}ms
              </span>
              <span
                className={`text-[9px] font-black px-2 py-0.5 rounded ${
                  slaMet
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                    : 'bg-orange-500/10 text-orange-600 dark:text-orange-400'
                }`}
              >
                {slaMet ? '✅ SLA MET' : '⚠️ SLA EXCEEDED'}
              </span>
            </div>
          )}
        </div>
        {error && (
          <div className="text-xs text-rose-600 dark:text-rose-400 bg-rose-500/10 px-3 py-2 rounded border border-rose-500/20">
            {error}
          </div>
        )}
      </div>

      {/* Pipeline Flow */}
      <div className="space-y-3">
        {nodes.map((node, index) => {
          const status = getNodeStatus(node.id);
          const duration = getDuration(node.id);
          const isCompleted = status === 'completed';
          const isRunning = status === 'running';
          const isPending = status === 'pending';

          return (
            <div key={node.id} className="space-y-1">
              {/* Node Card */}
              <div
                className={`relative overflow-hidden rounded-lg border transition-all duration-300 ${
                  isCompleted
                    ? `border-emerald-500/50 bg-gradient-to-r ${node.color} text-white shadow-lg`
                    : isRunning
                    ? `border-amber-500/50 bg-gradient-to-r ${node.color} text-white shadow-lg animate-pulse`
                    : `border-[var(--border-subtle)] bg-[var(--bg-elevated)]/50 text-[var(--text-muted)]`
                }`}
              >
                <div className="p-3 flex items-center justify-between">
                  {/* Left: Icon + Label */}
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="text-lg shrink-0">{node.icon}</div>
                    <div className="min-w-0">
                      <div className="font-semibold text-xs uppercase tracking-wider truncate">
                        {node.label}
                      </div>
                      <div className="text-[9px] opacity-75 truncate">
                        {node.description}
                      </div>
                    </div>
                  </div>

                  {/* Right: Timing + Status */}
                  <div className="flex items-center gap-2 shrink-0">
                    {duration && (
                      <span className="font-mono text-xs font-bold">
                        {duration}ms
                      </span>
                    )}
                    <div className="flex-shrink-0">
                      {isCompleted && (
                        <div className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center text-white">
                          ✓
                        </div>
                      )}
                      {isRunning && (
                        <div className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      )}
                      {isPending && (
                        <div className="w-5 h-5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-base)]" />
                      )}
                    </div>
                  </div>
                </div>

                {/* Progress bar */}
                {duration && (
                  <div className="h-1 bg-white/10">
                    <div
                      className="h-full bg-white/40 transition-all duration-500"
                      style={{
                        width: `${Math.min(100, (duration / 100) * 100)}%`,
                      }}
                    />
                  </div>
                )}
              </div>

              {/* Node Details */}
              <div className="ml-6 space-y-1 text-xs text-[var(--text-muted)] opacity-75">
                {node.id === 'ingest' && isCompleted && (
                  <div>└─ Masked PII entities safely</div>
                )}
                {node.id === 'triage' && triageResult && (
                  <>
                    <div>
                      └─ Score: {Math.round(triageResult.composite_score)} | Type:{' '}
                      {triageResult.email_type || 'uncategorised'}
                    </div>
                    <div>
                      └─ Priority: <span className="font-semibold">{triageResult.priority}</span> |
                      Mode: <span className="font-semibold">{triageResult.approval_mode}</span>
                    </div>
                  </>
                )}
                {node.id === 'commitment' && commitmentCount > 0 && (
                  <div>└─ Extracted {commitmentCount} commitment(s)</div>
                )}
                {node.id === 'calendar' && conflictCount > 0 && (
                  <div>└─ {conflictCount} conflict(s) detected</div>
                )}
                {node.id === 'rag' && draftGenerated && (
                  <div>└─ Generated draft reply</div>
                )}
                {node.id === 'gate' && (
                  <div>
                    └─ {approved ? 'Approved by user' : 'Awaiting human approval'}
                  </div>
                )}
              </div>

              {/* Arrow between nodes (except after last) */}
              {index < nodes.length - 1 && (
                <div className="flex justify-center py-1">
                  <div className="text-[var(--text-muted)] opacity-40 text-lg">↓</div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary Footer */}
      {totalDuration > 0 && (
        <div className="p-3 rounded bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-[var(--text-muted)]">Pipeline Status</span>
            <span className="font-semibold text-[var(--text-primary)]">
              {isLoading ? 'Running...' : 'Complete'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-muted)]">Nodes Completed</span>
            <span className="font-semibold text-[var(--text-primary)]">
              {metrics.filter((m) => m.status === 'completed').length} / 6
            </span>
          </div>
          <div className="h-px bg-[var(--border-subtle)]" />
          <div className="flex justify-between">
            <span className="text-[var(--text-muted)]">SLA Target (Triage)</span>
            <span
              className={`font-semibold ${
                slaMet
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-orange-600 dark:text-orange-400'
              }`}
            >
              {totalDuration}ms / {slaTarget}ms {slaMet ? '✅' : '⚠️'}
            </span>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && totalDuration === 0 && !error && (
        <div className="text-center py-8 text-[var(--text-muted)] text-xs opacity-60">
          Select an email to see the pipeline in action
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="text-center py-8">
          <div className="inline-block">
            <div className="w-8 h-8 border-2 border-[var(--border-subtle)] border-t-[var(--text-primary)] rounded-full animate-spin" />
          </div>
          <p className="mt-3 text-xs text-[var(--text-muted)]">
            Processing email through pipeline...
          </p>
        </div>
      )}
    </div>
  );
}
