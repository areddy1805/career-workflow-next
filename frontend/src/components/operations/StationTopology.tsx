import React, { Fragment } from 'react';
import { cn } from '@/lib/utils';
import { StateMarker, type StateSemantic } from '@/components/operations/StateMarker';

// ─── StationTopology — the signature component (DESIGN.md §3, §5, §15) ───────
// The real pipeline as stations on one conductor, with gate breakers on the
// flow segments and a dispatch position marker when a run is live.
// Every station/breaker is caller-supplied from real API data; nothing is
// invented here. Horizontal on md+, vertical station flow below md.

export interface TopoStation {
  id: string;
  label: string;
  state: StateSemantic;
  /** optional measurement under the label, e.g. "12" or "1.2s" */
  detail?: string;
}

export type BreakerState = 'closed' | 'open' | 'tagged';

export interface TopoBreaker {
  /** station id this gate follows */
  after: string;
  state: BreakerState;
  label?: string;
}

const BREAKER_GLYPH: Record<BreakerState, React.ReactNode> = {
  closed: <rect x="5" y="1" width="2" height="10" fill="currentColor" />,
  open: (
    <>
      <line x1="1" y1="6" x2="5" y2="6" stroke="currentColor" />
      <line x1="7" y1="6" x2="11" y2="6" stroke="currentColor" />
    </>
  ),
  tagged: (
    <>
      <rect x="5" y="1" width="2" height="10" fill="currentColor" />
      <rect x="8" y="1" width="3.5" height="3" fill="currentColor" />
    </>
  ),
};

export interface StationTopologyProps {
  stations: TopoStation[];
  breakers?: TopoBreaker[];
  /** dispatch position — the running station id, if any */
  activeId?: string | null;
  running?: boolean;
  className?: string;
  ariaLabel?: string;
}

export function StationTopology({
  stations,
  breakers = [],
  activeId,
  running,
  className,
  ariaLabel = 'Pipeline topology',
}: StationTopologyProps) {
  if (stations.length === 0) return null;

  const breakerByAfter = new Map(breakers.map((b) => [b.after, b]));

  return (
    <div className={cn('relative py-2', className)} role="group" aria-label={ariaLabel}>
      {/* conductor — horizontal on md+, vertical below */}
      <div
        className="absolute left-5 right-5 top-[15px] h-px bg-borderStrong hidden md:block"
        aria-hidden="true"
      />
      <div
        className="absolute left-[15px] top-2 bottom-2 w-px bg-borderStrong md:hidden"
        aria-hidden="true"
      />

      <ol className="relative flex flex-col md:flex-row md:items-stretch gap-y-5 md:gap-y-0">
        {stations.map((station, i) => {
          const brk = breakerByAfter.get(station.id);
          const isActive = station.id === activeId;
          return (
            <Fragment key={station.id}>
              {i > 0 && (
                <li
                  className="flex items-center justify-center shrink-0 md:flex-1 relative"
                  aria-hidden="true"
                >
                  {/* gate breaker on the segment */}
                  {brk && (
                    <span className="relative z-10 flex flex-col items-center gap-1">
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 12 12"
                        className={cn(
                          'state-snap',
                          brk.state === 'closed' && 'text-borderStrong',
                          brk.state === 'open' && 'text-faint',
                          brk.state === 'tagged' && 'text-manual'
                        )}
                      >
                        {BREAKER_GLYPH[brk.state]}
                      </svg>
                      {brk.label && (
                        <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-faint whitespace-nowrap">
                          {brk.label}
                        </span>
                      )}
                    </span>
                  )}
                  {!brk && <span className="h-px w-6 bg-borderStrong md:w-full hidden md:block" />}
                </li>
              )}
              <li className="flex items-center gap-2.5 md:flex-col md:gap-1.5 px-1 md:px-2 md:py-0 shrink-0">
                <StateMarker
                  state={station.state}
                  pulse={isActive && running}
                  size="md"
                  hideLabel
                  id={`station-${station.id}`}
                />
                <div className="text-left md:text-center min-w-0">
                  <p
                    className={cn(
                      'font-mono text-[10px] uppercase tracking-[0.08em] leading-tight whitespace-nowrap',
                      isActive ? 'text-foreground' : 'text-muted-foreground'
                    )}
                  >
                    {station.label}
                  </p>
                  {station.detail && (
                    <p className="text-[10px] text-faint tabular leading-tight mt-0.5 whitespace-nowrap">
                      {station.detail}
                    </p>
                  )}
                </div>
              </li>
            </Fragment>
          );
        })}
      </ol>
    </div>
  );
}
