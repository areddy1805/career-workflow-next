import { useEffect, useState } from 'react';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { fetchJobDetails } from '@/lib/api';
import { Loader2, AlertCircle } from 'lucide-react';
import { JobInspectorContent } from '@/components/JobInspector';

interface JobDrawerProps {
  jobId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTransitioned: () => void;
}

export function JobDrawer({ jobId, open, onOpenChange, onTransitioned }: JobDrawerProps) {
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [data, setData]               = useState<any>(null);
  const [jsonOpen, setJsonOpen]       = useState(false);

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

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-[760px] p-0 flex flex-col border-l border-border/50">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex h-full items-center justify-center px-6">
            <div className="flex items-start gap-2 text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-md p-3">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              {error}
            </div>
          </div>
        ) : data && jobId ? (
          <JobInspectorContent
            data={data}
            jobId={jobId}
            variant="queue"
            onOpenJson={() => setJsonOpen(true)}
            onTransitioned={onTransitioned}
          />
        ) : null}

        {/* JSON debug view — secondary */}
        <Dialog open={jsonOpen} onOpenChange={setJsonOpen}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-auto">
            <DialogHeader>
              <DialogTitle className="text-sm">Job Data</DialogTitle>
            </DialogHeader>
            <pre className="text-[11px] font-mono bg-console text-console-foreground/75 p-4 rounded-md overflow-auto leading-relaxed">
              {JSON.stringify(data, null, 2)}
            </pre>
          </DialogContent>
        </Dialog>
      </SheetContent>
    </Sheet>
  );
}
