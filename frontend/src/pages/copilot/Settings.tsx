import { useEffect, useState } from 'react';
import { Bot, Database, Gauge, Rocket, Timer } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PageHeader } from '@/components/operations/PageHeader';
import { Panel, PanelHeader } from '@/components/operations/Panel';
import { Checkbox } from '@/components/ui/checkbox';

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
      <PageHeader
        coordinate="03 · 05"
        title="Settings"
        subtitle="Copilot thresholds, autopilot, and source enablement."
      />

      <div className="flex-1 overflow-auto pb-8">
        <div className="max-w-3xl mx-auto space-y-5">
          <Panel>
            <PanelHeader
              title="Profiles"
              actions={<span className="font-mono text-[10px] text-faint uppercase tracking-wider">Read-only</span>}
            />
            <div className="p-4">
              <p className="text-meta text-muted-foreground mb-3 max-w-[65ch]">
                Frozen profile set (ai / fde / generic). Switching happens in Learning and the Workspace.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {PROFILES.map((p) => (
                  <div key={p.id} className="rounded-md border border-border p-3 bg-muted/20">
                    <p className="text-sm font-semibold font-mono flex items-center gap-2">
                      <Bot className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" /> {p.id}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">{p.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </Panel>

          {/* ── Confidence thresholds ── */}
          <Panel>
            <PanelHeader title="Confidence thresholds" />
            <div className="p-4">
              <p className="text-meta text-muted-foreground mb-3 max-w-[65ch]">
                How the Browser Assistant decides to fill, flag, or ask (04_BROWSER_ASSISTANT.md §6). Reference only.
              </p>
              <div className="divide-y divide-border rounded-md border border-border">
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
            </div>
          </Panel>

          {/* ── Autopilot ── */}
          <Panel>
            <PanelHeader title="Autopilot" />
            <div className="p-4">
              <p className="text-meta text-muted-foreground mb-3 max-w-[65ch]">
                Run the full apply flow with minimal checkpoints. Off by default; applies per session.
              </p>
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium flex items-center gap-2">
                    <Rocket className="w-4 h-4 text-muted-foreground shrink-0" aria-hidden="true" /> Autopilot
                  </p>
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
            </div>
          </Panel>

          {/* ── Source enablement ── */}
          <Panel>
            <PanelHeader title="Source enablement" />
            <div className="p-4">
              <p className="text-meta text-muted-foreground mb-3 max-w-[65ch]">
                Which opportunity sources feed the inbox. Frozen list (03_OPPORTUNITY_MODEL.md §2); persisted to localStorage.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                {SOURCES.map((src) => (
                  <label
                    key={src}
                    className="flex items-center justify-between gap-3 px-3 py-2 rounded-md hover:bg-muted/30 cursor-pointer"
                  >
                    <span className="flex items-center gap-2 min-w-0">
                      <Checkbox
                        checked={!!settings.sources[src]}
                        onCheckedChange={() => toggleSource(src)}
                        aria-label={humanize(src)}
                      />
                      <span className="text-[13px] truncate">{humanize(src)}</span>
                    </span>
                    <code className="text-[10px] font-mono text-muted-foreground shrink-0">
                      {src}
                    </code>
                  </label>
                ))}
              </div>
            </div>
          </Panel>

          {/* ── Effort caps + LLM budget ── */}
          <Panel>
            <PanelHeader title="Effort caps & LLM budget" />
            <div className="p-4">
              <p className="text-meta text-muted-foreground mb-3 max-w-[65ch]">
                Per-application effort limits and inference budget usage.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="rounded-md border border-border p-3">
                  <p className="text-xs text-muted-foreground flex items-center gap-2">
                    <Timer className="w-3.5 h-3.5" aria-hidden="true" /> Effort cap (per application)
                  </p>
                  <p className="text-sm font-mono mt-1">—</p>
                  <p className="text-[10px] text-muted-foreground/70 mt-1">
                    Not computed yet.
                  </p>
                </div>
                <div className="rounded-md border border-border p-3">
                  <p className="text-xs text-muted-foreground flex items-center gap-2">
                    <Gauge className="w-3.5 h-3.5" aria-hidden="true" /> LLM budget usage
                  </p>
                  <p className="text-sm font-mono mt-1">—</p>
                  <p className="text-[10px] text-muted-foreground/70 mt-1">
                    Not computed yet.
                  </p>
                </div>
              </div>
            </div>
          </Panel>

          {/* ── Sources icon legend (decorative) ── */}
          <p className="text-[10px] text-muted-foreground/60 flex items-center gap-1.5 px-1">
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
