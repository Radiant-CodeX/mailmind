'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import Link from 'next/link';
import gsap from 'gsap';
import { Flip } from 'gsap/Flip';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import {
  ArrowDown,
  CalendarClock,
  Check,
  CircleCheck,
  EyeOff,
  KeyRound,
  ListChecks,
  Minus,
  PenLine,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { LogoGlyph } from '../shared/LogoGlyph';
import { WaitlistForm } from './WaitlistForm';
import './landing.css';

gsap.registerPlugin(Flip, ScrollTrigger);

/* ───────────────────────── content ───────────────────────── */

type Mail = { id: string; from: string; subj: string; time: string; key?: string };

const HERO_MAIL: Mail[] = [
  { id: 'a', from: 'Weekend Deals', subj: 'Last chance: 60% off everything', time: '9:41' },
  { id: 'b', from: 'Career Centre', subj: 'Placement drive — registration closes tonight', time: '9:30', key: 'Hard deadline, today at 11:59 pm' },
  { id: 'c', from: 'Design Club', subj: 'Newsletter #42: what we made this month', time: '9:12' },
  { id: 'd', from: 'LinkedIn', subj: 'You appeared in 14 searches this week', time: '8:58' },
  { id: 'e', from: 'Priya Raman', subj: 'Re: report — you said you’d send it Friday', time: '8:40', key: 'Your promise. Added to tasks for Friday' },
  { id: 'f', from: 'Food Court', subj: 'Menu for the week', time: '8:15' },
  { id: 'g', from: 'Notion', subj: 'Your weekly digest', time: '7:52' },
  { id: 'h', from: 'Dr. Menon', subj: 'Review moved to 3 pm Thursday', time: '7:30', key: 'Clashes with your 3 pm lab. Reply drafted' },
  { id: 'i', from: 'Spotify', subj: 'Your mix is ready', time: 'Yest.' },
  { id: 'j', from: 'Hackathon Team', subj: 'Anyone up for pizza?', time: 'Yest.' },
];

type Caught = { from: string; when: string; subj: string; act: string; icon: 'deadline' | 'task' | 'draft' | 'calendar' };
type Persona = { title: string; body: string; caught: Caught[]; quiet: string[] };

const PERSONAS: Record<string, Persona> = {
  student: {
    title: 'The deadlines that can’t be undone, first.',
    body: 'A missed placement registration or hall-ticket download doesn’t come with a second chance. MailMind knows which senders on campus matter and which dates are final, and puts them above everything else.',
    caught: [
      { from: 'Career Development Centre', when: 'Today', subj: 'Drive registration closes at 11:59 pm', act: 'Flagged as a hard deadline', icon: 'deadline' },
      { from: 'Controller of Examinations', when: 'Mon', subj: 'Hall tickets are now available', act: 'Reminder set before exams begin', icon: 'calendar' },
      { from: 'Accounts Office', when: 'Fri', subj: 'Semester fee due this Friday', act: 'Added to your tasks for Friday', icon: 'task' },
    ],
    quiet: ['Club newsletters and event spam', 'Sale mail and app digests', 'Reply-all threads you’re only cc’d on'],
  },
  faculty: {
    title: 'Students and your department, without the noise.',
    body: 'Requests from students, your HOD and the exam cell rise to the top. Routine replies are drafted in your voice, ready for you to read, tweak and send.',
    caught: [
      { from: 'Head of Department', when: 'Mon', subj: 'Course file submission due Monday', act: 'Added to your tasks for Monday', icon: 'task' },
      { from: 'A student in your section', when: 'Today', subj: 'Request: extension on assignment 3', act: 'Reply drafted in your voice', icon: 'draft' },
      { from: 'Examination Cell', when: 'Wed', subj: 'Invigilation duty, Wednesday 2 pm', act: 'Clashes with your 2 pm lecture', icon: 'calendar' },
    ],
    quiet: ['Vendor pitches and conference spam', 'Mass circulars that need no action', 'Automated portal notifications'],
  },
  staff: {
    title: 'Circulars, approvals and requests that keep moving.',
    body: 'Administrative mail runs on handoffs. MailMind picks out the circulars that need action, the approvals waiting on you and the bookings that collide.',
    caught: [
      { from: 'Registrar’s Office', when: 'Today', subj: 'Circular: action needed by the 15th', act: 'Deadline pulled into your tasks', icon: 'deadline' },
      { from: 'Purchase Committee', when: 'Today', subj: 'Approval needed: lab equipment order', act: 'Reply drafted for your review', icon: 'draft' },
      { from: 'Events Team', when: 'Sat', subj: 'Auditorium booking for Saturday', act: 'Conflicts with an existing booking', icon: 'calendar' },
    ],
    quiet: ['FYI-only circulars', 'Newsletters and vendor mail', 'Notifications from internal tools'],
  },
  professional: {
    title: 'Clients and commitments before newsletters.',
    body: 'Freelancers, founders and anyone whose work lives in email. MailMind surfaces the people waiting on you, remembers what you promised and warns you before you double-book.',
    caught: [
      { from: 'Client', when: 'Today', subj: 'Can you confirm Thursday’s review?', act: 'Reply drafted in your voice', icon: 'draft' },
      { from: 'You, in a thread', when: 'Fri', subj: '“I’ll send the revised deck by Friday”', act: 'Tracked as a task for Friday', icon: 'task' },
      { from: 'Partner team', when: 'Thu', subj: 'Invite: sync at 4 pm Thursday', act: 'Overlaps with a call you already have', icon: 'calendar' },
    ],
    quiet: ['Promotions and product updates', 'Social notifications', 'Receipts, filed where you can find them'],
  },
};

const CAMPUS_ROLES = [
  { id: 'student', label: 'Students' },
  { id: 'faculty', label: 'Faculty' },
  { id: 'staff', label: 'Staff' },
] as const;

const FAQ = [
  {
    q: 'Will MailMind ever send an email on its own?',
    a: 'No. MailMind drafts, and you decide. Every reply waits for you to read it, edit it if you like, and press send yourself.',
  },
  {
    q: 'Which email accounts does it work with?',
    a: 'Gmail today, including Google Workspace accounts on campus or at work. You can connect more than one account, and each keeps its own voice and history.',
  },
  {
    q: 'Do I need my own AI key?',
    a: 'No. Sorting, deadlines and tasks work without one. If you want AI-written drafts, you can bring a key from OpenRouter, Groq, Google Gemini or OpenAI, or run a local model with Ollama.',
  },
  {
    q: 'What does the AI actually see?',
    a: 'Only the email text it needs, with names, phone numbers, email addresses and similar details replaced by placeholders first. The real values are restored on your screen, never sent to the model.',
  },
  {
    q: 'How does it learn to write like me?',
    a: 'It reads your sent mail to learn how you write: how formal you are, how long your replies run, how you open and sign off. That profile belongs to that account alone.',
  },
  {
    q: 'Who can join right now?',
    a: 'MailMind is in a private beta. Join the waitlist and we’ll email you when your spot opens.',
  },
];

/* ───────────────────────── pieces ───────────────────────── */

function CaughtIcon({ kind }: { kind: Caught['icon'] }) {
  if (kind === 'task') return <ListChecks aria-hidden />;
  if (kind === 'draft') return <PenLine aria-hidden />;
  if (kind === 'calendar') return <CalendarClock aria-hidden />;
  return <Sparkles aria-hidden />;
}

function HeroInbox() {
  const ref = useRef<HTMLDivElement>(null);
  const flipState = useRef<Flip.FlipState | null>(null);
  const [sorted, setSorted] = useState(false);

  const list = sorted
    ? [...HERO_MAIL.filter((m) => m.key), ...HERO_MAIL.filter((m) => !m.key)]
    : HERO_MAIL;

  function toggle(next: boolean) {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (ref.current && !reduce) flipState.current = Flip.getState(ref.current.querySelectorAll('li'));
    setSorted(next);
  }

  useLayoutEffect(() => {
    if (!flipState.current) return;
    Flip.from(flipState.current, { duration: 0.9, ease: 'expo.out', stagger: 0.03 });
    flipState.current = null;
  }, [sorted]);

  // sort once, a beat after the inbox comes into view
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let timer: number | undefined;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          timer = window.setTimeout(() => toggle(true), 1100);
          io.disconnect();
        }
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      window.clearTimeout(timer);
    };
  }, []);

  return (
    <div ref={ref} className="lp-inbox" data-sorted={sorted} aria-label="Example inbox being sorted by MailMind">
      <div className="lp-inbox-bar">
        <strong>Inbox</strong>
        <button type="button" className="lp-replay" onClick={() => toggle(!sorted)}>
          <RotateCcw aria-hidden />
          {sorted ? 'Show unsorted' : 'Sort it'}
        </button>
      </div>
      <ul className="lp-mail">
        {list.map((m) => (
          <li key={m.id} data-flip-id={m.id} data-key={Boolean(m.key)} data-hide-sm={['g', 'i', 'j'].includes(m.id)}>
            <span className="dot" aria-hidden />
            <span className="from">{m.from}</span>
            <span className="subj">{m.subj}</span>
            <span className="time">{m.time}</span>
            {m.key && <span className="why">{m.key}</span>}
          </li>
        ))}
      </ul>
      <div className="lp-inbox-foot" aria-live="polite">
        {sorted ? `3 need you today. The rest are filed quietly, nothing deleted.` : '10 new messages'}
      </div>
    </div>
  );
}

function Audience() {
  const [track, setTrack] = useState<'campus' | 'professional'>('campus');
  const [role, setRole] = useState<(typeof CAMPUS_ROLES)[number]['id']>('student');
  const [tick, setTick] = useState(0);
  const persona = PERSONAS[track === 'campus' ? role : 'professional'];

  const pick = (fn: () => void) => {
    fn();
    setTick((t) => t + 1);
  };

  return (
    <section id="who" className="lp-section">
      <div className="lp-wrap">
        <div className="lp-section-head">
          <h2 className="lp-h2">
            Different inboxes. <em>Different things that matter.</em>
          </h2>
          <p className="lp-body">
            What’s urgent for a final-year student isn’t what’s urgent for a freelancer. Pick yours to see what
            MailMind brings forward, and what it quietly moves out of the way.
          </p>
        </div>

        <div role="tablist" aria-label="Who you are" className="lp-tabs">
          {(['campus', 'professional'] as const).map((t) => (
            <button
              key={t}
              role="tab"
              type="button"
              aria-selected={track === t}
              aria-controls="persona-panel"
              className="lp-tab"
              onClick={() => pick(() => setTrack(t))}
            >
              {t === 'campus' ? 'On campus' : 'At work'}
            </button>
          ))}
        </div>

        {track === 'campus' && (
          <div role="tablist" aria-label="Campus role" className="lp-subtabs">
            {CAMPUS_ROLES.map((r) => (
              <button
                key={r.id}
                role="tab"
                type="button"
                aria-selected={role === r.id}
                aria-controls="persona-panel"
                className="lp-subtab"
                onClick={() => pick(() => setRole(r.id))}
              >
                {r.label}
              </button>
            ))}
          </div>
        )}

        <div
          id="persona-panel"
          role="tabpanel"
          key={tick}
          data-entering={tick > 0}
          className="lp-persona lp-persona-panel"
        >
          <div className="lp-persona-copy">
            <h3 className="lp-h3">{persona.title}</h3>
            <p className="lp-body">{persona.body}</p>
            <p className="lp-small" style={{ marginTop: '0.75rem' }}>
              Moved out of your way
            </p>
            <ul className="lp-quiet-list">
              {persona.quiet.map((q) => (
                <li key={q}>
                  <Minus aria-hidden />
                  {q}
                </li>
              ))}
            </ul>
          </div>
          <ul className="lp-caught" aria-label="What MailMind brings forward">
            {persona.caught.map((c) => (
              <li key={c.subj}>
                <div className="meta">
                  <b>{c.from}</b>
                  <span>{c.when}</span>
                </div>
                <div className="subj">{c.subj}</div>
                <div className="act">
                  <CaughtIcon kind={c.icon} />
                  {c.act}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────── page ───────────────────────── */

export function Landing() {
  const rootRef = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    // globals.css locks body scroll for the dashboard; the landing needs window scroll
    const { overflow, height } = document.body.style;
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      document.body.style.overflow = overflow;
      document.body.style.height = height;
    };
  }, []);

  // Quiet entrances. Content is visible by default; motion is only layered on.
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const ctx = gsap.context(() => {
      gsap.from('[data-hero-in]', {
        y: 18,
        opacity: 0,
        filter: 'blur(6px)',
        duration: 1.1,
        ease: 'expo.out',
        stagger: 0.09,
        clearProps: 'filter',
      });
      gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach((el) => {
        gsap.from(el, {
          y: 24,
          opacity: 0,
          duration: 1,
          ease: 'expo.out',
          scrollTrigger: { trigger: el, start: 'top 88%', once: true },
        });
      });
    }, rootRef);
    return () => ctx.revert();
  }, []);

  return (
    <div ref={rootRef} className="lp">
      <a href="#main" className="sr-only focus:not-sr-only">
        Skip to content
      </a>

      <header className="lp-nav" data-scrolled={scrolled}>
        <div className="lp-wrap lp-nav-inner">
          <Link href="/" className="lp-brand" aria-label="MailMind home">
            <LogoGlyph />
            MailMind
          </Link>
          <nav className="lp-nav-links" aria-label="Sections">
            <a href="#how">How it works</a>
            <a href="#who">Who it’s for</a>
            <a href="#privacy">Privacy</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className="lp-nav-actions">
            <Link href="/login" className="lp-signin">
              Sign in
            </Link>
            <a href="#waitlist" className="lp-btn lp-btn-sm">
              Join waitlist
            </a>
          </div>
        </div>
      </header>

      <main id="main">
        {/* hero */}
        <div className="lp-wrap lp-hero">
          <div className="lp-hero-copy">
            <h1 className="lp-display" data-hero-in>
              Read what matters. <em>The rest can wait.</em>
            </h1>
            <p className="lp-lede" data-hero-in>
              MailMind sorts your Gmail by what actually needs you, tracks what you promised, and drafts replies
              in your voice.
            </p>
            <div data-hero-in>
              <WaitlistForm variant="inline" />
            </div>
          </div>
          <div data-hero-in>
            <HeroInbox />
          </div>
        </div>

        {/* how it works */}
        <section id="how" className="lp-section">
          <div className="lp-wrap">
            <div className="lp-section-head" data-reveal>
              <h2 className="lp-h2">
                Feels like your inbox. <em>Thinks like an assistant.</em>
              </h2>
              <p className="lp-body">
                There’s no new way of working to learn. MailMind sits on top of the Gmail you already use and
                does the reading-ahead for you.
              </p>
            </div>
            <ol className="lp-steps" data-reveal>
              <li className="lp-step">
                <span className="lp-step-n">1</span>
                <h3 className="lp-h3">Connect Gmail</h3>
                <p className="lp-body">
                  Sign in with Google. MailMind reads your recent mail and your sent folder to learn what matters
                  to you and how you write.
                </p>
              </li>
              <li className="lp-step">
                <span className="lp-step-n">2</span>
                <h3 className="lp-h3">It sorts and prepares</h3>
                <p className="lp-body">
                  New mail is ranked by deadline, sender and what’s being asked of you. Promises become tasks,
                  clashes are flagged, and replies are drafted.
                </p>
              </li>
              <li className="lp-step">
                <span className="lp-step-n">3</span>
                <h3 className="lp-h3">You decide</h3>
                <p className="lp-body">
                  Read the few that need you, edit a draft if you want, and press send. Nothing leaves your
                  account without you.
                </p>
              </li>
            </ol>
          </div>
        </section>

        <Audience />

        {/* voice */}
        <section className="lp-section">
          <div className="lp-wrap lp-feature">
            <div className="lp-feature-copy" data-reveal>
              <h2 className="lp-h2">
                Replies that sound like you. <em>Not like a bot.</em>
              </h2>
              <p className="lp-body">
                MailMind learns your voice from the mail you’ve already sent: how formal you are, how long you
                write, how you sign off. It also remembers how you handled similar emails before, so drafts start
                from your own past decisions.
              </p>
            </div>
            <div className="lp-paper" data-reveal>
              <div className="lp-paper-label">
                <span>From Dr. Menon</span>
                <span>7:30 am</span>
              </div>
              <p className="lp-quote">
                Hi, we need to move Thursday’s project review to 3 pm. Does that still work for your team?
              </p>
              <div className="lp-divider" />
              <div className="lp-paper-label">
                <span>Draft in your voice</span>
                <span>Waiting for you</span>
              </div>
              <p className="lp-draft">
                {'Hi Dr. Menon,\n\n3 pm clashes with our lab slot, unfortunately. Would 4:30 on Thursday or any time Friday morning work instead?\n\nThanks,\nArjun'}
              </p>
              <div className="lp-traits" aria-label="What MailMind matched">
                <span className="lp-trait">Short replies</span>
                <span className="lp-trait">Polite, not formal</span>
                <span className="lp-trait">Signs off “Thanks”</span>
                <span className="lp-trait">Checked your calendar</span>
              </div>
              <div className="lp-draft-actions">
                <span className="lp-btn lp-btn-sm" aria-hidden>
                  Review and send
                </span>
                <span className="lp-btn lp-btn-sm lp-btn-quiet" aria-hidden>
                  Edit
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* commitments */}
        <section className="lp-section">
          <div className="lp-wrap lp-feature" data-flip="true">
            <div className="lp-feature-copy" data-reveal>
              <h2 className="lp-h2">
                What you promise <em>stays promised.</em>
              </h2>
              <p className="lp-body">
                “I’ll send it by Friday” is easy to type and easy to forget. MailMind catches commitments in the
                threads you write and read, turns them into tasks with real dates, and checks them against your
                calendar.
              </p>
            </div>
            <div className="lp-paper" data-reveal>
              <div className="lp-paper-label">
                <span>You, replying to Priya</span>
                <span>Tue</span>
              </div>
              <p className="lp-quote">
                Thanks for the notes! <span className="lp-mark">I’ll send the final report by Friday</span>, and
                let’s catch up after that.
              </p>
              <div className="lp-arrow">
                <ArrowDown aria-hidden />
                Added to your tasks
              </div>
              <div className="lp-task">
                <span className="box" aria-hidden />
                <span className="t">Send the final report to Priya</span>
                <span className="d">Due Fri</span>
              </div>
            </div>
          </div>
        </section>

        {/* privacy */}
        <section id="privacy" className="lp-section">
          <div className="lp-wrap lp-privacy">
            <div className="lp-feature-copy" data-reveal>
              <h2 className="lp-h2">
                Your inbox is personal. <em>We treat it that way.</em>
              </h2>
              <p className="lp-body">
                Before any AI model reads an email, the personal details in it are swapped for placeholders. This
                is what the model sees:
              </p>
              <div className="lp-paper lp-redact" aria-label="Example of a masked email">
                <p>
                  Hi, this is <span className="tok">[PERSON_1]</span>. Please call me on{' '}
                  <span className="tok">[PHONE_1]</span> or write to <span className="tok">[EMAIL_1]</span> before
                  the fee deadline.
                </p>
              </div>
            </div>
            <ul className="lp-promises" data-reveal>
              <li>
                <EyeOff aria-hidden />
                <div>
                  <b>Personal details are masked first</b>
                  <p>Names, phone numbers and addresses are replaced before any model sees the text.</p>
                </div>
              </li>
              <li>
                <CircleCheck aria-hidden />
                <div>
                  <b>Nothing sends without you</b>
                  <p>Every draft waits for your approval. MailMind never replies on its own.</p>
                </div>
              </li>
              <li>
                <KeyRound aria-hidden />
                <div>
                  <b>Bring your own AI, or none at all</b>
                  <p>Use your own key or a local model. Sorting and tasks work even with AI switched off.</p>
                </div>
              </li>
              <li>
                <ShieldCheck aria-hidden />
                <div>
                  <b>Each account stays separate</b>
                  <p>Connect several inboxes. Each keeps its own voice and history, never mixed.</p>
                </div>
              </li>
            </ul>
          </div>
        </section>

        {/* faq */}
        <section id="faq" className="lp-section">
          <div className="lp-wrap lp-faq">
            <h2 className="lp-h2" data-reveal>
              Questions, answered plainly.
            </h2>
            <div data-reveal>
              {FAQ.map((f) => (
                <details key={f.q}>
                  <summary>
                    {f.q}
                    <Plus aria-hidden />
                  </summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* closing waitlist */}
        <section id="waitlist" className="lp-section">
          <div className="lp-wrap lp-close">
            <div className="lp-feature-copy" data-reveal>
              <h2 className="lp-h2">
                A calmer inbox, <em>starting this week.</em>
              </h2>
              <p className="lp-body">
                MailMind is opening to small groups at a time. Tell us a little about your inbox and we’ll invite
                you as soon as there’s room.
              </p>
              <ul className="lp-quiet-list">
                <li>
                  <Check aria-hidden />
                  Works with Gmail and Google Workspace
                </li>
                <li>
                  <Check aria-hidden />
                  No AI key needed to get started
                </li>
                <li>
                  <Check aria-hidden />
                  Disconnect your account any time
                </li>
              </ul>
            </div>
            <div className="lp-close-form" data-reveal>
              <WaitlistForm />
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-wrap lp-footer-inner">
          <Link href="/" className="lp-brand" aria-label="MailMind home">
            <LogoGlyph />
            MailMind
          </Link>
          <nav aria-label="Legal">
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
            <Link href="/login">Sign in</Link>
          </nav>
          <span>© {new Date().getFullYear()} Radiants</span>
        </div>
      </footer>
    </div>
  );
}
