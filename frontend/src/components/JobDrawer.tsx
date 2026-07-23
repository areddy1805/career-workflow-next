import { useEffect, useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useQueryClient } from '@tanstack/react-query';
import { fetchJobDetails, transitionQueueJob } from '@/lib/api';
import { formatSalary, cn } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';
import { RelativeTime } from '@/components/RelativeTime';
import { Loader2, ExternalLink, CheckCircle, XCircle, SkipForward, Brain, AlertCircle } from 'lucide-react';

interface JobDrawerProps {
  jobId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTransitioned: () => void;
}

function scoreColor(score: number | null | undefined) {
  if (score == null) return 'text-muted-foreground';
  if (score >= 70) return 'text-emerald-500';
  if (score >= 40) return 'text-amber-500';
  return 'text-red-400';
}

export function JobDrawer({ jobId, open, onOpenChange, onTransitioned }: JobDrawerProps) {
  const [loading, setLoading]         = useState(false);
  const [transitioning, setTransitioning] = useState<string | null>(null);
  const [error, setError]             = useState<string | null>(null);
  const [data, setData]               = useState<any>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (jobId && open) {
      setLoading(true);
      setError(null);
      fetchJobDetails(jobId)
        .then(res => setData(res))
        .catch(err => { console.error(err); setError('Failed to load job details.'); })
        .finally(() => setLoading(false));
    } else {
      setData(null);
      setError(null);
    }
  }, [jobId, open]);

  const handleTransition = async (status: string) => {
    if (!jobId) return;
    setTransitioning(status);
    setError(null);
    try {
      await transitionQueueJob(jobId, status, 'From Drawer');
      queryClient.invalidateQueries({ queryKey: ['queue'] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      onTransitioned();
      onOpenChange(false);
    } catch (e: any) {
      console.error(e);
      setError(`Action failed — this job may not allow this transition from its current state.`);
    } finally {
      setTransitioning(null);
    }
  };

  const getJobUrl = () => {
    const url = data?.overview?.apply_url || data?.overview?.apply_link || data?.overview?.url || data?.overview?.source_url;
    if (!url) return null;
    if (url.startsWith('http')) return url;
    if (url.startsWith('job-listings-') || url.startsWith('/job-listings-')) {
      return `https://www.naukri.com/${url.replace(/^\//, '')}`;
    }
    return `https://www.naukri.com/job-listings-${url}`;
  };

  const jobUrl = getJobUrl();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-[600px] p-0 flex flex-col border-l border-border/50">
        {loading || !data ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            {/* Header */}
            <SheetHeader className="px-5 pt-5 pb-4 border-b border-border/40 bg-muted/10">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <SheetTitle className="text-base font-bold leading-snug truncate">{data.overview?.title}</SheetTitle>
                  <SheetDescription className="text-sm mt-1">
                    <span className="font-medium text-foreground">{data.overview?.company}</span>
                    {data.overview?.location && <> · <span className="text-muted-foreground">{data.overview.location}</span></>}
                  </SheetDescription>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <StatusBadge status={data.overview?.workflow_status ?? data.overview?.status ?? 'UNKNOWN'} />
                  {data.overview?.score != null && (
                    <span className={cn('text-xs font-mono font-bold tabular-nums', scoreColor(data.overview.score))}>
                      {data.overview.score}
                    </span>
                  )}
                </div>
              </div>
            </SheetHeader>

            <ScrollArea className="flex-1">
              <div className="px-5 py-5 space-y-5">

                {/* AI Assessment — elevated to the top */}
                {(data.overview?.reasoning || data.overview?.notes || data.overview?.ai_reason) && (
                  <div className="bg-primary/5 border border-primary/15 rounded-lg p-4">
                    <div className="flex items-center gap-1.5 mb-2">
                      <Brain className="w-3.5 h-3.5 text-primary" />
                      <p className="text-[10px] font-semibold text-primary uppercase tracking-wider">AI Assessment</p>
                    </div>
                    <p className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap">
                      {data.overview.reasoning ?? data.overview.ai_reason ?? data.overview.notes}
                    </p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex flex-wrap gap-2">
                  {jobUrl && (
                    <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5" onClick={() => window.open(jobUrl, '_blank', 'noopener,noreferrer')}>
                      <ExternalLink className="w-3 h-3" /> Open Externally
                    </Button>
                  )}
                  <Button
                    size="sm"
                    className="h-8 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white border-0"
                    onClick={() => handleTransition('APPLIED')}
                    disabled={!!transitioning}
                  >
                    {transitioning === 'APPLIED' ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                    Mark Applied
                  </Button>
                  <Button
                    variant="outline" size="sm"
                    className="h-8 text-xs gap-1.5 text-red-500 border-red-500/30 hover:bg-red-500/10"
                    onClick={() => handleTransition('REJECTED')}
                    disabled={!!transitioning}
                  >
                    {transitioning === 'REJECTED' ? <Loader2 className="w-3 h-3 animate-spin" /> : <SkipForward className="w-3 h-3" />}
                    Skip
                  </Button>
                  <Button
                    variant="ghost" size="sm"
                    className="h-8 text-xs gap-1.5 text-destructive hover:bg-destructive/10"
                    onClick={() => handleTransition('ARCHIVED')}
                    disabled={!!transitioning}
                  >
                    {transitioning === 'ARCHIVED' ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
                    Dismiss
                  </Button>
                </div>

                {/* Error */}
                {error && (
                  <div className="flex items-start gap-2 text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-md p-3">
                    <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    {error}
                  </div>
                )}

                {/* Metadata Grid */}
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: 'Experience', value: data.overview?.experience },
                    { label: 'Salary',     value: data.overview?.salary ? formatSalary(data.overview.salary) : null },
                    { label: 'Source',     value: data.overview?.source },
                    { label: 'Priority',   value: data.overview?.priority },
                  ].filter(m => m.value).map(m => (
                    <div key={m.label} className="bg-muted/30 rounded-md p-3">
                      <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{m.label}</p>
                      <p className="text-xs font-medium">{String(m.value)}</p>
                    </div>
                  ))}
                </div>

                {/* Application Timeline */}
                {data.events?.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">Application History</p>
                    <div className="space-y-0 relative before:absolute before:left-[5px] before:top-2 before:bottom-2 before:w-px before:bg-border/50">
                      {data.events.map((evt: any, i: number) => (
                        <div key={i} className="relative pl-4 py-2">
                          <div className="absolute left-[2px] top-3 w-2 h-2 rounded-full bg-border border-2 border-background z-10" />
                          <div className="flex items-center gap-2 flex-wrap">
                            <StatusBadge status={evt.status} />
                            <span className="text-[10px] text-muted-foreground">
                              <RelativeTime date={evt.timestamp ?? evt.created_at} />
                            </span>
                          </div>
                          {(evt.note || evt.detail) && (
                            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{evt.note ?? evt.detail}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Job Description */}
                {data.overview?.description && (
                  <div>
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">Job Description</p>
                    <div
                      className="text-xs bg-muted/20 border border-border/30 p-4 rounded-lg max-h-[400px] overflow-y-auto leading-relaxed [&>p]:mb-3 [&>ul]:list-disc [&>ul]:pl-5 [&>ul]:mb-3"
                      dangerouslySetInnerHTML={{ __html: data.overview.description }}
                    />
                  </div>
                )}

              </div>
            </ScrollArea>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
