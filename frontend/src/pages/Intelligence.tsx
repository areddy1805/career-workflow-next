import { useIntelligence, useDashboard } from '@/lib/hooks';
import { useState, useMemo } from 'react';
import {
  Search as SearchIcon, Globe, MapPin, Layers, Cpu,
  Filter, ChevronDown, ChevronRight, Zap, Database, Server,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { SectionTitle } from '@/components/operations/SectionTitle';
import { StatusBadge } from '@/components/operations/StatusBadge';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

// ─── Provider Health Card ───────────────────────────────────────────────────

const PROVIDER_META: Record<string, { label: string; icon: string; color: string }> = {
  naukri: { label: 'Naukri', icon: 'N', color: 'text-indigo-500' },
  google: { label: 'Google Jobs', icon: 'G', color: 'text-blue-500' },
  indeed: { label: 'Indeed', icon: 'I', color: 'text-yellow-500' },
  linkedin: { label: 'LinkedIn', icon: 'in', color: 'text-sky-500' },
};

function ProviderCard({ id, data }: { id: string; data: any }) {
  const meta = PROVIDER_META[id] ?? { label: id, icon: id[0].toUpperCase(), color: 'text-primary' };
  const isActive = data.status === 'active' || data.status === 'HEALTHY';
  const isDegraded = data.status === 'degraded' || data.status === 'WARNING';
  const successPct = ((data.success_rate ?? 0) * 100).toFixed(0);
  const latency = (data.average_latency_seconds ?? 0).toFixed(2);

  return (
    <div className="flex flex-col p-4 rounded-md border border-border bg-card shadow-card group hover:border-foreground/20 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={cn('w-8 h-8 rounded border border-border bg-muted/30 flex items-center justify-center text-[10px] font-bold tracking-wider', meta.color)}>
            {meta.icon}
          </div>
          <div>
            <p className="font-semibold text-[13px] tracking-tight leading-none mb-1 text-foreground">{meta.label}</p>
            <p className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">{id}</p>
          </div>
        </div>
        <StatusBadge 
          status={isActive ? 'success' : isDegraded ? 'warning' : 'neutral'} 
          label={isActive ? 'Active' : isDegraded ? 'Degraded' : 'Unknown'} 
        />
      </div>

      <div className="grid grid-cols-3 gap-2 mt-auto">
        <div className="border border-border/50 bg-muted/20 rounded p-2 text-center group-hover:bg-muted/40 transition-colors">
          <p className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1 font-semibold">Queries</p>
          <p className="text-[13px] font-bold font-mono text-foreground">{data.total_searches ?? 0}</p>
        </div>
        <div className="border border-border/50 bg-muted/20 rounded p-2 text-center group-hover:bg-muted/40 transition-colors">
          <p className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1 font-semibold">Success</p>
          <p className={cn('text-[13px] font-bold font-mono', Number(successPct) >= 90 ? 'text-emerald-500' : 'text-amber-500')}>{successPct}%</p>
        </div>
        <div className="border border-border/50 bg-muted/20 rounded p-2 text-center group-hover:bg-muted/40 transition-colors">
          <p className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1 font-semibold">Latency</p>
          <p className={cn('text-[13px] font-bold font-mono', Number(latency) > 10 ? 'text-amber-500' : 'text-foreground')}>{latency}s</p>
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
    <div className="overflow-auto max-h-[400px]">
      <table className="text-[10px] border-collapse w-full">
        <thead className="bg-muted/30 sticky top-0 z-10 backdrop-blur-sm">
          <tr>
            <th className="text-left px-4 py-3 text-muted-foreground font-semibold tracking-wider uppercase border-b border-r border-border min-w-[180px]">Profile</th>
            {orderedTechs.map(t => (
              <th key={t} className="px-3 py-3 text-center text-muted-foreground font-semibold tracking-wider uppercase border-b border-border whitespace-nowrap min-w-[80px]">
                {TECH_LABELS[t] ?? t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {profiles.map((profile) => (
            <tr key={profile} className="hover:bg-muted/30 transition-colors">
              <td className="px-4 py-2.5 font-mono text-[10px] font-medium text-foreground border-r border-border/50 sticky left-0 bg-card z-10 whitespace-nowrap">
                {(profile as string).replace(/_/g, ' ')}
              </td>
              {orderedTechs.map(tech => {
                const key = `${profile}|${tech}`;
                const has = matrix.has(key);
                const tier = tierMap.get(key);
                return (
                  <td key={tech} className="text-center py-2.5">
                    {has ? (
                      <span title={`${tier}`} className={cn(
                        'inline-block w-4 h-4 rounded-sm mx-auto shadow-sm',
                        tier === 'TIER_A' ? 'bg-primary' : 'bg-muted-foreground/40'
                      )} />
                    ) : (
                      <span className="inline-block w-4 h-4 rounded-sm mx-auto bg-muted/20 border border-border/30" />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-5 px-4 py-3 border-t border-border text-[9px] text-muted-foreground uppercase tracking-widest font-semibold bg-muted/10">
        <span className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-primary inline-block" /> TIER_A (Priority)</span>
        <span className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-muted-foreground/40 inline-block" /> TIER_B</span>
        <span className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-muted/20 border border-border/30 inline-block" /> No Coverage</span>
      </div>
    </div>
  );
}

// ─── Query Browser ────────────────────────────────────────────────────────────

function QueryBrowser({ queries }: { queries: any[] }) {
  const [filter, setFilter] = useState('');
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
    if (tierFilter) q = q.filter((r: any) => r.track === tierFilter);
    return q;
  }, [queries, filter, tierFilter]);

  const grouped = useMemo(() => {
    const g: Record<string, any[]> = {};
    filtered.forEach((q: any) => {
      if (!g[q.search_profile]) g[q.search_profile] = [];
      g[q.search_profile].push(q);
    });
    return g;
  }, [filtered]);

  return (
    <div className="flex flex-col gap-0 h-full">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-card/50">
        <Filter className="w-4 h-4 text-muted-foreground shrink-0" />
        <Input
          placeholder="Filter active queries…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="h-8 text-[11px] bg-background/50 border-0 focus-visible:ring-0 flex-1 p-0 placeholder:text-muted-foreground/50 shadow-none font-mono"
        />
        <div className="flex items-center gap-1.5 shrink-0 border-l border-border pl-3">
          {['TIER_A', 'TIER_B'].map(t => (
            <button
              key={t}
              onClick={() => setTierFilter(tierFilter === t ? null : t)}
              className={cn(
                'text-[9px] font-bold uppercase tracking-widest px-2 py-1 rounded transition-colors',
                tierFilter === t
                  ? t === 'TIER_A' ? 'bg-primary text-primary-foreground' : 'bg-muted-foreground text-background'
                  : 'text-muted-foreground bg-muted/40 hover:bg-muted'
              )}
            >{t}</button>
          ))}
        </div>
        <span className="text-[10px] text-muted-foreground font-mono ml-2 border-l border-border pl-3">{filtered.length} QUERIES</span>
      </div>

      <div className="overflow-auto flex-1">
        {Object.entries(grouped).map(([profile, qs]) => {
          const isOpen = expanded === profile || expanded === '__ALL__';
          const tierA = qs.filter((q: any) => q.track === 'TIER_A').length;
          const tierB = qs.filter((q: any) => q.track === 'TIER_B').length;
          return (
            <div key={profile} className="border-b border-border/50 last:border-0 group">
              <button
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/20 text-left transition-colors"
                onClick={() => setExpanded(isOpen ? null : profile)}
              >
                {isOpen ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />}
                <span className="font-mono text-[11px] font-medium flex-1 text-foreground">{profile.replace(/_/g, ' ')}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[9px] font-mono bg-primary/10 text-primary border border-primary/20 px-1.5 py-0.5 rounded shadow-sm">{tierA} TIER_A</span>
                  {tierB > 0 && <span className="text-[9px] font-mono bg-muted text-muted-foreground border border-border/50 px-1.5 py-0.5 rounded shadow-sm">{tierB} TIER_B</span>}
                </div>
              </button>
              {isOpen && (
                <div className="bg-background border-t border-border/20">
                  {qs.map((q: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-start gap-4 px-8 py-2.5 border-b border-border/20 last:border-0 hover:bg-muted/10 transition-colors"
                    >
                      <span className={cn(
                        'text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded shrink-0 mt-0.5 border',
                        q.track === 'TIER_A' ? 'bg-primary/5 text-primary border-primary/20' : 'bg-muted/30 text-muted-foreground border-border/50'
                      )}>{q.track}</span>
                      <div className="flex-1 min-w-0 flex items-center h-[22px]">
                        <p className="font-mono text-[11px] text-muted-foreground group-hover:text-foreground transition-colors leading-relaxed break-words truncate">
                          {q.keyword}
                        </p>
                      </div>
                      <Badge variant="outline" className="text-[9px] font-mono shrink-0 h-[22px] flex items-center tracking-tight border-border/50 text-muted-foreground">
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
          <div className="py-20 flex flex-col items-center justify-center text-center">
            <SearchIcon className="w-8 h-8 text-muted-foreground/30 mb-3" />
            <p className="text-sm font-medium text-foreground">No queries found</p>
            <p className="text-xs text-muted-foreground mt-1">Try adjusting your filters.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function Search() {
  const { data, isLoading: siLoading } = useIntelligence();
  const { data: dashboard, isLoading: dashLoading } = useDashboard();

  const isLoading = siLoading || dashLoading;

  const { active_profiles = [], locations = [], total_queries = 0, queries = [] } = data || {};
  const providerHealth: Record<string, any> = dashboard?.provider_health ?? {};

  const tierCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    queries.forEach((q: any) => { counts[q.track] = (counts[q.track] || 0) + 1; });
    return counts;
  }, [queries]);

  // const techCounts = useMemo(() => {
  //   const counts: Record<string, number> = {};
  //   queries.forEach((q: any) => { counts[q.matched_technology] = (counts[q.matched_technology] || 0) + 1; });
  //   return counts;
  // }, [queries]);

  if (isLoading) {
    return (
      <div className="h-full flex flex-col p-6 animate-in fade-in duration-300">
        <div className="animate-pulse space-y-6">
          <div className="h-10 bg-muted/50 w-1/3 rounded-md" />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-32 bg-muted/50 rounded-md" />)}</div>
          <div className="h-80 bg-muted/50 rounded-md" />
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col animate-in fade-in duration-300 overflow-auto">
      <SectionTitle 
        title="Search Intelligence" 
        subtitle="Active search strategy, provider health, and query coverage matrix."
      />

      <div className="flex-1 flex flex-col gap-8 pb-8">

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-card border border-border rounded-md shadow-card p-5">
            <p className="text-[10px] uppercase tracking-widest font-semibold text-muted-foreground mb-2 flex items-center gap-2"><Layers className="w-3.5 h-3.5" /> Active Profiles</p>
            <p className="text-2xl font-bold tracking-tight text-foreground font-mono">{active_profiles.length}</p>
          </div>
          <div className="bg-card border border-border rounded-md shadow-card p-5">
            <p className="text-[10px] uppercase tracking-widest font-semibold text-muted-foreground mb-2 flex items-center gap-2"><MapPin className="w-3.5 h-3.5" /> Locations</p>
            <p className="text-2xl font-bold tracking-tight text-foreground font-mono">{locations.length}</p>
            <p className="text-[10px] text-muted-foreground mt-1 truncate">{(locations as string[]).join(', ')}</p>
          </div>
          <div className="bg-card border border-border rounded-md shadow-card p-5">
            <p className="text-[10px] uppercase tracking-widest font-semibold text-muted-foreground mb-2 flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Tier A Queries</p>
            <p className="text-2xl font-bold tracking-tight text-primary font-mono">{tierCounts['TIER_A'] ?? 0}</p>
            <p className="text-[10px] text-muted-foreground mt-1">Priority acquisition</p>
          </div>
          <div className="bg-card border border-border rounded-md shadow-card p-5">
            <p className="text-[10px] uppercase tracking-widest font-semibold text-muted-foreground mb-2 flex items-center gap-2"><Database className="w-3.5 h-3.5" /> Total Combos</p>
            <p className="text-2xl font-bold tracking-tight text-foreground font-mono">{total_queries.toLocaleString()}</p>
            <p className="text-[10px] text-muted-foreground mt-1">TIER_B: {tierCounts['TIER_B'] ?? 0}</p>
          </div>
        </div>

        {/* Provider Health */}
        <div>
          <h3 className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground mb-3 flex items-center gap-2">
            <Server className="w-3.5 h-3.5" />
            Multi-Provider Health
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {Object.entries(providerHealth).map(([id, ph]) => (
              <ProviderCard key={id} id={id} data={ph} />
            ))}
            {Object.keys(providerHealth).length === 0 && (
              <div className="col-span-4 text-sm text-muted-foreground text-center py-8 border border-dashed border-border/50 rounded-md bg-muted/10">
                No provider health data — run the pipeline to collect metrics.
              </div>
            )}
          </div>
        </div>

        {/* Coverage Matrix & Query Browser Layout */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
          <div className="flex flex-col h-full min-h-[400px]">
            <h3 className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground mb-3 flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5" />
              Coverage Matrix
            </h3>
            <div className="bg-card border border-border rounded-md shadow-card flex-1">
              <CoverageMatrix queries={queries} />
            </div>
          </div>
          
          <div className="flex flex-col h-full min-h-[400px]">
            <h3 className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground mb-3 flex items-center gap-2">
              <Globe className="w-3.5 h-3.5" />
              Active Query Browser
            </h3>
            <div className="bg-card border border-border rounded-md shadow-card flex-1 max-h-[445px]">
              <QueryBrowser queries={queries} />
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
