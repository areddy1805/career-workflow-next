import { useQuery } from '@tanstack/react-query';
import { fetchSearchIntelligence, fetchDashboard } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useState, useMemo } from 'react';
import {
  Search as SearchIcon, Globe, MapPin, Layers, Cpu,
  Filter, ChevronDown, ChevronRight, Zap, Database, Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ─── Provider Health Card ───────────────────────────────────────────────────

const PROVIDER_META: Record<string, { label: string; icon: string; color: string }> = {
  naukri: { label: 'Naukri', icon: 'N', color: 'text-indigo-500' },
  google: { label: 'Google Jobs', icon: 'G', color: 'text-blue-500' },
  indeed: { label: 'Indeed', icon: 'I', color: 'text-yellow-500' },
  linkedin: { label: 'LinkedIn', icon: 'in', color: 'text-sky-500' },
};

function ProviderCard({ id, data }: { id: string; data: any }) {
  const meta = PROVIDER_META[id] ?? { label: id, icon: id[0].toUpperCase(), color: 'text-primary' };
  const isActive = data.status === 'active';
  const isDegraded = data.status === 'degraded';
  const successPct = ((data.success_rate ?? 0) * 100).toFixed(0);
  const latency = (data.average_latency_seconds ?? 0).toFixed(2);

  return (
    <div className={cn(
      'flex flex-col gap-3 p-4 rounded-lg border bg-card',
      isActive ? 'border-green-500/20' : isDegraded ? 'border-amber-500/20' : 'border-border/50'
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold bg-muted', meta.color)}>
            {meta.icon}
          </div>
          <div>
            <p className="font-semibold text-sm leading-tight">{meta.label}</p>
            <p className="text-[9px] text-muted-foreground font-mono uppercase">{id}</p>
          </div>
        </div>
        <div className={cn(
          'text-[9px] font-bold uppercase px-2 py-0.5 rounded-full border',
          isActive ? 'bg-green-500/10 text-green-500 border-green-500/30'
            : isDegraded ? 'bg-amber-500/10 text-amber-500 border-amber-500/30'
            : 'bg-muted text-muted-foreground border-border'
        )}>
          {isActive ? '● Active' : isDegraded ? '▲ Degraded' : '○ Unknown'}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-muted/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Queries</p>
          <p className="text-lg font-bold font-mono">{data.total_searches ?? 0}</p>
        </div>
        <div className="bg-muted/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Success</p>
          <p className={cn('text-lg font-bold font-mono', Number(successPct) >= 90 ? 'text-green-500' : 'text-amber-500')}>{successPct}%</p>
        </div>
        <div className="bg-muted/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Latency</p>
          <p className={cn('text-lg font-bold font-mono', Number(latency) > 10 ? 'text-amber-400' : 'text-foreground')}>{latency}s</p>
        </div>
      </div>
    </div>
  );
}

// ─── Coverage Matrix ─────────────────────────────────────────────────────────

const TECH_LABELS: Record<string, string> = {
  role_only: 'Role Only',
  Anthropic: 'Anthropic',
  'Azure OpenAI': 'Azure OAI',
  Embeddings: 'Embeddings',
  LLM: 'LLM',
  LangChain: 'LangChain',
  OpenAI: 'OpenAI',
  'Prompt Engineering': 'Prompt Eng',
  RAG: 'RAG',
  'Vector Search': 'Vec Search',
};

function CoverageMatrix({ queries }: { queries: any[] }) {
  const profiles = [...new Set(queries.map((q: any) => q.search_profile))].sort();
  const techs = [...new Set(queries.map((q: any) => q.matched_technology))];
  const techOrder = ['role_only', 'LLM', 'OpenAI', 'Anthropic', 'Azure OpenAI', 'LangChain', 'RAG', 'Embeddings', 'Vector Search', 'Prompt Engineering'];
  const orderedTechs = [...techOrder.filter(t => techs.includes(t)), ...techs.filter(t => !techOrder.includes(t))];

  const matrix = new Set(queries.map((q: any) => `${q.search_profile}|${q.matched_technology}`));
  const tierMap = new Map(queries.map((q: any) => [`${q.search_profile}|${q.matched_technology}`, q.track]));

  return (
    <div className="overflow-auto">
      <table className="text-[10px] border-collapse w-full">
        <thead>
          <tr>
            <th className="text-left px-3 py-2 text-muted-foreground font-medium border-b border-r border-border/40 bg-muted/10 sticky left-0 z-10 min-w-[160px]">Profile</th>
            {orderedTechs.map(t => (
              <th key={t} className="px-2 py-2 text-center text-muted-foreground font-medium border-b border-border/40 whitespace-nowrap min-w-[72px]">
                {TECH_LABELS[t] ?? t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {profiles.map((profile, ri) => (
            <tr key={profile} className={ri % 2 === 0 ? 'bg-transparent' : 'bg-muted/5'}>
              <td className="px-3 py-1.5 font-mono border-r border-b border-border/20 sticky left-0 bg-card z-10 text-[10px] whitespace-nowrap">
                {(profile as string).replace(/_/g, ' ')}
              </td>
              {orderedTechs.map(tech => {
                const key = `${profile}|${tech}`;
                const has = matrix.has(key);
                const tier = tierMap.get(key);
                return (
                  <td key={tech} className="border-b border-border/10 text-center py-1.5">
                    {has ? (
                      <span title={`${tier}`} className={cn(
                        'inline-block w-4 h-4 rounded-sm mx-auto',
                        tier === 'TIER_A' ? 'bg-primary/80' : 'bg-primary/30'
                      )} />
                    ) : (
                      <span className="inline-block w-4 h-4 rounded-sm mx-auto bg-muted/30 opacity-30" />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-4 px-3 py-2 border-t border-border/30 text-[9px] text-muted-foreground">
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-primary/80 inline-block" /> TIER_A (priority)</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-primary/30 inline-block" /> TIER_B</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-muted/30 opacity-30 inline-block" /> No query</span>
      </div>
    </div>
  );
}

// ─── Query Browser ────────────────────────────────────────────────────────────

function QueryBrowser({ queries }: { queries: any[] }) {
  const [filter, setFilter] = useState('');
  const [profileFilter] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>('__ALL__');

  const filtered = useMemo(() => {
    let q = queries;
    if (filter) {
      const lc = filter.toLowerCase();
      q = q.filter((r: any) =>
        r.keyword.toLowerCase().includes(lc) ||
        r.search_profile.toLowerCase().includes(lc) ||
        (r.matched_technology || '').toLowerCase().includes(lc)
      );
    }
    if (profileFilter) q = q.filter((r: any) => r.search_profile === profileFilter);
    if (tierFilter) q = q.filter((r: any) => r.track === tierFilter);
    return q;
  }, [queries, filter, profileFilter, tierFilter]);

  // Group by profile
  const grouped = useMemo(() => {
    const g: Record<string, any[]> = {};
    filtered.forEach((q: any) => {
      if (!g[q.search_profile]) g[q.search_profile] = [];
      g[q.search_profile].push(q);
    });
    return g;
  }, [filtered]);

  return (
    <div className="flex flex-col gap-0">
      {/* Filter Bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b bg-muted/10">
        <Filter className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
        <Input
          placeholder="Filter queries…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="h-7 text-xs bg-transparent border-0 focus-visible:ring-0 flex-1 p-0 placeholder:text-muted-foreground/50"
        />
        <div className="flex items-center gap-1 shrink-0">
          {['TIER_A', 'TIER_B'].map(t => (
            <button
              key={t}
              onClick={() => setTierFilter(tierFilter === t ? null : t)}
              className={cn(
                'text-[9px] font-bold uppercase px-2 py-0.5 rounded border transition-colors',
                tierFilter === t
                  ? t === 'TIER_A' ? 'bg-primary/20 text-primary border-primary/40' : 'bg-muted text-foreground border-border'
                  : 'text-muted-foreground border-border/50 hover:border-border'
              )}
            >{t}</button>
          ))}
        </div>
        <span className="text-[10px] text-muted-foreground shrink-0">{filtered.length} queries</span>
      </div>

      {/* Profile group rows */}
      <div className="overflow-auto max-h-[500px]">
        {Object.entries(grouped).map(([profile, qs]) => {
          const isOpen = expanded === profile || expanded === '__ALL__';
          const tierA = qs.filter((q: any) => q.track === 'TIER_A').length;
          const tierB = qs.filter((q: any) => q.track === 'TIER_B').length;
          return (
            <div key={profile} className="border-b border-border/30 last:border-0">
              <button
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-muted/30 text-left transition-colors"
                onClick={() => setExpanded(isOpen ? null : profile)}
              >
                {isOpen ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />}
                <span className="font-mono text-xs font-medium flex-1">{profile.replace(/_/g, ' ')}</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] font-mono bg-primary/20 text-primary px-1.5 py-0.5 rounded">{tierA} TIER_A</span>
                  {tierB > 0 && <span className="text-[9px] font-mono bg-muted text-muted-foreground px-1.5 py-0.5 rounded">{tierB} TIER_B</span>}
                </div>
              </button>
              {isOpen && (
                <div className="bg-muted/5 border-t border-border/20">
                  {qs.map((q: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-start gap-3 px-8 py-2 border-b border-border/10 last:border-0 hover:bg-muted/20"
                    >
                      <span className={cn(
                        'text-[8px] font-bold uppercase px-1.5 py-0.5 rounded shrink-0 mt-0.5',
                        q.track === 'TIER_A' ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'
                      )}>{q.track}</span>
                      <div className="flex-1 min-w-0">
                        <p className="font-mono text-[11px] text-foreground/80 leading-relaxed break-words">{q.keyword}</p>
                      </div>
                      <Badge variant="outline" className="text-[8px] font-mono shrink-0 h-4">
                        {q.matched_technology === 'role_only' ? 'Base' : q.matched_technology}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {Object.keys(grouped).length === 0 && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            <SearchIcon className="w-8 h-8 mx-auto mb-2 opacity-20" />
            No queries match the filter.
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Search() {
  const { data, isLoading: siLoading } = useQuery({
    queryKey: ['search_intelligence'],
    queryFn: fetchSearchIntelligence,
  });

  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
  });

  const isLoading = siLoading || dashLoading;

  const { active_profiles = [], locations = [], total_queries = 0, queries = [] } = data || {};
  const providerHealth: Record<string, any> = dashboard?.provider_health ?? {};

  const tierCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    queries.forEach((q: any) => { counts[q.track] = (counts[q.track] || 0) + 1; });
    return counts;
  }, [queries]);

  const techCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    queries.forEach((q: any) => { counts[q.matched_technology] = (counts[q.matched_technology] || 0) + 1; });
    return counts;
  }, [queries]);

  if (isLoading) {
    return (
      <div className="h-full flex flex-col bg-background p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted w-1/4 rounded" />
          <div className="grid grid-cols-3 gap-3">{[1,2,3].map(i => <div key={i} className="h-36 bg-muted rounded-lg" />)}</div>
          <div className="h-64 bg-muted rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background overflow-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Search Intelligence</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Provider health, query coverage, and active search strategy.
            <span className="ml-1 text-muted-foreground/60">{active_profiles.length} profiles · {locations.length} location{locations.length !== 1 ? 's' : ''} · {total_queries} queries</span>
          </p>
        </div>
      </div>

      <div className="flex-1 p-5 space-y-5 max-w-[1600px]">

        {/* ── Section 1: Provider Health ──────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-3.5 h-3.5 text-muted-foreground" />
            <h3 className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">Multi-Provider Health</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {Object.entries(providerHealth).map(([id, ph]) => (
              <ProviderCard key={id} id={id} data={ph} />
            ))}
            {Object.keys(providerHealth).length === 0 && (
              <div className="col-span-3 text-sm text-muted-foreground text-center py-8 border border-dashed rounded-lg">
                No provider health data — run the pipeline to collect metrics.
              </div>
            )}
          </div>
        </section>

        {/* ── Section 2: Stats Row ─────────────────────────────────────── */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-card border border-border/50 rounded-lg p-4">
            <p className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground mb-1 flex items-center gap-1"><Layers className="w-3 h-3" /> Active Profiles</p>
            <p className="text-2xl font-bold tracking-tight">{active_profiles.length}</p>
          </div>
          <div className="bg-card border border-border/50 rounded-lg p-4">
            <p className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground mb-1 flex items-center gap-1"><MapPin className="w-3 h-3" /> Locations</p>
            <p className="text-2xl font-bold tracking-tight">{locations.length}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">{(locations as string[]).join(', ')}</p>
          </div>
          <div className="bg-card border border-border/50 rounded-lg p-4">
            <p className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground mb-1 flex items-center gap-1"><Zap className="w-3 h-3 text-primary" /> TIER_A Queries</p>
            <p className="text-2xl font-bold tracking-tight text-primary">{tierCounts['TIER_A'] ?? 0}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">Priority acquisition</p>
          </div>
          <div className="bg-card border border-border/50 rounded-lg p-4">
            <p className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground mb-1 flex items-center gap-1"><Database className="w-3 h-3" /> Total Combinations</p>
            <p className="text-2xl font-bold tracking-tight">{total_queries.toLocaleString()}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">TIER_B: {tierCounts['TIER_B'] ?? 0}</p>
          </div>
        </section>

        {/* ── Section 3: Coverage Matrix ──────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Cpu className="w-3.5 h-3.5 text-muted-foreground" />
            <h3 className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
              Query Coverage Matrix — {active_profiles.length} Profiles × {Object.keys(techCounts).length} Technologies
            </h3>
          </div>
          <div className="bg-card border border-border/50 rounded-lg overflow-hidden">
            <CoverageMatrix queries={queries} />
          </div>
        </section>

        {/* ── Section 4: Query Browser ────────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Globe className="w-3.5 h-3.5 text-muted-foreground" />
            <h3 className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">Active Query Browser</h3>
          </div>
          <div className="bg-card border border-border/50 rounded-lg overflow-hidden">
            <QueryBrowser queries={queries} />
          </div>
        </section>

      </div>
    </div>
  );
}
