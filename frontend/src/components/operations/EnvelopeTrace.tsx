import { cn } from '@/lib/utils';

// ─── EnvelopeTrace — load vs operating envelope (DESIGN.md §3, §8, §15) ──────
// A throughput series drawn against a labeled policy bound (run limit, budget,
// cap). Flat fills only — no gradients. Renders nothing when empty; the caller
// decides the honest empty state.

export interface EnvelopePoint {
  x: number;
  y: number;
}

export interface EnvelopeTraceProps {
  points: EnvelopePoint[];
  /** operating-envelope ceiling (same units as y) */
  bound?: number;
  boundLabel?: string;
  yMax?: number;
  xLabel?: string;
  yLabel?: string;
  className?: string;
}

const W = 320;
const H = 96;
const PAD = 4;

export function EnvelopeTrace({
  points,
  bound,
  boundLabel,
  yMax,
  xLabel,
  yLabel,
  className,
}: EnvelopeTraceProps) {
  if (points.length === 0) return null;

  const max = yMax ?? Math.max(bound ?? 0, ...points.map((p) => p.y), 1);
  const top = PAD;
  const bottom = H - PAD;
  const span = max || 1;

  const toX = (x: number) => PAD + (x / Math.max(...points.map((p) => p.x), 1)) * (W - PAD * 2);
  const toY = (y: number) => bottom - (y / span) * (bottom - top);

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(p.x).toFixed(1)},${toY(p.y).toFixed(1)}`).join(' ');
  const area = `${line} L${toX(points[points.length - 1].x).toFixed(1)},${bottom} L${toX(points[0].x).toFixed(1)},${bottom} Z`;
  const boundY = bound != null ? toY(bound) : null;

  return (
    <div className={cn('relative', className)}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        role="img"
        aria-label={yLabel ? `${yLabel} load trace` : 'Load trace'}
      >
        {/* hairline grid — emphasized ticks only */}
        {[0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={PAD}
            x2={W - PAD}
            y1={top + f * (bottom - top)}
            y2={top + f * (bottom - top)}
            stroke="hsl(var(--border))"
            strokeWidth="1"
          />
        ))}
        {boundY != null && (
          <line
            x1={PAD}
            x2={W - PAD}
            y1={boundY}
            y2={boundY}
            stroke="hsl(var(--border-strong))"
            strokeDasharray="4 3"
            strokeWidth="1"
          />
        )}
        <path d={area} fill="hsl(var(--chart-1) / 0.14)" stroke="none" />
        <path d={line} fill="none" stroke="hsl(var(--chart-1))" strokeWidth="1.5" strokeLinejoin="round" />
        {/* last point — live reading */}
        <circle
          cx={toX(points[points.length - 1].x)}
          cy={toY(points[points.length - 1].y)}
          r="2.5"
          fill="hsl(var(--chart-1))"
          className="pulse-live"
        />
      </svg>
      {boundLabel && boundY != null && (
        <span
          className="absolute right-0 font-mono text-[9px] uppercase tracking-[0.08em] text-faint translate-y-[-50%]"
          style={{ top: `${(boundY / H) * 100}%` }}
        >
          {boundLabel}
        </span>
      )}
      {xLabel && yLabel && (
        <div className="flex justify-between mt-1 font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
          <span>{xLabel}</span>
          <span>{yLabel}</span>
        </div>
      )}
    </div>
  );
}
