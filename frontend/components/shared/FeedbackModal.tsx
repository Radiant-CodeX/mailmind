'use client';

import React, { useState } from 'react';
import { submitFeedback } from '../../lib/api';

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  userRole?: string | null;
}

const CATEGORIES = [
  { id: 'Bug', label: 'Bug Report', emoji: '🐛' },
  { id: 'Feature', label: 'Feature Request', emoji: '✨' },
  { id: 'General', label: 'General Feedback', emoji: '💬' },
  { id: 'Other', label: 'Other', emoji: '📝' },
];

export function FeedbackModal({ isOpen, onClose, userRole }: FeedbackModalProps) {
  const [rating, setRating] = useState(0);
  const [hoveredRating, setHoveredRating] = useState(0);
  const [category, setCategory] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const reset = () => {
    setRating(0);
    setHoveredRating(0);
    setCategory('');
    setMessage('');
    setLoading(false);
    setSuccess(false);
    setError('');
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    if (!rating || !category || !message.trim()) {
      setError('Please fill in all fields.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await submitFeedback({
        rating,
        category,
        message: message.trim(),
        role: userRole,
      });
      setSuccess(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
    >
      <div className="bg-base-100 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden animate-fade-in border border-base-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-base-300">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <div>
              <h2 className="font-bold text-base-content text-sm">Send Feedback</h2>
              <p className="text-[10px] text-base-content/50">Help us make MailMind better</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="w-7 h-7 rounded-lg hover:bg-base-200 flex items-center justify-center text-base-content/40 hover:text-base-content transition-colors cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {success ? (
          /* Success state */
          <div className="px-6 py-10 text-center">
            <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4 animate-fade-in">
              <svg className="w-8 h-8 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="font-bold text-base-content text-lg mb-1">Thank you!</h3>
            <p className="text-base-content/60 text-sm mb-6">Your feedback helps us build a better MailMind.</p>
            <button
              onClick={handleClose}
              className="px-6 py-2 bg-primary text-base-100 font-bold rounded-lg text-sm hover:opacity-90 transition-opacity cursor-pointer"
            >
              Close
            </button>
          </div>
        ) : (
          <div className="px-6 py-5 space-y-5">
            {/* Star rating */}
            <div>
              <p className="text-xs font-semibold text-base-content/70 mb-2">How would you rate MailMind?</p>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((star) => {
                  const filled = star <= (hoveredRating || rating);
                  return (
                    <button
                      key={star}
                      onMouseEnter={() => setHoveredRating(star)}
                      onMouseLeave={() => setHoveredRating(0)}
                      onClick={() => setRating(star)}
                      className="cursor-pointer transition-transform hover:scale-110 active:scale-95"
                      aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
                    >
                      <svg
                        className={`w-8 h-8 transition-colors duration-100 ${
                          filled ? 'text-warning' : 'text-base-content/20'
                        }`}
                        fill={filled ? 'currentColor' : 'none'}
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.907c.961 0 1.36 1.245.588 1.81l-3.97 2.883a1 1 0 00-.364 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.971-2.883a1 1 0 00-1.18 0l-3.97 2.883c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.364-1.118l-3.97-2.883c-.772-.565-.373-1.81.588-1.81h4.906a1 1 0 00.951-.69l1.519-4.674z"
                        />
                      </svg>
                    </button>
                  );
                })}
                {(hoveredRating || rating) > 0 && (
                  <span className="ml-2 text-xs text-base-content/50 self-center">
                    {['', 'Poor', 'Fair', 'Good', 'Great', 'Excellent!'][(hoveredRating || rating)]}
                  </span>
                )}
              </div>
            </div>

            {/* Category */}
            <div>
              <p className="text-xs font-semibold text-base-content/70 mb-2">What type of feedback?</p>
              <div className="grid grid-cols-2 gap-2">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setCategory(cat.id)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-all cursor-pointer ${
                      category === cat.id
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-base-300 text-base-content/60 hover:border-base-content/30 hover:text-base-content'
                    }`}
                  >
                    <span>{cat.emoji}</span>
                    <span>{cat.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Message */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <p className="text-xs font-semibold text-base-content/70">Your message</p>
                <span className={`text-[10px] ${message.length > 1800 ? 'text-error' : 'text-base-content/40'}`}>
                  {message.length}/2000
                </span>
              </div>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value.slice(0, 2000))}
                placeholder="Tell us what's on your mind..."
                rows={4}
                className="w-full bg-base-200 rounded-lg px-3 py-2.5 text-sm text-base-content placeholder:text-base-content/30 resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all"
              />
            </div>

            {error && (
              <p className="text-error text-xs flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {error}
              </p>
            )}

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full py-2.5 bg-primary hover:opacity-90 disabled:opacity-50 text-base-100 font-bold rounded-lg text-sm transition-all cursor-pointer flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-base-100/30 border-t-base-100 rounded-full animate-spin" />
                  Sending...
                </>
              ) : (
                'Send Feedback'
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
