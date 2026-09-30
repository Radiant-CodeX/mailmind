"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  CircleCheck,
  ExternalLink,
  Eye,
  EyeOff,
  FlaskConical,
  Gauge,
  GraduationCap,
  KeyRound,
  PenLine,
  Search,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import {
  AIProvider,
  AISettingsView,
  AITestResult,
  CampusProfile,
  CampusRole,
  ToneProfile,
  buildToneProfile,
  clearAISettings,
  fetchAIProviders,
  fetchAISettings,
  fetchCampusProfile,
  fetchToneProfile,
  saveAISettings,
  saveCampusProfile,
  testAISettings,
} from "../../lib/api";
import { PrivacyView } from "../privacy/PrivacyView";
import { MetricsView } from "../metrics/MetricsView";
import { EvaluationView } from "../evaluation/EvaluationView";
import { RAGSettingsView } from "../rag/RAGSettingsView";
import { Button } from "./ui";

type Section = "profile" | "ai" | "voice" | "privacy" | "metrics" | "evaluation" | "retrieval";

const SECTIONS: { id: Section; label: string; icon: LucideIcon; group: string }[] = [
  { id: "profile", label: "About you", icon: GraduationCap, group: "You" },
  { id: "ai", label: "AI model", icon: KeyRound, group: "You" },
  { id: "voice", label: "Writing voice", icon: PenLine, group: "You" },
  { id: "privacy", label: "Privacy", icon: ShieldCheck, group: "Trust" },
  { id: "metrics", label: "Performance", icon: Gauge, group: "Under the hood" },
  { id: "evaluation", label: "Accuracy check", icon: FlaskConical, group: "Under the hood" },
  { id: "retrieval", label: "Past-email memory", icon: Search, group: "Under the hood" },
];

/* ─────────────── shared field bits ─────────────── */

function Field({ label, hint, children, htmlFor }: { label: string; hint?: string; children: React.ReactNode; htmlFor?: string }) {
  return (
    <div className="grid gap-1.5">
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-ink">{label}</label>
      {children}
      {hint && <p className="text-[12px] leading-snug text-ink-3">{hint}</p>}
    </div>
  );
}

const INPUT =
  "h-10 w-full rounded-xl border border-rule bg-surface px-3.5 text-[13.5px] text-ink placeholder:text-ink-3 focus:border-cobalt focus:outline-none disabled:opacity-60";

function Panel({ title, intro, children }: { title: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[40rem] px-5 pb-16 pt-6 md:px-8">
      <h2 className="text-[20px] font-semibold tracking-tight text-ink">{title}</h2>
      {intro && <p className="mt-1.5 max-w-[60ch] text-[13.5px] leading-relaxed text-ink-2">{intro}</p>}
      <div className="mt-6 grid gap-6">{children}</div>
    </div>
  );
}

function Notice({ tone, children }: { tone: "ok" | "error" | "info"; children: React.ReactNode }) {
  const cls = tone === "ok" ? "bg-ok-soft text-ok" : tone === "error" ? "bg-urgent-soft text-urgent" : "bg-cobalt-soft text-ink";
  return <p role={tone === "error" ? "alert" : "status"} className={`rounded-xl px-3.5 py-2.5 text-[13px] ${cls}`}>{children}</p>;
}

/* ─────────────── About you ─────────────── */

function ProfilePanel() {
  const [profile, setProfile] = useState<CampusProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    fetchCampusProfile().then(setProfile).catch(() => setProfile({ role: "student", department: null, year_of_study: null }));
  }, []);

  if (!profile) return <Panel title="About you"><span className="mm-skeleton block h-40" /></Panel>;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    try {
      setProfile(await saveCampusProfile(profile));
      setMsg({ tone: "ok", text: "Saved. New mail is sorted with this in mind." });
    } catch (err) {
      setMsg({ tone: "error", text: err instanceof Error ? err.message : "Could not save" });
    } finally {
      setSaving(false);
    }
  };

  const roles: { id: CampusRole; label: string; hint: string }[] = [
    { id: "student", label: "Student", hint: "Placements, exams, fees and faculty requests come first" },
    { id: "faculty", label: "Faculty", hint: "Student requests, HOD and exam-cell duties come first" },
    { id: "staff", label: "Staff", hint: "Circulars, approvals and bookings come first" },
  ];

  return (
    <Panel title="About you" intro="What counts as urgent depends on who you are on campus. This tunes how MailMind ranks your mail and how it writes on your behalf.">
      <form onSubmit={save} className="grid gap-6">
        <fieldset className="grid gap-2">
          <legend className="mb-1.5 text-[13px] font-medium text-ink">I am</legend>
          {roles.map((r) => (
            <label
              key={r.id}
              className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3.5 py-3 transition-colors ${
                profile.role === r.id ? "border-cobalt bg-cobalt-soft" : "border-rule bg-surface hover:bg-hover"
              }`}
            >
              <input
                type="radio"
                name="role"
                value={r.id}
                checked={profile.role === r.id}
                onChange={() => setProfile({ ...profile, role: r.id })}
                className="mt-1 accent-[var(--mm-accent)]"
              />
              <span>
                <span className="block text-[13.5px] font-medium text-ink">{r.label}</span>
                <span className="block text-[12.5px] text-ink-3">{r.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Department" htmlFor="dept" hint="For example CSE, ECE or Mechanical.">
            <input id="dept" className={INPUT} value={profile.department ?? ""} maxLength={128}
              onChange={(e) => setProfile({ ...profile, department: e.target.value || null })} placeholder="CSE" />
          </Field>
          {profile.role === "student" && (
            <Field label="Year of study" htmlFor="year">
              <select id="year" className={INPUT} value={profile.year_of_study ?? ""}
                onChange={(e) => setProfile({ ...profile, year_of_study: e.target.value ? Number(e.target.value) : null })}>
                <option value="">Not set</option>
                {[1, 2, 3, 4, 5].map((y) => <option key={y} value={y}>Year {y}</option>)}
              </select>
            </Field>
          )}
        </div>
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        <div><Button type="submit" variant="primary" loading={saving}>Save</Button></div>
      </form>
    </Panel>
  );
}

/* ─────────────── AI model (bring your own key) ─────────────── */

function AIPanel() {
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [view, setView] = useState<AISettingsView | null>(null);
  const [provider, setProvider] = useState("openrouter");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [busy, setBusy] = useState<"test" | "save" | "remove" | null>(null);
  const [result, setResult] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    Promise.all([fetchAIProviders(), fetchAISettings()])
      .then(([p, v]) => {
        setProviders(p);
        setView(v);
        if (v.own) {
          setProvider(v.own.provider);
          setChatModel(v.own.chat_model ?? "");
          if (v.own.provider === "custom") setBaseUrl(v.own.base_url);
        }
      })
      .catch((e) => setResult({ tone: "error", text: e instanceof Error ? e.message : "Could not load AI settings" }));
  }, []);

  const preset = useMemo(() => providers.find((p) => p.id === provider), [providers, provider]);
  const savedForThis = view?.own?.provider === provider && view.own.has_api_key;

  const input = (test: boolean) => ({
    provider,
    api_key: apiKey || undefined,
    base_url: provider === "custom" ? baseUrl : undefined,
    chat_model: chatModel || undefined,
    triage_model: chatModel || undefined,
    test,
  });

  const runTest = async () => {
    setBusy("test");
    setResult(null);
    try {
      const r: AITestResult = await testAISettings(input(true));
      setResult(r.ok
        ? { tone: "ok", text: `Connected to ${r.model}. It answered in ${r.latency_ms} ms.` }
        : { tone: "error", text: r.error || "The provider did not accept this setup." });
    } catch (e) {
      setResult({ tone: "error", text: e instanceof Error ? e.message : "Test failed" });
    } finally {
      setBusy(null);
    }
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("save");
    setResult(null);
    try {
      const v = await saveAISettings(input(true));
      setView(v);
      setApiKey("");
      setResult({ tone: "ok", text: "Saved and verified. Rescoring your inbox with your model now." });
      // Drop locally saved scores so the inbox is rescored with the new model.
      try {
        Object.keys(localStorage)
          .filter((k) => /^mm_.+_(emails_v\d+_|enrich_cache)/.test(k))
          .forEach((k) => localStorage.removeItem(k));
      } catch {
        /* storage unavailable: server-side rescoring still applies */
      }
    } catch (err) {
      setResult({ tone: "error", text: err instanceof Error ? err.message : "Could not save" });
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    setBusy("remove");
    setResult(null);
    try {
      setView(await clearAISettings());
      setApiKey("");
      setResult({ tone: "ok", text: "Your key was removed." });
    } catch (err) {
      setResult({ tone: "error", text: err instanceof Error ? err.message : "Could not remove the key" });
    } finally {
      setBusy(null);
    }
  };

  const effective = view?.effective;

  return (
    <Panel
      title="AI model"
      intro="MailMind sorts mail and finds deadlines without any AI key. Add a free key from one of these providers for sharper ranking and drafts written in your voice. Personal details are hidden from the model either way."
    >
      {effective && (
        <div className="flex items-start gap-3 rounded-xl border border-rule bg-surface px-3.5 py-3">
          <CircleCheck className={`mt-0.5 size-4 shrink-0 ${effective.source === "rules" ? "text-ink-3" : "text-ok"}`} strokeWidth={1.75} aria-hidden />
          <p className="text-[13px] text-ink-2">
            {effective.source === "user" && <>Using <b className="font-medium text-ink">your {effective.provider} key</b> with {effective.chat_model}.</>}
            {effective.source === "server" && <>Using the shared campus model ({effective.chat_model}). Add your own key for your own quota.</>}
            {effective.source === "rules" && <>No AI model is connected. Sorting uses MailMind&apos;s built-in campus rules; drafts need a key.</>}
          </p>
        </div>
      )}

      <form onSubmit={save} className="grid gap-5">
        <fieldset>
          <legend className="mb-2 text-[13px] font-medium text-ink">Provider</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {providers.map((p) => (
              <label
                key={p.id}
                className={`flex cursor-pointer items-start gap-2.5 rounded-xl border px-3 py-2.5 transition-colors ${
                  provider === p.id ? "border-cobalt bg-cobalt-soft" : "border-rule bg-surface hover:bg-hover"
                }`}
              >
                <input
                  type="radio"
                  name="provider"
                  value={p.id}
                  checked={provider === p.id}
                  onChange={() => { setProvider(p.id); setChatModel(""); setResult(null); }}
                  className="mt-1 accent-[var(--mm-accent)]"
                />
                <span className="min-w-0">
                  <span className="flex items-center gap-2 text-[13.5px] font-medium text-ink">
                    {p.label}
                    {p.free_tier && <span className="rounded-full bg-ok-soft px-1.5 text-[10.5px] font-semibold text-ok">Free</span>}
                  </span>
                  <span className="block text-[12px] leading-snug text-ink-3">{p.notes}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        {preset?.requires_key !== false && (
          <Field
            label="API key"
            htmlFor="ai-key"
            hint={savedForThis ? `A key ending ${view?.own?.api_key_hint} is saved. Leave this empty to keep it.` : "Stored encrypted. Only a masked hint is ever shown back."}
          >
            <div className="flex gap-2">
              <input
                id="ai-key"
                type={showKey ? "text" : "password"}
                autoComplete="off"
                spellCheck={false}
                className={`${INPUT} font-mono`}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={savedForThis ? view?.own?.api_key_hint : "Paste your key"}
              />
              <button type="button" onClick={() => setShowKey((s) => !s)} aria-label={showKey ? "Hide key" : "Show key"}
                className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl border border-rule text-ink-3 hover:bg-hover hover:text-ink cursor-pointer">
                {showKey ? <EyeOff className="size-4" strokeWidth={1.75} /> : <Eye className="size-4" strokeWidth={1.75} />}
              </button>
            </div>
            {preset?.key_url && (
              <a href={preset.key_url} target="_blank" rel="noopener noreferrer" className="inline-flex w-fit items-center gap-1 text-[12.5px] text-cobalt hover:underline">
                Get a {preset.label} key <ExternalLink className="size-3" strokeWidth={1.75} aria-hidden />
              </a>
            )}
          </Field>
        )}

        {provider === "custom" && (
          <Field label="Base URL" htmlFor="ai-base" hint="Any OpenAI-compatible endpoint, over https.">
            <input id="ai-base" className={INPUT} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://example.com/v1" />
          </Field>
        )}

        <Field label="Model" htmlFor="ai-model" hint={preset?.default_chat_model ? `Leave empty to use ${preset.default_chat_model}.` : undefined}>
          <input id="ai-model" className={INPUT} list="ai-models" value={chatModel} onChange={(e) => setChatModel(e.target.value)}
            placeholder={preset?.default_chat_model || "model id"} />
          <datalist id="ai-models">
            {preset?.suggested_models.map((m) => <option key={m} value={m} />)}
          </datalist>
        </Field>

        {result && <Notice tone={result.tone}>{result.text}</Notice>}

        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="primary" loading={busy === "save"} disabled={!!busy}>Verify and save</Button>
          <Button variant="quiet" loading={busy === "test"} disabled={!!busy} onClick={runTest}>Test only</Button>
          {view?.own && (
            <Button variant="danger" loading={busy === "remove"} disabled={!!busy} onClick={remove} className="ml-auto">Remove my key</Button>
          )}
        </div>
      </form>
    </Panel>
  );
}

/* ─────────────── Writing voice ─────────────── */

function VoicePanel() {
  const [tone, setTone] = useState<ToneProfile | null | undefined>(undefined);
  const [building, setBuilding] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { fetchToneProfile().then(setTone); }, []);

  const learn = async () => {
    setBuilding(true);
    setErr(null);
    try {
      await buildToneProfile();
      setTone(await fetchToneProfile());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not read your sent mail");
    } finally {
      setBuilding(false);
    }
  };

  const f = tone?.features;
  const rows = f ? [
    ["Formality", f.formality_score > 0.66 ? "Formal" : f.formality_score < 0.34 ? "Casual" : "Polite, not stiff"],
    ["Sentence length", `About ${Math.round(f.avg_sentence_length)} words`],
    ["Usually opens with", f.greeting_patterns?.slice(0, 2).join(", ") || "No clear pattern"],
    ["Usually signs off", f.signoff_patterns?.slice(0, 2).join(", ") || "No clear pattern"],
    ["Contractions", f.contraction_rate > 0.05 ? "Uses them (I'll, don't)" : "Avoids them"],
    ["Lists", f.bullet_point_preference > 0.2 ? "Likes bullet points" : "Writes in prose"],
  ] : [];

  return (
    <Panel title="Writing voice" intro="Drafts are written the way you write. MailMind learns this from your sent mail in this account only, and never mixes accounts.">
      {tone === undefined ? (
        <span className="mm-skeleton block h-40" />
      ) : tone && f ? (
        <>
          <dl className="grid overflow-hidden rounded-xl border border-rule bg-surface sm:grid-cols-2">
            {rows.map(([k, v]) => (
              <div key={k} className="border-b border-rule px-4 py-3 sm:[&:nth-last-child(-n+2)]:border-b-0">
                <dt className="text-[12px] text-ink-3">{k}</dt>
                <dd className="mt-0.5 text-[13.5px] text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="text-[12.5px] text-ink-3">Learned from {tone.sample_size} sent emails.</p>
        </>
      ) : (
        <Notice tone="info">No voice profile yet. Let MailMind read your recent sent mail to learn it.</Notice>
      )}
      {err && <Notice tone="error">{err}</Notice>}
      <div>
        <Button variant={tone ? "quiet" : "primary"} icon={PenLine} loading={building} onClick={learn}>
          {tone ? "Relearn from sent mail" : "Learn my voice"}
        </Button>
      </div>
    </Panel>
  );
}

/* ─────────────── Shell ─────────────── */

export function Settings() {
  const [section, setSection] = useState<Section>("profile");
  const groups = [...new Set(SECTIONS.map((s) => s.group))];

  return (
    <section aria-label="Settings" className="flex h-full min-w-0 flex-1 flex-col bg-bg md:flex-row">
      <nav aria-label="Settings sections" className="shrink-0 border-b border-rule bg-surface px-3 py-3 md:w-60 md:border-b-0 md:border-r md:py-5">
        <h1 className="hidden px-2.5 pb-3 text-[17px] font-semibold tracking-tight text-ink md:block">Settings</h1>
        <div className="flex gap-1 overflow-x-auto md:block">
          {groups.map((g) => (
            <div key={g} className="contents md:block md:pb-3">
              <p className="hidden px-2.5 pb-1 text-[12px] font-medium text-ink-3 md:block">{g}</p>
              {SECTIONS.filter((s) => s.group === g).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSection(s.id)}
                  aria-current={section === s.id ? "page" : undefined}
                  className={`flex h-8 shrink-0 items-center gap-2.5 whitespace-nowrap rounded-lg px-2.5 text-[13.5px] transition-colors md:w-full cursor-pointer ${
                    section === s.id ? "bg-cobalt-soft font-medium text-ink" : "text-ink-2 hover:bg-hover hover:text-ink"
                  }`}
                >
                  <s.icon className={`size-4 ${section === s.id ? "text-cobalt" : "text-ink-3"}`} strokeWidth={1.75} aria-hidden />
                  {s.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      </nav>
      <div className="mm-scroll min-h-0 flex-1 overflow-y-auto">
        {section === "profile" && <ProfilePanel />}
        {section === "ai" && <AIPanel />}
        {section === "voice" && <VoicePanel />}
        {section === "privacy" && <div className="h-full"><PrivacyView /></div>}
        {section === "metrics" && <div className="h-full"><MetricsView /></div>}
        {section === "evaluation" && <div className="h-full"><EvaluationView /></div>}
        {section === "retrieval" && <div className="h-full"><RAGSettingsView /></div>}
      </div>
    </section>
  );
}
