import { useEffect, useState, type ReactNode } from 'react';
import { Bot, Cog, Database, Gauge, Rocket, Timer } from 'lucide-react';
import { cn } from '@/lib/utils';

// ─── Client-side preferences only (07_UI §3.8) ──────────────────────────────
// The backend has NO settings endpoint (autopilot defers to v5.2.0), so all
// state here is persisted to localStorage, mirroring the existing
// frontend/src/store/preferences.ts persist pattern — kept component-local
// because the store file is out of scope for CP-6-08.

const STORAGE_KEY = 'cw-copilot-settings';

interface CopilotSettings {
  /** Autopilot is OFF by default and per-session (client-side only). */
  autopilot: boolean;
  /** Opportunity source enablement, keyed by the frozen enum value. */
  sources: Record<string, boolean>;
}

// Frozen OpportunitySource enum (03_OPPORTUNITY_MODEL.md §2).
const SOURCES = [
  'manual_queue',
  'generic_url',
  'linkedin_url',
  'wellfound_url',
  'careers_url',
  'pasted_text',
  'pdf',
  'greenhouse',
  'lever',
  'ashby',
  'workday',
  'rippling',
  'recruiter_email',
  'recruiter_message',
  'screenshot',
  'html',
  'future',
];

const ALL_SOURCES_ENABLED = Object.fromEntries(
  SOURCES.map((s) => [s, true]),
) as Record<string, boolean>;

function loadSettings(): CopilotSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { autopilot: false, sources: { ...ALL_SOURCES_ENABLED } };
    const parsed = JSON.parse(raw) as Partial<CopilotSettings>;
    return {
      autopilot: parsed.autopilot ?? false,
      sources: { ...ALL_SOURCES_ENABLED, ...(parsed.sources ?? {}) },
    };
  } catch {
    return { autopilot: false, sources: { ...ALL_SOURCES_ENABLED } };
  }
}

function useCopilotSettings() {
  const [settings, setSettings] = useState<CopilotSettings>(loadSettings);
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
      // Storage unavailable (e.g. private mode) — keep in-memory state.
    }
  }, [settings]);
  return [settings, setSettings] as const;
}

// Frozen confidence thresholds (04_BROWSER_ASSISTANT.md §6) — reference table.
const THRESHOLDS: Array<{ confidence: string; behavior: string }> = [
  { confidence: '≥ 0.95, non-sensitive', behavior: 'Fill silently' },
  { confidence: '0.80 – 0.95', behavior: 'Fill + flag for review at checkpoint' },
  { confidence: '< 0.80', behavior: 'Do not fill; raise inline question' },
  { confidence: 'Sensitive field (PAN / DOB / address / bank)', behavior: 'Never auto-fill; always ask' },
  { confidence: 'manual_review answer', behavior: 'Never fill; ask' },
  { confidence: 'Unknown field (no fingerprint)', behavior: 'Skip; surface in review list' },
];

// Frozen profile set (07_UI §3.8) — read-only here; switching lives in the
// Learning / Workspace surfaces.
const PROFILES = [
  { id: 'ai', description: 'Answers tuned for applied-AI / ML roles' },
  { id: 'fde', description: 'Answers tuned for forward-deployed engineer roles' },
  { id: 'generic', description: 'General software-engineering answers' },
];

const humanize = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function Settings() {
  const [settings, setSettings] = useCopilotSettings();

  const toggleSource = (source: string) =>
    setSettings((s) => ({ ...s, sources: { ...s.sources, [source]: !s.sources[source] } }));

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <Cog className="w-4 h-4 text-primary" /> Settings
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Copilot thresholds, autopilot, and source enablement.
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-3xl mx-auto space-y-5 pb-8">
          {/* ── Profiles ── */}
          <SectionCard
            title="Profiles"
            description="Frozen profile set (ai / fde / generic). Read-only here — switching happens in Learning and the Workspace."
          >
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {PROFILES.map((p) => (
                <div key={p.id} className="rounded-lg border border-border/60 p-3 bg-muted/20">
                  <p className="text-sm font-semibold font-mono flex items-center gap-2">
                    <Bot className="w-3.5 h-3.5 text-primary" aria-hidden="true" /> {p.id}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">{p.description}</p>
                  <p className="text-[10px] text-muted-foreground/70 mt-2">Read-only</p>
                </div>
              ))}
            </div>
          </SectionCard>

          {/* ── Confidence thresholds ── */}
          <SectionCard
            title="Confidence thresholds"
            description="How the Browser Assistant decides to fill, flag, or ask (04_BROWSER_ASSISTANT.md §6). Reference only."
          >
            <div className="divide-y divide-border/50 rounded-lg border border-border/60">
              {THRESHOLDS.map((t) => (
                <div
                  key={t.confidence}
                  className="grid grid-cols-1 sm:grid-cols-2 gap-1 px-3 py-2.5 text-[13px]"
                >
                  <span className="font-mono text-xs">{t.confidence}</span>
                  <span className="text-muted-foreground">{t.behavior}</span>
                </div>
              ))}
            </div>
          </SectionCard>

          {/* ── Autopilot ── */}
          <SectionCard
            title="Autopilot"
            description="Run the full apply flow with minimal checkpoints."
          >
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium flex items-center gap-2">
                  <Rocket className="w-4 h-4 text-primary shrink-0" aria-hidden="true" /> Autopilot
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Off by default; applies per session.
                </p>
                {/* Backend defers autopilot to v5.2.0 — no settings endpoint,
                    so this is a client-side preference only (see header note). */}
                <p className="text-[10px] text-muted-foreground/70 mt-1">
                  Client-side preference only — the backend defers autopilot to v5.2.0.
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={settings.autopilot}
                aria-label="Autopilot"
                onClick={() => setSettings((s) => ({ ...s, autopilot: !s.autopilot }))}
                className={cn(
                  'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                  settings.autopilot ? 'bg-primary' : 'bg-muted',
                )}
              >
                <span
                  className={cn(
                    'inline-block h-4 w-4 transform rounded-full bg-background transition-transform',
                    settings.autopilot ? 'translate-x-6' : 'translate-x-1',
                  )}
                />
              </button>
            </div>
          </SectionCard>

          {/* ── Source enablement ── */}
          <SectionCard
            title="Source enablement"
            description="Which opportunity sources feed the inbox. Frozen list (03_OPPORTUNITY_MODEL.md §2); persisted to localStorage."
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
              {SOURCES.map((src) => (
                <label
                  key={src}
                  className="flex items-center justify-between gap-3 px-3 py-2 rounded-md hover:bg-muted/30 cursor-pointer"
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <input
                      type="checkbox"
                      checked={!!settings.sources[src]}
                      onChange={() => toggleSource(src)}
                      className="accent-primary"
                    />
                    <span className="text-[13px] truncate">{humanize(src)}</span>
                  </span>
                  <code className="text-[10px] font-mono text-muted-foreground shrink-0">
                    {src}
                  </code>
                </label>
              ))}
            </div>
          </SectionCard>

          {/* ── Effort caps + LLM budget ── */}
          <SectionCard
            title="Effort caps & LLM budget"
            description="Per-application effort limits and inference budget usage."
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-lg border border-border/60 p-3">
                <p className="text-xs text-muted-foreground flex items-center gap-2">
                  <Timer className="w-3.5 h-3.5" aria-hidden="true" /> Effort cap (per application)
                </p>
                <p className="text-sm font-mono mt-1">—</p>
                <p className="text-[10px] text-muted-foreground/70 mt-1">
                  Not computed yet.
                </p>
              </div>
              <div className="rounded-lg border border-border/60 p-3">
                <p className="text-xs text-muted-foreground flex items-center gap-2">
                  <Gauge className="w-3.5 h-3.5" aria-hidden="true" /> LLM budget usage
                </p>
                <p className="text-sm font-mono mt-1">—</p>
                <p className="text-[10px] text-muted-foreground/70 mt-1">
                  Not computed yet.
                </p>
              </div>
            </div>
          </SectionCard>

          {/* ── Sources icon legend (decorative) ── */}
          <p className="text-[10px] text-muted-foreground/60 flex items-center gap-1.5">
            <Database className="w-3 h-3" aria-hidden="true" />
            All settings on this page are stored locally in{' '}
            <code className="font-mono">{STORAGE_KEY}</code>. The backend has no settings
            endpoint.
          </p>
        </div>
      </div>
    </div>
  );
}

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-card border border-border/60 rounded-xl shadow-sm">
      <div className="px-4 py-3 border-b border-border/50">
        <h2 className="text-sm font-semibold">{title}</h2>
        {description && (
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        )}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}
