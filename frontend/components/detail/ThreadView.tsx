import React, { useState, useEffect } from 'react';
import { BASE } from '../../lib/api';

interface Message {
  sender: string;
  timestamp: string;
  subject: string;
  body: string;
}

interface ThreadViewProps {
  emailId: string;
}

export function ThreadView({ emailId }: ThreadViewProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadThread() {
      setLoading(true);
      try {
        const res = await fetch(`${BASE}/api/thread/${emailId}`);
        if (res.ok) {
          const data = await res.json();
          setMessages(data || []);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    loadThread();
  }, [emailId]);

  if (loading) {
    return (
      <div className="py-4 text-center text-xs text-[var(--text-muted)] font-medium">
        Loading thread timeline...
      </div>
    );
  }

  if (messages.length === 0) return null;

  return (
    <div className="mt-6 border-t border-[var(--border)] pt-6 text-left" id="thread-view">
      <h4 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider mb-4 flex items-center gap-1.5">
        <svg
          className="w-4 h-4 text-[var(--accent-primary)]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
        Thread History
      </h4>

      <div className="relative border-l border-[var(--border)] pl-4 ml-2 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className="relative">
            {/* Dot marker */}
            <div className="absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full bg-[var(--accent-primary)] border-2 border-[var(--bg-base)]"></div>
            
            <div className="text-xs">
              <div className="flex items-center justify-between gap-2 text-[var(--text-muted)] font-medium mb-1">
                <span>{msg.sender}</span>
                <span className="font-mono text-[10px]">
                  {new Date(msg.timestamp).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
              <div className="p-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-lg">
                <h5 className="font-semibold text-[var(--text-primary)] mb-1">{msg.subject}</h5>
                <p className="text-[var(--text-muted)] leading-relaxed">{msg.body}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
